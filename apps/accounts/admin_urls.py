from rest_framework.routers import DefaultRouter

from .admin_views import AdminUserViewSet

router = DefaultRouter()
router.register("users", AdminUserViewSet, basename="admin-users")
