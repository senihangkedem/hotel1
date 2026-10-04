from django.urls import path

from .consumers import RestaurantOrderConsumer

websocket_urlpatterns = [
    path("ws/restaurants/<int:restaurant_id>/", RestaurantOrderConsumer.as_asgi()),
]
