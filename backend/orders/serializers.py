from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(
        source="menu_item.name",
        read_only=True,
    )
    quantity = serializers.IntegerField(min_value=1)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "menu_item",
            "menu_item_name",
            "quantity",
            "unit_price",
            "subtotal",
            "notes",
        ]

        read_only_fields = [
            "unit_price",
            "subtotal",
        ]

    def validate(self, attrs):
        menu_item = attrs.get("menu_item", getattr(self.instance, "menu_item", None))
        quantity = attrs.get("quantity", getattr(self.instance, "quantity", 1))

        if menu_item is None:
            raise serializers.ValidationError({
                "menu_item": "A menu item is required.",
            })

        if quantity < 1:
            raise serializers.ValidationError({
                "quantity": "Quantity must be at least 1.",
            })

        if not menu_item.is_available:
            raise serializers.ValidationError({
                "menu_item": "This menu item is currently unavailable.",
            })

        return attrs


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "restaurant",
            "table",
            "customer",
            "status",
            "payment_status",
            "customer_name",
            "customer_phone",
            "notes",
            "total_amount",
            "items",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "customer",
            "status",
            "payment_status",
            "total_amount",
        ]

    def _validate_items(self, restaurant, items):
        if not items:
            raise serializers.ValidationError({
                "items": "An order must include at least one item.",
            })

        for item_data in items:
            menu_item = item_data.get("menu_item")
            quantity = item_data.get("quantity", 1)

            if menu_item is None:
                raise serializers.ValidationError({
                    "items": "Each order item must include a menu item.",
                })

            if quantity < 1:
                raise serializers.ValidationError({
                    "items": "Each item quantity must be at least 1.",
                })

            if menu_item.restaurant_id != restaurant.id:
                raise serializers.ValidationError({
                    "items": "Each menu item must belong to the selected restaurant.",
                })

            if not menu_item.is_available:
                raise serializers.ValidationError({
                    "items": "One or more selected menu items are unavailable.",
                })

    def validate(self, attrs):
        restaurant = attrs.get(
            "restaurant",
            getattr(self.instance, "restaurant", None),
        )
        table = attrs.get(
            "table",
            getattr(self.instance, "table", None),
        )
        items = attrs.get("items", getattr(self.instance, "items", None))

        if restaurant is None:
            raise serializers.ValidationError({
                "restaurant": "A restaurant is required.",
            })

        if table is not None and table.restaurant_id != restaurant.id:
            raise serializers.ValidationError({
                "table": "Table must belong to the selected restaurant.",
            })

        if items is not None:
            self._validate_items(restaurant, items)

        return attrs

    def update(self, instance, validated_data):
        blocked_fields = {"restaurant", "customer", "status", "payment_status", "total_amount"}
        invalid_fields = sorted(set(validated_data).intersection(blocked_fields))
        if invalid_fields:
            raise serializers.ValidationError({
                field: "This field cannot be modified directly." for field in invalid_fields
            })
        return super().update(instance, validated_data)

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        validated_data.pop("customer", None)
        restaurant = validated_data["restaurant"]

        with transaction.atomic():
            order = Order.objects.create(
                customer=self.context["request"].user,
                **validated_data,
            )

            total = Decimal("0.00")

            for item_data in items_data:
                menu_item = item_data["menu_item"]
                quantity = item_data["quantity"]

                if menu_item.restaurant_id != restaurant.id:
                    raise serializers.ValidationError({
                        "items": "Each menu item must belong to the selected restaurant.",
                    })

                if not menu_item.is_available:
                    raise serializers.ValidationError({
                        "items": "One or more selected menu items are unavailable.",
                    })

                if quantity < 1:
                    raise serializers.ValidationError({
                        "items": "Each item quantity must be at least 1.",
                    })

                unit_price = menu_item.price
                subtotal = unit_price * quantity

                OrderItem.objects.create(
                    order=order,
                    menu_item=menu_item,
                    quantity=quantity,
                    unit_price=unit_price,
                    subtotal=subtotal,
                    notes=item_data.get("notes", ""),
                )

                total += subtotal

            order.total_amount = total
            order.save(update_fields=["total_amount"])
            return order


class OrderTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)