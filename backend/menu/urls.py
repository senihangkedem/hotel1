from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, MenuItemIngredientViewSet, MenuItemViewSet

router = DefaultRouter()

router.register(
    "categories",
    CategoryViewSet,
    basename="category"
)

router.register(
    "items",
    MenuItemViewSet,
    basename="menu-item"
)

router.register(
    "recipes",
    MenuItemIngredientViewSet,
    basename="menu-item-ingredient"
)

urlpatterns = router.urls
