import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from restaurants.permissions import has_restaurant_access

from .services import restaurant_group_name


class RestaurantOrderConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not getattr(user, "is_authenticated", False):
            await self.close(code=1008)
            return

        restaurant_id = self.scope["url_route"]["kwargs"].get("restaurant_id")
        if restaurant_id is None:
            await self.close(code=1008)
            return

        restaurant_id = int(restaurant_id)
        if not await self._has_access(user, restaurant_id):
            await self.close(code=1008)
            return

        self.restaurant_id = restaurant_id
        self.group_name = restaurant_group_name(restaurant_id)

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name") and self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None:
            return

        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        if payload.get("type") == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))

    async def restaurant_order_event(self, event):
        await self.send(text_data=json.dumps(event["payload"]))

    @database_sync_to_async
    def _has_access(self, user, restaurant_id):
        return has_restaurant_access(user, restaurant_id)
