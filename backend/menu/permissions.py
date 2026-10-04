from rest_framework.permissions import BasePermission

from restaurants.models import Restaurant
from restaurants.permissions import MANAGER_ROLES, has_active_staff_membership


class RecipeAccessPermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if user.role == "CUSTOMER":
            return False
        if Restaurant.objects.filter(owner=user).exists():
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return has_active_staff_membership(user)
        return has_active_staff_membership(user, MANAGER_ROLES)

    def has_object_permission(self, request, view, obj):
        from restaurants.permissions import can_manage_restaurant, has_restaurant_access

        restaurant_id = obj.menu_item.restaurant_id
        if request.user.is_superuser:
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return has_restaurant_access(request.user, restaurant_id)
        return can_manage_restaurant(request.user, restaurant_id)