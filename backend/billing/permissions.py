from django.db.models import Q
from rest_framework.permissions import BasePermission

from restaurants.models import Restaurant
from restaurants.permissions import MANAGER_ROLES, has_restaurant_access
from user_accounts.models import User


BILL_READ_ROLES = (User.Role.MANAGER, User.Role.WAITER)


class BillingAccessPermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return (
                user.role == User.Role.CUSTOMER
                or Restaurant.objects.filter(owner=user).exists()
                or user.restaurant_memberships.filter(
                    role__in=BILL_READ_ROLES,
                    is_active=True,
                ).exists()
            )
        return (
            Restaurant.objects.filter(owner=user).exists()
            or user.restaurant_memberships.filter(
                role__in=MANAGER_ROLES,
                is_active=True,
            ).exists()
        )

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return (
                obj.order.customer_id == request.user.id
                or has_restaurant_access(
                    request.user,
                    obj.restaurant_id,
                    roles=(User.Role.MANAGER, User.Role.WAITER),
                )
                or obj.restaurant.owner_id == request.user.id
            )
        return obj.restaurant.owner_id == request.user.id or has_restaurant_access(
            request.user,
            obj.restaurant_id,
            roles=MANAGER_ROLES,
        )


class BillingSettingsPermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        return obj.owner_id == request.user.id or has_restaurant_access(
            request.user,
            obj.id,
            roles=MANAGER_ROLES,
        )
