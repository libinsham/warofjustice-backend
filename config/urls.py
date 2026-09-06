from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.accounts.admin_urls import router as admin_users_router
from apps.analytics.urls import urlpatterns as analytics_urlpatterns
from apps.categories.urls import router as categories_router
from apps.comments.urls import admin_router as admin_comments_router
from apps.comments.urls import public_router as public_comments_router
from apps.core.urls import router as settings_router
from apps.media_lib.urls import admin_router as admin_media_router
from apps.media_lib.urls import dashboard_router as dashboard_media_router
from apps.posts.urls import admin_router as admin_posts_router
from apps.posts.urls import dashboard_router as dashboard_posts_router
from apps.posts.urls import public_router as public_posts_router
from apps.videos.urls import admin_router as admin_videos_router
from apps.videos.urls import dashboard_router as dashboard_videos_router
from apps.videos.urls import webhook_urlpatterns as bunny_webhook_urls

urlpatterns = [
    path("admin/", admin.site.urls),

    # ---- Auth (JWT) ----
    path("api/v1/auth/", include("apps.accounts.urls")),

    # ---- Public, read-only (website + Flutter) ----
    path("api/v1/", include(public_posts_router.urls)),
    path("api/v1/", include(categories_router.urls)),
    path("api/v1/", include(public_comments_router.urls)),
    path("api/v1/", include(settings_router.urls)),

    # ---- Author/Editor dashboard (own content, submit for review, uploads) ----
    path("api/v1/dashboard/", include(dashboard_posts_router.urls)),
    path("api/v1/dashboard/", include(dashboard_media_router.urls)),
    path("api/v1/dashboard/", include(dashboard_videos_router.urls)),

    # ---- Admin/Editor/Super Admin (approval workflow, moderation, media library) ----
    path("api/v1/admin/", include(admin_posts_router.urls)),
    path("api/v1/admin/", include(admin_media_router.urls)),
    path("api/v1/admin/", include(admin_comments_router.urls)),
    path("api/v1/admin/", include(admin_videos_router.urls)),
    path("api/v1/admin/", include(analytics_urlpatterns)),

    # ---- Super Admin only (user management) ----
    path("api/v1/super-admin/", include(admin_users_router.urls)),

    # ---- Webhooks (server-to-server, not user-authenticated) ----
    path("api/v1/", include(bunny_webhook_urls)),

    # ---- API docs ----
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
