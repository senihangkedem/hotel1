from rest_framework.routers import DefaultRouter

from .views import InventoryItemViewSet, InventoryTransactionViewSet


router = DefaultRouter()
router.register("items", InventoryItemViewSet, basename="inventory-item")
router.register("transactions", InventoryTransactionViewSet, basename="inventory-transaction")

urlpatterns = router.urls