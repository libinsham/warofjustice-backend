from rest_framework.routers import DefaultRouter

from .views import AdminCommentViewSet, PublicCommentViewSet

public_router = DefaultRouter()
public_router.register("comments", PublicCommentViewSet, basename="public-comments")

admin_router = DefaultRouter()
admin_router.register("comments", AdminCommentViewSet, basename="admin-comments")
