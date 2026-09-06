from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AdminVideoViewSet, BunnyWebhookView, VideoViewSet

dashboard_router = DefaultRouter()
dashboard_router.register("videos", VideoViewSet, basename="dashboard-videos")

admin_router = DefaultRouter()
admin_router.register("videos", AdminVideoViewSet, basename="admin-videos")

webhook_urlpatterns = [
    path("webhooks/bunny/", BunnyWebhookView.as_view(), name="bunny-webhook"),
]
