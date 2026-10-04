from rest_framework import serializers

from orders.models import Order
from restaurants.models import Restaurant
from restaurants.permissions import can_manage_restaurant

from .models import Bill, BillLine
from .services import create_bill, update_unpaid_bill_discount


class BillLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillLine
        fields = ["id", "item_name", "quantity", "unit_price", "subtotal"]
        read_only_fields = fields


class BillSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source="restaurant.name", read_only=True)
    restaurant_address = serializers.CharField(source="restaurant.address", read_only=True)
    restaurant_phone = serializers.CharField(source="restaurant.phone", read_only=True)
    order_table_number = serializers.IntegerField(source="order.table.table_number", read_only=True, allow_null=True)
    lines = BillLineSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True, allow_null=True)
    paid_by_name = serializers.CharField(source="paid_by.username", read_only=True, allow_null=True)

    class Meta:
        model = Bill
        fields = [
            "id",
            "order",
            "restaurant",
            "restaurant_name",
            "restaurant_address",
            "restaurant_phone",
            "order_table_number",
            "subtotal",
            "discount_type",
            "discount_value",
            "discount_amount",
            "tax_rate",
            "tax_amount",
            "service_charge_rate",
            "service_charge_amount",
            "total_amount",
            "payment_status",
            "payment_method",
            "issued_at",
            "paid_at",
            "updated_at",
            "created_by_name",
            "paid_by_name",
            "lines",
        ]
        read_only_fields = [
            "id",
            "order",
            "restaurant",
            "subtotal",
            "discount_amount",
            "tax_rate",
            "tax_amount",
            "service_charge_rate",
            "service_charge_amount",
            "total_amount",
            "payment_status",
            "payment_method",
            "issued_at",
            "paid_at",
            "updated_at",
            "created_by_name",
            "paid_by_name",
            "lines",
        ]

    def update(self, instance, validated_data):
        return update_unpaid_bill_discount(
            bill_id=instance.id,
            discount_type=validated_data.get("discount_type", instance.discount_type),
            discount_value=validated_data.get("discount_value", instance.discount_value),
            user=self.context["request"].user,
        )


class BillCreateSerializer(serializers.Serializer):
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all())
    discount_type = serializers.ChoiceField(
        choices=Bill.DiscountType.choices,
        default=Bill.DiscountType.NONE,
    )
    discount_value = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        default=0,
    )

    def validate_order(self, order):
        if not can_manage_restaurant(self.context["request"].user, order.restaurant_id):
            raise serializers.ValidationError("You cannot create bills for this restaurant.")
        return order

    def create(self, validated_data):
        bill = create_bill(
            order_id=validated_data["order"].id,
            discount_type=validated_data["discount_type"],
            discount_value=validated_data["discount_value"],
            user=self.context["request"].user,
        )
        return bill

    def to_representation(self, instance):
        return BillSerializer(instance, context=self.context).data


class BillPaymentSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(choices=Bill.PaymentMethod.choices)


class RestaurantBillingSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = ["id", "name", "tax_rate", "service_charge_rate"]
        read_only_fields = ["id", "name"]

    def validate_tax_rate(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Tax rate must be between 0 and 100.")
        return value

    def validate_service_charge_rate(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Service charge rate must be between 0 and 100.")
        return value
