from datetime import timedelta

from django.shortcuts import render

# Create your views here.

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = request.user.restaurant_memberships.filter(
            is_active=True,
        ).select_related("restaurant")

        return Response({
            "id": request.user.id,
            "username": request.user.username,
            "email": request.user.email,
            "role": request.user.role,
            "is_superuser": request.user.is_superuser,
            "staff_memberships": [
                {
                    "restaurant": membership.restaurant_id,
                    "restaurant_name": membership.restaurant.name,
                    "role": membership.role,
                }
                for membership in memberships
            ],
        })


class WebSocketTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        token = AccessToken.for_user(request.user)
        token.set_exp(lifetime=timedelta(minutes=1))
        return Response({"token": str(token)})