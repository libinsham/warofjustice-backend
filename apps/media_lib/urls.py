from rest_framework.routers import DefaultRouter

from .views import AdminMediaViewSet, MediaViewSet

dashboard_router = DefaultRouter()
dashboard_router.register("media", MediaViewSet, basename="dashboard-media")

admin_router = DefaultRouter()
admin_router.register("media", AdminMediaViewSet, basename="admin-media")
