from django.urls import path

from .views import AnalyticsSummaryView, CategoryBreakdownView, PublishingTrendView, TopPostsView

urlpatterns = [
    path("analytics/summary/", AnalyticsSummaryView.as_view(), name="analytics-summary"),
    path("analytics/top-posts/", TopPostsView.as_view(), name="analytics-top-posts"),
    path("analytics/category-breakdown/", CategoryBreakdownView.as_view(), name="analytics-category-breakdown"),
    path("analytics/publishing-trend/", PublishingTrendView.as_view(), name="analytics-publishing-trend"),
]
