from django.urls import path

from .views import (
    MagazineListCreateView,
    MagazineDetailView,
)


urlpatterns = [
    path(
        "",
        MagazineListCreateView.as_view(),
        name="magazine-list-create",
    ),
    path(
        "<int:pk>/",
        MagazineDetailView.as_view(),
        name="magazine-detail",
    ),
]