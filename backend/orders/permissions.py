from rest_framework.permissions import BasePermission

from restaurants.permissions import can_manage_restaurant, has_restaurant_access


class OrderAccessPermission(BasePermission):
    """Keep staff order views read-only until staff transitions are implemented."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        order = getattr(obj, "order", obj)
        is_safe_method = request.method in ("GET", "HEAD", "OPTIONS")
        if not is_safe_method and getattr(view, "action", None) != "transition" and hasattr(order, "bill"):
            return False
        if request.user.is_superuser:
            return True
        if getattr(view, "action", None) == "transition":
            return can_manage_restaurant(request.user, order.restaurant_id)
        if is_safe_method:
            return (
                order.customer_id == request.user.id
                or has_restaurant_access(request.user, order.restaurant_id)
            )

        return (
            order.customer_id == request.user.id
            or order.restaurant.owner_id == request.user.id
        )