from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction


def restaurant_group_name(restaurant_id):
    return f"restaurant_orders_{restaurant_id}"


def emit_order_event(order, event_type, **extra):
    payload = {
        "event": event_type,
        "order_id": order.id,
        "restaurant_id": order.restaurant_id,
        "timestamp": timezone.now().isoformat(),
    }
    payload.update(extra)

    def send_event():
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        async_to_sync(channel_layer.group_send)(
            restaurant_group_name(order.restaurant_id),
            {
                "type": "restaurant_order_event",
                "payload": payload,
            },
        )

    transaction.on_commit(send_event)
