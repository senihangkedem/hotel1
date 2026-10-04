from django.db.models import Q
from rest_framework.permissions import BasePermission

from user_accounts.models import User

from .models import Restaurant, RestaurantStaff


STAFF_ROLES = tuple(role for role, _label in RestaurantStaff.STAFF_ROLE_CHOICES)
MANAGER_ROLES = (User.Role.MANAGER,)


def restaurant_scope(user, roles=None):
    scope = Q(owner=user)
    memberships = Q(
        staff_memberships__user=user,
        staff_memberships__is_active=True,
    )
    if roles is not None:
        memberships &= Q(staff_memberships__role__in=roles)
    return scope | memberships


def related_restaurant_scope(user, relation="restaurant", roles=None):
    owner_field = f"{relation}__owner"
    user_field = f"{relation}__staff_memberships__user"
    active_field = f"{relation}__staff_memberships__is_active"
    role_field = f"{relation}__staff_memberships__role__in"
    memberships = Q(**{user_field: user, active_field: True})
    if roles is not None:
        memberships &= Q(**{role_field: roles})
    return Q(**{owner_field: user}) | memberships


def has_restaurant_access(user, restaurant_id, roles=None):
    if user.is_superuser:
        return True

    if Restaurant.objects.filter(id=restaurant_id, owner=user).exists():
        return True

    memberships = RestaurantStaff.objects.filter(
        user=user,
        restaurant_id=restaurant_id,
        is_active=True,
    )
    if roles is not None:
        memberships = memberships.filter(role__in=roles)
    return memberships.exists()


def can_manage_restaurant(user, restaurant_id):
    return user.is_superuser or has_restaurant_access(
        user,
        restaurant_id,
        roles=MANAGER_ROLES,
    )


def has_active_staff_membership(user, roles=None):
    memberships = RestaurantStaff.objects.filter(user=user, is_active=True)
    if roles is not None:
        memberships = memberships.filter(role__in=roles)
    return memberships.exists()


def has_public_restaurant_access(user, restaurant_id):
    return bool(
        user.role == User.Role.CUSTOMER
        and Restaurant.objects.filter(id=restaurant_id, is_active=True).exists()
    )


class IsRestaurantOwnerOrSuperuser(BasePermission):
    """Allow restaurant management only to owners and superusers."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or user.role == "OWNER")
        )

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        owner_id = getattr(obj, "owner_id", None)
        if owner_id is None:
            owner_id = obj.restaurant.owner_id

        return owner_id == request.user.id


class IsRestaurantReadOrOwner(BasePermission):
    """Allow restaurant staff to read only restaurants they belong to."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            return (
                request.method == "POST"
                and user.role == User.Role.OWNER
            ) or Restaurant.objects.filter(owner=user).exists()
        return (
            Restaurant.objects.filter(owner=user).exists()
            or has_active_staff_membership(user)
            or user.role == User.Role.CUSTOMER
            or user.role == User.Role.OWNER
        )

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            return obj.owner_id == request.user.id
        return (
            has_restaurant_access(request.user, obj.id)
            or has_public_restaurant_access(request.user, obj.id)
        )


class IsRestaurantOperationsAccess(BasePermission):
    """Owners and managers can operate; active staff can read scoped data."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return (
                Restaurant.objects.filter(owner=user).exists()
                or has_active_staff_membership(user)
                or user.role == User.Role.CUSTOMER
                or user.role == User.Role.OWNER
            )
        return (
            Restaurant.objects.filter(owner=user).exists()
            or has_active_staff_membership(user, MANAGER_ROLES)
        )

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        restaurant_id = getattr(obj, "restaurant_id", obj.id)
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return (
                has_restaurant_access(request.user, restaurant_id)
                or has_public_restaurant_access(request.user, restaurant_id)
            )
        return can_manage_restaurant(request.user, restaurant_id)


class IsRestaurantStaffManager(BasePermission):
    """Staff membership administration is restricted to restaurant owners."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or Restaurant.objects.filter(owner=user).exists())
        )

    def has_object_permission(self, request, view, obj):
        return request.user.is_superuser or obj.restaurant.owner_id == request.user.id