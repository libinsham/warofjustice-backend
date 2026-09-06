from rest_framework.routers import DefaultRouter

from .views import SiteSettingsViewSet

router = DefaultRouter()
router.register("settings", SiteSettingsViewSet, basename="site-settings")
