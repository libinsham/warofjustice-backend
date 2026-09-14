from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, TagViewSet

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="categories")
router.register("tags", TagViewSet, basename="tags")
