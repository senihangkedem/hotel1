from django.contrib import admin

from .models import InventoryItem, InventoryTransaction


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
	list_display = ("name", "restaurant", "quantity_on_hand", "unit", "is_active")
	list_filter = ("restaurant", "unit", "is_active")
	search_fields = ("name", "restaurant__name")
	readonly_fields = ("quantity_on_hand",)


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
	list_display = (
		"inventory_item",
		"transaction_type",
		"source",
		"quantity",
		"order",
		"created_by",
		"created_at",
	)
	list_filter = ("transaction_type", "source", "created_at")
	search_fields = ("inventory_item__name", "order__id", "created_by__username")
	readonly_fields = tuple(field.name for field in InventoryTransaction._meta.fields)

	def has_add_permission(self, request):
		return False

	def has_delete_permission(self, request, obj=None):
		return False
