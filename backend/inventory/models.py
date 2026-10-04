from django.conf import settings
from django.db import models


class InventoryItem(models.Model):
	class Unit(models.TextChoices):
		KILOGRAM = "kg", "Kilogram"
		GRAM = "g", "Gram"
		LITRE = "litre", "Litre"
		MILLILITRE = "ml", "Millilitre"
		PIECE = "piece", "Piece"

	restaurant = models.ForeignKey(
		"restaurants.Restaurant",
		on_delete=models.CASCADE,
		related_name="inventory_items",
	)
	name = models.CharField(max_length=150)
	unit = models.CharField(max_length=10, choices=Unit.choices)
	quantity_on_hand = models.DecimalField(max_digits=15, decimal_places=6, default=0)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["name"]
		constraints = [
			models.UniqueConstraint(
				fields=["restaurant", "name"],
				name="unique_inventory_item_name_per_restaurant",
			),
			models.CheckConstraint(
				condition=models.Q(quantity_on_hand__gte=0),
				name="inventory_quantity_nonnegative",
			),
		]

	def __str__(self):
		return f"{self.name} ({self.restaurant.name})"


class InventoryTransaction(models.Model):
	class Type(models.TextChoices):
		IN = "IN", "Stock in"
		OUT = "OUT", "Stock out"
		ADJUSTMENT = "ADJUSTMENT", "Adjustment"
		REVERSAL = "REVERSAL", "Order reversal"

	class Source(models.TextChoices):
		MANUAL = "MANUAL", "Manual"
		ORDER = "ORDER", "Order"

	inventory_item = models.ForeignKey(
		InventoryItem,
		on_delete=models.PROTECT,
		related_name="transactions",
	)
	transaction_type = models.CharField(max_length=12, choices=Type.choices)
	source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
	quantity = models.DecimalField(max_digits=15, decimal_places=6)
	order = models.ForeignKey(
		"orders.Order",
		on_delete=models.PROTECT,
		related_name="inventory_transactions",
		null=True,
		blank=True,
	)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		related_name="inventory_transactions",
		null=True,
		blank=True,
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at", "-id"]
		constraints = [
			models.UniqueConstraint(
				fields=["order", "inventory_item", "transaction_type"],
				condition=models.Q(order__isnull=False),
				name="unique_order_inventory_transaction_type",
			),
			models.CheckConstraint(
				condition=(
					models.Q(transaction_type="ADJUSTMENT")
					| models.Q(quantity__gt=0)
				),
				name="non_adjustment_inventory_quantity_positive",
			),
		]

	def __str__(self):
		return f"{self.transaction_type} {self.quantity} {self.inventory_item.unit} {self.inventory_item.name}"
