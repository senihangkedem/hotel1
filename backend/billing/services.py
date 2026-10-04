from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError

from orders.models import Order, OrderItem
from realtime.services import emit_order_event
from restaurants.permissions import can_manage_restaurant

from .models import Bill, BillLine


CENT = Decimal("0.01")


class PaymentAlreadyRecorded(APIException):
    status_code = 409
    default_detail = "This bill has already been paid."
    default_code = "bill_already_paid"


def money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_bill(*, subtotal, discount_type, discount_value, tax_rate, service_charge_rate):
    subtotal = money(subtotal)
    discount_value = Decimal(discount_value)
    tax_rate = Decimal(tax_rate)
    service_charge_rate = Decimal(service_charge_rate)

    if subtotal < 0:
        raise ValidationError({"subtotal": "Subtotal cannot be negative."})
    if discount_value < 0:
        raise ValidationError({"discount_value": "Discount cannot be negative."})
    if not Decimal("0") <= tax_rate <= Decimal("100"):
        raise ValidationError({"tax_rate": "Tax rate must be between 0 and 100."})
    if not Decimal("0") <= service_charge_rate <= Decimal("100"):
        raise ValidationError({"service_charge_rate": "Service charge rate must be between 0 and 100."})

    if discount_type == Bill.DiscountType.NONE:
        if discount_value != 0:
            raise ValidationError({"discount_value": "A bill without a discount must use a zero discount value."})
        discount_amount = Decimal("0.00")
    elif discount_type == Bill.DiscountType.PERCENTAGE:
        if discount_value > 100:
            raise ValidationError({"discount_value": "Percentage discount cannot exceed 100."})
        discount_amount = money(subtotal * discount_value / Decimal("100"))
    elif discount_type == Bill.DiscountType.FIXED:
        if discount_value > subtotal:
            raise ValidationError({"discount_value": "Fixed discount cannot exceed the subtotal."})
        discount_amount = money(discount_value)
    else:
        raise ValidationError({"discount_type": "Unsupported discount type."})

    discounted_subtotal = subtotal - discount_amount
    tax_amount = money(discounted_subtotal * tax_rate / Decimal("100"))
    service_charge_amount = money(discounted_subtotal * service_charge_rate / Decimal("100"))
    total_amount = money(discounted_subtotal + tax_amount + service_charge_amount)
    if total_amount < 0:
        raise ValidationError({"total_amount": "Bill total cannot be negative."})

    return {
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "tax_rate": tax_rate,
        "tax_amount": tax_amount,
        "service_charge_rate": service_charge_rate,
        "service_charge_amount": service_charge_amount,
        "total_amount": total_amount,
    }


@transaction.atomic
def create_bill(*, order_id, discount_type, discount_value, user):
    order = Order.objects.select_for_update().select_related("restaurant").get(id=order_id)
    if not can_manage_restaurant(user, order.restaurant_id):
        raise ValidationError({"order": "You cannot bill orders for this restaurant."})
    if order.status == Order.Status.CANCELLED:
        raise ValidationError({"order": "Cancelled orders cannot be billed."})
    if order.payment_status == Order.PaymentStatus.PAID:
        raise ValidationError({"order": "This order is already marked paid and cannot receive a new bill."})
    if Bill.objects.filter(order=order).exists():
        raise ValidationError({"order": "A bill already exists for this order."})

    order_items = list(
        OrderItem.objects.select_for_update()
        .filter(order=order)
        .select_related("menu_item")
        .order_by("id")
    )
    if not order_items:
        raise ValidationError({"order": "Orders without items cannot be billed."})

    amounts = calculate_bill(
        subtotal=order.total_amount,
        discount_type=discount_type,
        discount_value=discount_value,
        tax_rate=order.restaurant.tax_rate,
        service_charge_rate=order.restaurant.service_charge_rate,
    )
    bill = Bill.objects.create(
        order=order,
        restaurant=order.restaurant,
        discount_type=discount_type,
        discount_value=discount_value,
        created_by=user,
        **amounts,
    )
    BillLine.objects.bulk_create([
        BillLine(
            bill=bill,
            order_item=item,
            item_name=item.menu_item.name,
            quantity=item.quantity,
            unit_price=item.unit_price,
            subtotal=item.subtotal,
        )
        for item in order_items
    ])
    return bill


@transaction.atomic
def update_unpaid_bill_discount(*, bill_id, discount_type, discount_value, user):
    bill = Bill.objects.select_for_update().select_related("restaurant", "order").get(id=bill_id)
    if not can_manage_restaurant(user, bill.restaurant_id):
        raise ValidationError({"bill": "You cannot manage this restaurant's bills."})
    if bill.payment_status == Order.PaymentStatus.PAID:
        raise ValidationError({"bill": "Paid bills are immutable."})

    amounts = calculate_bill(
        subtotal=bill.subtotal,
        discount_type=discount_type,
        discount_value=discount_value,
        tax_rate=bill.tax_rate,
        service_charge_rate=bill.service_charge_rate,
    )
    for field, value in amounts.items():
        setattr(bill, field, value)
    bill.discount_type = discount_type
    bill.discount_value = discount_value
    bill.save(update_fields=[*amounts.keys(), "discount_type", "discount_value", "updated_at"])
    return bill


@transaction.atomic
def mark_bill_paid(*, bill_id, payment_method, user):
    bill = Bill.objects.select_for_update().select_related("restaurant", "order").get(id=bill_id)
    if not can_manage_restaurant(user, bill.restaurant_id):
        raise ValidationError({"bill": "You cannot take payment for this restaurant."})
    if bill.payment_status == Order.PaymentStatus.PAID or bill.order.payment_status == Order.PaymentStatus.PAID:
        raise PaymentAlreadyRecorded()

    bill.payment_status = Order.PaymentStatus.PAID
    bill.payment_method = payment_method
    bill.paid_at = django_timezone_now()
    bill.paid_by = user
    bill.save(update_fields=["payment_status", "payment_method", "paid_at", "paid_by", "updated_at"])

    order = Order.objects.select_for_update().get(id=bill.order_id)
    if order.payment_status == Order.PaymentStatus.PAID:
        raise PaymentAlreadyRecorded()
    order.payment_status = Order.PaymentStatus.PAID
    order.save(update_fields=["payment_status", "updated_at"])
    emit_order_event(
        order,
        "order.payment_status_changed",
        status=order.status,
        payment_status=order.payment_status,
    )
    return bill


def django_timezone_now():
    from django.utils import timezone

    return timezone.now()
