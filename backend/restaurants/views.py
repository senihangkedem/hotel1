from rest_framework import viewsets

from .models import Restaurant, RestaurantTable
from .permissions import (
    IsRestaurantOperationsAccess,
    IsRestaurantReadOrOwner,
    IsRestaurantStaffManager,
    related_restaurant_scope,
    restaurant_scope,
)
from .serializers import (
    RestaurantSerializer,
    RestaurantStaffCreateSerializer,
    RestaurantStaffSerializer,
    RestaurantTableSerializer,
)
from .models import RestaurantStaff


class RestaurantViewSet(viewsets.ModelViewSet):
    serializer_class = RestaurantSerializer
    permission_classes = [IsRestaurantReadOrOwner]

    def get_queryset(self):
        queryset = Restaurant.objects.select_related("owner")

        if self.request.user.is_superuser:
            return queryset
        if self.request.user.role == "CUSTOMER":
            return queryset.filter(is_active=True)

        return queryset.filter(restaurant_scope(self.request.user)).distinct()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class RestaurantTableViewSet(viewsets.ModelViewSet):
    serializer_class = RestaurantTableSerializer
    permission_classes = [IsRestaurantOperationsAccess]

    def get_queryset(self):
        queryset = RestaurantTable.objects.select_related(
            "restaurant",
            "restaurant__owner",
        )

        if self.request.user.is_superuser:
            return queryset
        if self.request.user.role == "CUSTOMER":
            return queryset.filter(is_active=True, restaurant__is_active=True)

        return queryset.filter(related_restaurant_scope(self.request.user)).distinct()


class RestaurantStaffViewSet(viewsets.ModelViewSet):
    permission_classes = [IsRestaurantStaffManager]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = RestaurantStaff.objects.select_related("user", "restaurant")
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(restaurant__owner=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return RestaurantStaffCreateSerializer
        return RestaurantStaffSerializer

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])