from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BillViewSet, RestaurantBillingSettingsView


router = DefaultRouter()
router.register("bills", BillViewSet, basename="bill")

urlpatterns = [
    path("settings/<int:restaurant_id>/", RestaurantBillingSettingsView.as_view(), name="restaurant-billing-settings"),
    path("", include(router.urls)),
]
