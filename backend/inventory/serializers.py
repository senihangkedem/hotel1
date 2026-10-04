from django.db import transaction
from rest_framework import serializers

from restaurants.models import Restaurant
from restaurants.permissions import can_manage_restaurant

from .models import InventoryItem, InventoryTransaction
from .services import create_manual_transaction


class InventoryItemSerializer(serializers.ModelSerializer):
    restaurant = serializers.PrimaryKeyRelatedField(queryset=Restaurant.objects.all())
    starting_quantity = serializers.DecimalField(
        max_digits=15,
        decimal_places=6,
        min_value=0,
        write_only=True,
        required=False,
    )

    class Meta:
        model = InventoryItem
        fields = [
            "id",
            "restaurant",
            "name",
            "unit",
            "quantity_on_hand",
            "starting_quantity",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "quantity_on_hand", "created_at", "updated_at"]

    def validate(self, attrs):
        restaurant = attrs.get("restaurant", getattr(self.instance, "restaurant", None))
        if restaurant is None or not can_manage_restaurant(
            self.context["request"].user,
            restaurant.id,
        ):
            raise serializers.ValidationError({
                "restaurant": "You can only manage inventory for restaurants you own or manage.",
            })

        if self.instance and restaurant.id != self.instance.restaurant_id:
            raise serializers.ValidationError({
                "restaurant": "An inventory item cannot be moved to another restaurant.",
            })
        if self.instance and "starting_quantity" in attrs:
            raise serializers.ValidationError({
                "starting_quantity": "Opening stock can only be set when creating an inventory item.",
            })

        if self.instance and "unit" in attrs and attrs["unit"] != self.instance.unit:
            if self.instance.transactions.exists() or self.instance.menu_recipes.exists():
                raise serializers.ValidationError({
                    "unit": "An inventory unit cannot change after it is used by a recipe or stock transaction.",
                })
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        starting_quantity = validated_data.pop("starting_quantity", 0)
        item = InventoryItem.objects.create(**validated_data)
        if starting_quantity > 0:
            create_manual_transaction(
                inventory_item_id=item.id,
                transaction_type=InventoryTransaction.Type.IN,
                quantity=starting_quantity,
                user=self.context["request"].user,
            )
        return item


class InventoryTransactionSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.CharField(source="inventory_item.name", read_only=True)
    inventory_unit = serializers.CharField(source="inventory_item.unit", read_only=True)
    order_id = serializers.IntegerField(source="order.id", read_only=True, allow_null=True)
    username = serializers.CharField(source="created_by.username", read_only=True, allow_null=True)

    class Meta:
        model = InventoryTransaction
        fields = [
            "id",
            "inventory_item",
            "inventory_item_name",
            "inventory_unit",
            "transaction_type",
            "source",
            "quantity",
            "order_id",
            "username",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "source",
            "order_id",
            "username",
            "created_at",
        ]

    def validate(self, attrs):
        item = attrs.get("inventory_item")
        transaction_type = attrs.get("transaction_type")
        quantity = attrs.get("quantity")
        if item is None:
            raise serializers.ValidationError({"inventory_item": "An inventory item is required."})
        if not can_manage_restaurant(self.context["request"].user, item.restaurant_id):
            raise serializers.ValidationError({"inventory_item": "You cannot manage this restaurant's inventory."})
        if transaction_type == InventoryTransaction.Type.REVERSAL:
            raise serializers.ValidationError({"transaction_type": "Order reversals are system-generated."})
        if transaction_type == InventoryTransaction.Type.ADJUSTMENT:
            if quantity == 0:
                raise serializers.ValidationError({"quantity": "Adjustment quantity cannot be zero."})
        elif quantity <= 0:
            raise serializers.ValidationError({"quantity": "Quantity must be greater than zero."})
        return attrs

    def create(self, validated_data):
        return create_manual_transaction(
            inventory_item_id=validated_data["inventory_item"].id,
            transaction_type=validated_data["transaction_type"],
            quantity=validated_data["quantity"],
            user=self.context["request"].user,
        )