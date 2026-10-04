from rest_framework.routers import DefaultRouter

from .views import OrderViewSet, OrderItemViewSet


router = DefaultRouter()

router.register(
    "orders",
    OrderViewSet,
    basename="order",
)

router.register(
    "items",
    OrderItemViewSet,
    basename="order-item",
)


urlpatterns = router.urls
