from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class JWTAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "websocket":
            return await self.app(scope, receive, send)

        token = self._extract_token(scope)
        scope["user"] = AnonymousUser()

        if token:
            user = await self._get_user_from_token(token)
            if user is not None:
                scope["user"] = user

        return await self.app(scope, receive, send)

    def _extract_token(self, scope):
        for key, value in scope.get("headers", []):
            if key == b"authorization":
                auth_value = value.decode("latin-1").strip()
                if auth_value.lower().startswith("bearer "):
                    return auth_value.split(" ", 1)[1].strip()

        query = parse_qs(scope.get("query_string", b"").decode("utf-8"))
        for key in ("token", "ws_token"):
            values = query.get(key, [])
            if values:
                return values[0]
        return None

    @database_sync_to_async
    def _get_user_from_token(self, token):
        auth = JWTAuthentication()
        try:
            validated_token = auth.get_validated_token(token)
            user = auth.get_user(validated_token)
        except (InvalidToken, TokenError, TypeError, ValueError):
            return None

        if user is not None and getattr(user, "is_authenticated", False):
            return user
        return None


def JWTAuthMiddlewareStack(app):
    return JWTAuthMiddleware(app)
