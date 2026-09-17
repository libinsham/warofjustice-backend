from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

from apps.accounts.admin_urls import router as admin_users_router
from apps.analytics.urls import urlpatterns as analytics_urlpatterns
from apps.categories.urls import router as categories_router
from apps.comments.urls import (
    admin_router as admin_comments_router,
    public_router as public_comments_router,
)
from apps.core.urls import router as settings_router
from apps.media_lib.urls import (
    admin_router as admin_media_router,
    dashboard_router as dashboard_media_router,
)
from apps.posts.urls import (
    admin_router as admin_posts_router,
    dashboard_router as dashboard_posts_router,
    public_router as public_posts_router,
)
from apps.videos.urls import (
    admin_router as admin_videos_router,
    dashboard_router as dashboard_videos_router,
    webhook_urlpatterns as bunny_webhook_urls,
)


urlpatterns = [
    # =====================================================
    # DJANGO ADMIN
    # =====================================================

    path(
        "admin/",
        admin.site.urls,
    ),

    # =====================================================
    # AUTH / JWT / REGISTRATION
    # =====================================================

    path(
        "api/v1/auth/",
        include("apps.accounts.urls"),
    ),

    # =====================================================
    # PUBLIC APIs
    # Website + future Flutter app
    # =====================================================

    # E-Magazine APIs
    path(
        "api/v1/emagazines/",
        include("apps.emagazine.urls"),
    ),

    path(
        "api/v1/",
        include(public_posts_router.urls),
    ),

    path(
        "api/v1/",
        include(categories_router.urls),
    ),

    path(
        "api/v1/",
        include(public_comments_router.urls),
    ),

    path(
        "api/v1/",
        include(settings_router.urls),
    ),

    # =====================================================
    # AUTHOR / EDITOR DASHBOARD APIs
    # =====================================================

    path(
        "api/v1/dashboard/",
        include(dashboard_posts_router.urls),
    ),

    path(
        "api/v1/dashboard/",
        include(dashboard_media_router.urls),
    ),

    path(
        "api/v1/dashboard/",
        include(dashboard_videos_router.urls),
    ),

    # =====================================================
    # ADMIN / EDITOR / SUPER ADMIN APIs
    # =====================================================

    path(
        "api/v1/admin/",
        include(admin_posts_router.urls),
    ),

    path(
        "api/v1/admin/",
        include(admin_media_router.urls),
    ),

    path(
        "api/v1/admin/",
        include(admin_comments_router.urls),
    ),

    path(
        "api/v1/admin/",
        include(admin_videos_router.urls),
    ),

    path(
        "api/v1/admin/",
        include(analytics_urlpatterns),
    ),

    # =====================================================
    # SUPER ADMIN USER MANAGEMENT
    # =====================================================

    path(
        "api/v1/super-admin/",
        include(admin_users_router.urls),
    ),

    # =====================================================
    # BUNNY WEBHOOKS
    # Server-to-server
    # =====================================================

    path(
        "api/v1/",
        include(bunny_webhook_urls),
    ),

    # =====================================================
    # API DOCUMENTATION
    # =====================================================

    path(
        "api/v1/schema/",
        SpectacularAPIView.as_view(),
        name="schema",
    ),

    path(
        "api/v1/docs/",
        SpectacularSwaggerView.as_view(
            url_name="schema"
        ),
        name="swagger-ui",
    ),
]


# =========================================================
# LOCAL DEVELOPMENT MEDIA FILES
# =========================================================

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )