"""
Read-only analytics endpoints. No dedicated Analytics models are needed
for this first pass — everything here is aggregated from existing Post/
User/Comment data, which is simpler and always consistent with the data
you're already looking at elsewhere in the admin panel. A dedicated
per-day PageView model would be the natural next step if you need
finer-grained traffic analytics later (this gives you per-post total
views and a published-per-day trend, not per-visit tracking).
"""
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.categories.models import Category
from apps.core.permissions import IsAdminOrEditor
from apps.posts.models import Post
from apps.videos.models import Video


class AnalyticsSummaryView(APIView):
    """
    GET /api/v1/admin/analytics/summary/
    Powers the admin dashboard's stat cards: total posts, published,
    pending, total authors, total views, total videos.
    """
    permission_classes = [IsAuthenticated, IsAdminOrEditor]

    def get(self, request):
        posts = Post.objects.all()
        return Response({
            "total_posts": posts.count(),
            "published_posts": posts.filter(status=Post.PUBLISHED).count(),
            "pending_posts": posts.filter(status__in=[Post.SUBMITTED, Post.UNDER_REVIEW]).count(),
            "draft_posts": posts.filter(status=Post.DRAFT).count(),
            "rejected_posts": posts.filter(status=Post.REJECTED).count(),
            "total_authors": User.objects.filter(role__name="author").count(),
            "total_views": posts.aggregate(total=Sum("views"))["total"] or 0,
            "total_videos": Video.objects.count(),
            "total_categories": Category.objects.count(),
        })


class TopPostsView(APIView):
    """GET /api/v1/admin/analytics/top-posts/?limit=10 — most-viewed published posts."""
    permission_classes = [IsAuthenticated, IsAdminOrEditor]

    def get(self, request):
        limit = min(int(request.query_params.get("limit", 10)), 50)
        posts = (
            Post.objects.filter(status=Post.PUBLISHED)
            .select_related("author", "category")
            .order_by("-views")[:limit]
        )
        return Response([
            {
                "id": p.id,
                "title": p.title,
                "slug": p.slug,
                "views": p.views,
                "author": p.author.username,
                "category": p.category.name if p.category else None,
                "published_at": p.published_at,
            }
            for p in posts
        ])


class CategoryBreakdownView(APIView):
    """GET /api/v1/admin/analytics/category-breakdown/ — published post count per category."""
    permission_classes = [IsAuthenticated, IsAdminOrEditor]

    def get(self, request):
        result = [
            {
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug,
                "post_count": cat.posts.filter(status=Post.PUBLISHED).count(),
            }
            for cat in Category.objects.all()
        ]
        return Response(result)


class PublishingTrendView(APIView):
    """
    GET /api/v1/admin/analytics/publishing-trend/?days=30
    Posts published per day over the given window — powers a simple line
    chart on the admin dashboard (spec's "Analytics chart placeholders").
    """
    permission_classes = [IsAuthenticated, IsAdminOrEditor]

    def get(self, request):
        days = min(int(request.query_params.get("days", 30)), 365)
        since = timezone.now() - timedelta(days=days)

        posts = (
            Post.objects.filter(status=Post.PUBLISHED, published_at__gte=since)
            .values_list("published_at", flat=True)
        )

        counts_by_day: dict[str, int] = {}
        for published_at in posts:
            day_key = published_at.date().isoformat()
            counts_by_day[day_key] = counts_by_day.get(day_key, 0) + 1

        # Fill in zero-count days so the frontend gets a continuous series.
        series = []
        for i in range(days, -1, -1):
            day = (timezone.now() - timedelta(days=i)).date().isoformat()
            series.append({"date": day, "count": counts_by_day.get(day, 0)})

        return Response(series)
