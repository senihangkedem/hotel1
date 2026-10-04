from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.response import Response

from orders.models import Order
from restaurants.models import Restaurant
from restaurants.permissions import (
    MANAGER_ROLES,
    has_restaurant_access,
    related_restaurant_scope,
    restaurant_scope,
)
from user_accounts.models import User

from .models import Bill
from .permissions import BILL_READ_ROLES, BillingAccessPermission, BillingSettingsPermission
from .serializers import (
    BillCreateSerializer,
    BillPaymentSerializer,
    BillSerializer,
    RestaurantBillingSettingsSerializer,
)
from .services import mark_bill_paid


class BillViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [BillingAccessPermission]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = Bill.objects.select_related(
            "order",
            "order__table",
            "restaurant",
            "created_by",
        ).prefetch_related("lines")
        user = self.request.user
        if user.is_superuser:
            scoped = queryset
        else:
            scoped = queryset.filter(
                Q(order__customer=user)
                | Q(restaurant__owner=user)
                | Q(
                    restaurant__staff_memberships__user=user,
                    restaurant__staff_memberships__is_active=True,
                    restaurant__staff_memberships__role__in=BILL_READ_ROLES,
                ),
            ).distinct()
        order_id = self.request.query_params.get("order")
        if order_id:
            if not order_id.isdecimal():
                raise ValidationError({"order": "Order must be a numeric ID."})
            scoped = scoped.filter(order_id=int(order_id))
        return scoped

    def get_serializer_class(self):
        if self.action == "create":
            return BillCreateSerializer
        if self.action == "pay":
            return BillPaymentSerializer
        return BillSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bill = serializer.save()
        return Response(BillSerializer(bill, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        serializer.save()

    @action(detail=True, methods=["post"], url_path="pay")
    def pay(self, request, pk=None):
        bill = self.get_object()
        payment_serializer = BillPaymentSerializer(data=request.data)
        payment_serializer.is_valid(raise_exception=True)
        paid_bill = mark_bill_paid(
            bill_id=bill.id,
            payment_method=payment_serializer.validated_data["payment_method"],
            user=request.user,
        )
        return Response(BillSerializer(paid_bill, context=self.get_serializer_context()).data)


class RestaurantBillingSettingsView(RetrieveUpdateAPIView):
    permission_classes = [BillingSettingsPermission]
    serializer_class = RestaurantBillingSettingsSerializer
    queryset = Restaurant.objects.all()
    lookup_url_kwarg = "restaurant_id"

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Restaurant.objects.all()
        return Restaurant.objects.filter(
            restaurant_scope(self.request.user, roles=MANAGER_ROLES),
        ).distinct()
