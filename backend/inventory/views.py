from rest_framework import mixins, viewsets
from rest_framework.permissions import BasePermission

from restaurants.models import Restaurant
from restaurants.permissions import MANAGER_ROLES, can_manage_restaurant, related_restaurant_scope

from .models import InventoryItem, InventoryTransaction
from .serializers import InventoryItemSerializer, InventoryTransactionSerializer


class InventoryManagerPermission(BasePermission):
	def has_permission(self, request, view):
		user = request.user
		if not user or not user.is_authenticated:
			return False
		return bool(
			user.is_superuser
			or Restaurant.objects.filter(owner=user).exists()
			or user.restaurant_memberships.filter(
				role__in=MANAGER_ROLES,
				is_active=True,
			).exists()
		)

	def has_object_permission(self, request, view, obj):
		if request.user.is_superuser:
			return True
		restaurant_id = getattr(obj, "restaurant_id", None)
		if restaurant_id is None:
			restaurant_id = obj.inventory_item.restaurant_id
		return can_manage_restaurant(request.user, restaurant_id)


class InventoryItemViewSet(viewsets.ModelViewSet):
	serializer_class = InventoryItemSerializer
	permission_classes = [InventoryManagerPermission]

	def get_queryset(self):
		queryset = InventoryItem.objects.select_related("restaurant")
		if self.request.user.is_superuser:
			return queryset
		return queryset.filter(
			related_restaurant_scope(self.request.user, roles=MANAGER_ROLES),
		).distinct()


class InventoryTransactionViewSet(
	mixins.ListModelMixin,
	mixins.CreateModelMixin,
	viewsets.GenericViewSet,
):
	serializer_class = InventoryTransactionSerializer
	permission_classes = [InventoryManagerPermission]
	http_method_names = ["get", "post", "head", "options"]

	def get_queryset(self):
		queryset = InventoryTransaction.objects.select_related(
			"inventory_item",
			"inventory_item__restaurant",
			"order",
			"created_by",
		)
		if self.request.user.is_superuser:
			return queryset
		return queryset.filter(
			related_restaurant_scope(
				self.request.user,
				relation="inventory_item__restaurant",
				roles=MANAGER_ROLES,
			),
		).distinct()
