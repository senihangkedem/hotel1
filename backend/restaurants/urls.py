from rest_framework.routers import DefaultRouter
from .views import RestaurantStaffViewSet, RestaurantTableViewSet, RestaurantViewSet

router = DefaultRouter()

router.register(
    "restaurants",
    RestaurantViewSet,
    basename="restaurant"
)

router.register(
    "tables",
    RestaurantTableViewSet,
    basename="table"
)

router.register(
    "staff",
    RestaurantStaffViewSet,
    basename="restaurant-staff"
)

urlpatterns = router.urls
