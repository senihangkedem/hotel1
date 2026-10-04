from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from orders.models import Order


class Bill(models.Model):
    class DiscountType(models.TextChoices):
        NONE = "NONE", "No discount"
        PERCENTAGE = "PERCENTAGE", "Percentage"
        FIXED = "FIXED", "Fixed amount"

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Cash"
        CARD = "CARD", "Card"
        BANK_TRANSFER = "BANK_TRANSFER", "Bank transfer"
        QR = "QR", "QR"
        OTHER = "OTHER", "Other"

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="bill",
    )
    restaurant = models.ForeignKey(
        "restaurants.Restaurant",
        on_delete=models.PROTECT,
        related_name="bills",
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount_type = models.CharField(
        max_length=12,
        choices=DiscountType.choices,
        default=DiscountType.NONE,
    )
    discount_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    service_charge_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    service_charge_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_status = models.CharField(
        max_length=10,
        choices=Order.PaymentStatus.choices,
        default=Order.PaymentStatus.UNPAID,
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        blank=True,
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_bills",
        null=True,
        blank=True,
    )
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="paid_bills",
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issued_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(subtotal__gte=0), name="bill_subtotal_nonnegative"),
            models.CheckConstraint(condition=models.Q(discount_amount__gte=0), name="bill_discount_nonnegative"),
            models.CheckConstraint(condition=models.Q(tax_amount__gte=0), name="bill_tax_nonnegative"),
            models.CheckConstraint(condition=models.Q(service_charge_amount__gte=0), name="bill_service_nonnegative"),
            models.CheckConstraint(condition=models.Q(total_amount__gte=0), name="bill_total_nonnegative"),
        ]

    def __str__(self):
        return f"Bill #{self.pk} for Order #{self.order_id}"


class BillLine(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="lines")
    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete=models.PROTECT,
        related_name="bill_lines",
    )
    item_name = models.CharField(max_length=150)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["bill", "order_item"], name="unique_bill_order_item_line"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="bill_line_quantity_positive"),
            models.CheckConstraint(condition=models.Q(subtotal__gte=0), name="bill_line_subtotal_nonnegative"),
        ]

    def __str__(self):
        return f"{self.item_name} x {self.quantity}"
