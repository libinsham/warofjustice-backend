from rest_framework.routers import DefaultRouter

from .views import AdminPostViewSet, DashboardPostViewSet, PhotoGalleryViewSet, PublicPostViewSet, PublicVideoViewSet

public_router = DefaultRouter()
public_router.register("posts", PublicPostViewSet, basename="public-posts")
public_router.register("videos", PublicVideoViewSet, basename="public-videos")
public_router.register("gallery", PhotoGalleryViewSet, basename="public-gallery")

dashboard_router = DefaultRouter()
dashboard_router.register("posts", DashboardPostViewSet, basename="dashboard-posts")

admin_router = DefaultRouter()
admin_router.register("posts", AdminPostViewSet, basename="admin-posts")
