from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from menu.models import MenuItemIngredient

from .models import InventoryItem, InventoryTransaction
from .units import convert_quantity


@transaction.atomic
def create_manual_transaction(*, inventory_item_id, transaction_type, quantity, user):
    if transaction_type not in {
        InventoryTransaction.Type.IN,
        InventoryTransaction.Type.OUT,
        InventoryTransaction.Type.ADJUSTMENT,
    }:
        raise ValidationError({"transaction_type": "Only manual IN, OUT, and ADJUSTMENT entries are allowed."})

    item = InventoryItem.objects.select_for_update().get(id=inventory_item_id)
    if transaction_type == InventoryTransaction.Type.ADJUSTMENT:
        next_quantity = item.quantity_on_hand + quantity
    elif transaction_type == InventoryTransaction.Type.IN:
        if quantity <= 0:
            raise ValidationError({"quantity": "Stock-in quantity must be greater than zero."})
        next_quantity = item.quantity_on_hand + quantity
    else:
        if quantity <= 0:
            raise ValidationError({"quantity": "Stock-out quantity must be greater than zero."})
        next_quantity = item.quantity_on_hand - quantity

    if next_quantity < 0:
        raise ValidationError({"quantity": "Insufficient inventory; stock cannot become negative."})

    item.quantity_on_hand = next_quantity
    item.save(update_fields=["quantity_on_hand", "updated_at"])
    return InventoryTransaction.objects.create(
        inventory_item=item,
        transaction_type=transaction_type,
        source=InventoryTransaction.Source.MANUAL,
        quantity=quantity,
        created_by=user,
    )


def _order_consumption(order):
    consumption = defaultdict(lambda: Decimal("0"))
    items = order.items.select_related("menu_item").prefetch_related(
        "menu_item__recipe_ingredients__inventory_item",
    )
    for order_item in items:
        for recipe_line in order_item.menu_item.recipe_ingredients.all():
            required = convert_quantity(
                recipe_line.quantity_required * order_item.quantity,
                recipe_line.unit,
                recipe_line.inventory_item.unit,
            )
            consumption[recipe_line.inventory_item_id] += required
    return consumption


@transaction.atomic
def deduct_order_inventory(order, user):
    consumption = _order_consumption(order)
    if not consumption:
        return

    items = list(
        InventoryItem.objects.select_for_update()
        .filter(id__in=consumption)
        .order_by("id")
    )
    by_id = {item.id: item for item in items}

    for item_id, required in consumption.items():
        item = by_id[item_id]
        if item.quantity_on_hand < required:
            raise ValidationError({
                "inventory": f"Insufficient {item.name}: need {required} {item.unit}, have {item.quantity_on_hand} {item.unit}.",
            })

    for item_id, required in consumption.items():
        item = by_id[item_id]
        item.quantity_on_hand -= required
        item.save(update_fields=["quantity_on_hand", "updated_at"])
        InventoryTransaction.objects.create(
            inventory_item=item,
            transaction_type=InventoryTransaction.Type.OUT,
            source=InventoryTransaction.Source.ORDER,
            quantity=required,
            order=order,
            created_by=user,
        )


@transaction.atomic
def reverse_order_inventory(order, user):
    outgoing = list(
        InventoryTransaction.objects.select_for_update()
        .filter(
            order=order,
            source=InventoryTransaction.Source.ORDER,
            transaction_type=InventoryTransaction.Type.OUT,
        )
        .select_related("inventory_item")
        .order_by("inventory_item_id")
    )
    if not outgoing:
        return

    item_ids = [entry.inventory_item_id for entry in outgoing]
    items = {
        item.id: item
        for item in InventoryItem.objects.select_for_update().filter(id__in=item_ids).order_by("id")
    }
    reversed_ids = set(
        InventoryTransaction.objects.filter(
            order=order,
            transaction_type=InventoryTransaction.Type.REVERSAL,
        ).values_list("inventory_item_id", flat=True)
    )

    for entry in outgoing:
        if entry.inventory_item_id in reversed_ids:
            continue
        item = items[entry.inventory_item_id]
        item.quantity_on_hand += entry.quantity
        item.save(update_fields=["quantity_on_hand", "updated_at"])
        InventoryTransaction.objects.create(
            inventory_item=item,
            transaction_type=InventoryTransaction.Type.REVERSAL,
            source=InventoryTransaction.Source.ORDER,
            quantity=entry.quantity,
            order=order,
            created_by=user,
        )


@transaction.atomic
def transition_order_status(order_id, target_status, user):
    from orders.models import Order

    order = Order.objects.select_for_update().get(id=order_id)
    if order.status == target_status:
        return order

    transitions = {
        Order.Status.PENDING: {Order.Status.CONFIRMED, Order.Status.CANCELLED},
        Order.Status.CONFIRMED: {Order.Status.PREPARING, Order.Status.CANCELLED},
        Order.Status.PREPARING: {Order.Status.READY, Order.Status.CANCELLED},
        Order.Status.READY: {Order.Status.SERVED},
        Order.Status.SERVED: {Order.Status.COMPLETED},
    }
    if target_status not in transitions.get(order.status, set()):
        raise ValidationError({"status": f"Cannot transition an order from {order.status} to {target_status}."})

    if target_status == Order.Status.CANCELLED and order.payment_status == Order.PaymentStatus.PAID:
        raise ValidationError({"status": "Paid orders cannot be cancelled without a refund workflow."})

    if target_status == Order.Status.PREPARING:
        deduct_order_inventory(order, user)
    elif target_status == Order.Status.CANCELLED:
        reverse_order_inventory(order, user)

    order.status = target_status
    order.save(update_fields=["status", "updated_at"])
    return order