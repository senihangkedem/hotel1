from rest_framework import serializers
from restaurants.permissions import can_manage_restaurant, has_restaurant_access
from inventory.units import convert_quantity

from .models import Category, MenuItem, MenuItemIngredient


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id",
            "restaurant",
            "name",
            "description",
            "is_active",
            "created_at",
        ]

    def validate(self, attrs):
        restaurant = attrs.get(
            "restaurant",
            self.instance.restaurant if self.instance else None,
        )
        user = self.context["request"].user

        if restaurant is None:
            raise serializers.ValidationError({
                "restaurant": "A restaurant is required.",
            })

        if not can_manage_restaurant(user, restaurant.id):
            raise serializers.ValidationError({
            "restaurant": "You can only manage categories in restaurants you own or manage.",
            })

        return attrs


class MenuItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(
        source="category.name",
        read_only=True
    )
    price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
    )

    class Meta:
        model = MenuItem
        fields = [
            "id",
            "restaurant",
            "category",
            "category_name",
            "name",
            "description",
            "price",
            "image",
            "is_available",
            "is_featured",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Name cannot be empty.")
        return value

    def validate(self, attrs):
        current_restaurant = (
            self.instance.restaurant if self.instance else None
        )
        restaurant = attrs.get("restaurant", current_restaurant)
        category = attrs.get(
            "category",
            self.instance.category if self.instance else None,
        )
        user = self.context["request"].user

        if restaurant is None:
            raise serializers.ValidationError({
                "restaurant": "A restaurant is required.",
            })

        if not can_manage_restaurant(user, restaurant.id):
            raise serializers.ValidationError({
            "restaurant": "You can only manage menu items in restaurants you own or manage.",
            })

        if category is not None and category.restaurant_id != restaurant.id:
            raise serializers.ValidationError({
                "category": "Category must belong to the selected restaurant.",
            })

        return attrs


class MenuItemIngredientSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.CharField(source="inventory_item.name", read_only=True)
    inventory_unit = serializers.CharField(source="inventory_item.unit", read_only=True)
    menu_item_name = serializers.CharField(source="menu_item.name", read_only=True)

    class Meta:
        model = MenuItemIngredient
        fields = [
            "id",
            "menu_item",
            "menu_item_name",
            "inventory_item",
            "inventory_item_name",
            "inventory_unit",
            "quantity_required",
            "unit",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "menu_item_name",
            "inventory_item_name",
            "inventory_unit",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        menu_item = attrs.get("menu_item", getattr(self.instance, "menu_item", None))
        inventory_item = attrs.get(
            "inventory_item",
            getattr(self.instance, "inventory_item", None),
        )
        quantity = attrs.get("quantity_required", getattr(self.instance, "quantity_required", None))
        unit = attrs.get("unit", getattr(self.instance, "unit", None))

        if menu_item is None or inventory_item is None:
            raise serializers.ValidationError("A menu item and inventory item are required.")
        user = self.context["request"].user
        if not has_restaurant_access(user, menu_item.restaurant_id):
            raise serializers.ValidationError({
                "menu_item": "You do not have access to this restaurant's recipe.",
            })
        if not can_manage_restaurant(user, menu_item.restaurant_id):
            raise serializers.ValidationError({
                "menu_item": "Only restaurant owners and managers can modify recipes.",
            })
        if menu_item.restaurant_id != inventory_item.restaurant_id:
            raise serializers.ValidationError({
                "inventory_item": "Menu item and inventory item must belong to the same restaurant.",
            })
        if quantity is None or quantity <= 0:
            raise serializers.ValidationError({
                "quantity_required": "Recipe quantity must be greater than zero.",
            })

        try:
            convert_quantity(quantity, unit, inventory_item.unit)
        except (KeyError, TypeError):
            raise serializers.ValidationError({"unit": "Recipe unit is not supported."})
        return attrs