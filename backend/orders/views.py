from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Order, OrderItem
from .permissions import OrderAccessPermission
from .serializers import OrderSerializer, OrderItemSerializer, OrderTransitionSerializer
from restaurants.permissions import related_restaurant_scope
from inventory.services import transition_order_status
from realtime.services import emit_order_event


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [OrderAccessPermission]

    def get_queryset(self):
        user = self.request.user
        queryset = Order.objects.select_related(
            "restaurant",
            "restaurant__owner",
            "table",
            "customer",
        ).prefetch_related("items__menu_item")

        if user.is_superuser:
            return queryset

        return queryset.filter(
            related_restaurant_scope(user) | Q(customer=user),
        ).distinct()

    def perform_create(self, serializer):
        order = serializer.save(customer=self.request.user)
        emit_order_event(
            order,
            "order.created",
            status=order.status,
            payment_status=order.payment_status,
        )

    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        order = self.get_object()
        transition_serializer = OrderTransitionSerializer(data=request.data)
        transition_serializer.is_valid(raise_exception=True)
        updated_order = transition_order_status(
            order.id,
            transition_serializer.validated_data["status"],
            request.user,
        )
        emit_order_event(
            updated_order,
            "order.status_changed",
            status=updated_order.status,
            payment_status=updated_order.payment_status,
        )
        return Response(
            self.get_serializer(updated_order).data,
            status=status.HTTP_200_OK,
        )


class OrderItemViewSet(viewsets.ModelViewSet):
    serializer_class = OrderItemSerializer
    permission_classes = [OrderAccessPermission]

    def get_queryset(self):
        user = self.request.user
        queryset = OrderItem.objects.select_related(
            "order",
            "order__restaurant",
            "order__customer",
            "menu_item",
            "menu_item__restaurant",
        )

        if user.is_superuser:
            return queryset

        return queryset.filter(
            related_restaurant_scope(user, relation="order__restaurant")
            | Q(order__customer=user),
        ).distinct()