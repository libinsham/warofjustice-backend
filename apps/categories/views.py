from rest_framework import viewsets

from apps.core.permissions import IsAdminOrEditor

from .models import Category, Tag
from .serializers import CategorySerializer, TagSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    """
    GET is public (used by the website's nav + category pages).
    Write actions require Admin/Editor/Super Admin — categories.manage.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return []
        return [IsAdminOrEditor()]


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return []
        return [IsAdminOrEditor()]
