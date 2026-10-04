from rest_framework import viewsets

from restaurants.permissions import IsRestaurantOperationsAccess, related_restaurant_scope

from .models import Category, MenuItem, MenuItemIngredient
from .permissions import RecipeAccessPermission
from .serializers import CategorySerializer, MenuItemIngredientSerializer, MenuItemSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsRestaurantOperationsAccess]

    def get_queryset(self):
        queryset = Category.objects.select_related(
            "restaurant",
            "restaurant__owner",
        )

        if self.request.user.is_superuser:
            return queryset
        if self.request.user.role == "CUSTOMER":
            return queryset.filter(
                is_active=True,
                restaurant__is_active=True,
            )

        return queryset.filter(related_restaurant_scope(self.request.user)).distinct()


class MenuItemViewSet(viewsets.ModelViewSet):
    serializer_class = MenuItemSerializer
    permission_classes = [IsRestaurantOperationsAccess]

    def get_queryset(self):
        queryset = MenuItem.objects.select_related(
            "restaurant",
            "restaurant__owner",
            "category",
        )

        if self.request.user.is_superuser:
            return queryset
        if self.request.user.role == "CUSTOMER":
            return queryset.filter(
                is_available=True,
                restaurant__is_active=True,
            )

        return queryset.filter(related_restaurant_scope(self.request.user)).distinct()


class MenuItemIngredientViewSet(viewsets.ModelViewSet):
    serializer_class = MenuItemIngredientSerializer
    permission_classes = [RecipeAccessPermission]

    def get_queryset(self):
        queryset = MenuItemIngredient.objects.select_related(
            "menu_item",
            "menu_item__restaurant",
            "inventory_item",
        )
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(
            related_restaurant_scope(
                self.request.user,
                relation="menu_item__restaurant",
            ),
        ).distinct()


    