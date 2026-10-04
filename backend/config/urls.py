from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from config.health import live, ready
from user_accounts.throttles import LoginRateThrottle


urlpatterns = [
    path("health/", live, name="health-live"),
    path("ready/", ready, name="health-ready"),
    path("admin/", admin.site.urls),

    path(
        "api/auth/token/",
        TokenObtainPairView.as_view(throttle_classes=[LoginRateThrottle]),
        name="token_obtain_pair",
    ),

    path(
        "api/auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),

    path(
        "api/auth/",
        include("user_accounts.urls"),
    ),

    path(
        "api/restaurants/",
        include("restaurants.urls"),
    ),

    path(
        "api/menu/",
        include("menu.urls"),
    ),

    path(
        "api/orders/",
        include("orders.urls"),
    ),

    path(
        "api/inventory/",
        include("inventory.urls"),
    ),

    path(
        "api/billing/",
        include("billing.urls"),
    ),

    path(
        "api/analytics/",
        include("analytics.urls"),
    ),
]