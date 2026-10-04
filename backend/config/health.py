import asyncio
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


logger = logging.getLogger(__name__)
CHANNEL_LAYER_TIMEOUT_SECONDS = 1


@require_GET
@never_cache
def live(request):
    return JsonResponse({"status": "ok"})


def database_ready():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone()[0] == 1
    except Exception as error:
        logger.warning("Readiness dependency unavailable: database (%s)", type(error).__name__)
        return False


async def _channel_layer_roundtrip(channel_layer):
    channel_name = await asyncio.wait_for(
        channel_layer.new_channel("healthcheck"),
        timeout=CHANNEL_LAYER_TIMEOUT_SECONDS,
    )
    await asyncio.wait_for(
        channel_layer.send(channel_name, {"type": "healthcheck.ping"}),
        timeout=CHANNEL_LAYER_TIMEOUT_SECONDS,
    )
    response = await asyncio.wait_for(
        channel_layer.receive(channel_name),
        timeout=CHANNEL_LAYER_TIMEOUT_SECONDS,
    )
    return response.get("type") == "healthcheck.ping"


def channel_layer_ready():
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return False
        if async_to_sync(_channel_layer_roundtrip)(channel_layer):
            return True
    except Exception as error:
        logger.warning("Readiness dependency unavailable: channel layer (%s)", type(error).__name__)
        return False

    logger.warning("Readiness dependency unavailable: channel layer")
    return False


@require_GET
@never_cache
def ready(request):
    dependencies = {
        "database": "ok" if database_ready() else "unavailable",
        "channel_layer": "ok" if channel_layer_ready() else "unavailable",
    }
    is_ready = all(value == "ok" for value in dependencies.values())
    return JsonResponse(
        {
            "status": "ok" if is_ready else "unavailable",
            "dependencies": dependencies,
        },
        status=200 if is_ready else 503,
    )