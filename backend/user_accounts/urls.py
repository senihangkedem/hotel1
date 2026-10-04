
from django.urls import path
from .views import CurrentUserView, WebSocketTokenView


urlpatterns = [
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path("ws-token/", WebSocketTokenView.as_view(), name="websocket-token"),
]

