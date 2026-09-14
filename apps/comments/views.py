from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import IsAdminOrEditor

from .models import Comment
from .serializers import CommentCreateSerializer, CommentSerializer, ModerateCommentSerializer


class PublicCommentViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    GET  /api/v1/comments/?post=<id>   - approved comments only, public
    POST /api/v1/comments/             - logged-in readers can comment;
                                          starts 'pending' until moderated
    """
    def get_permissions(self):
        return [AllowAny()] if self.action == "list" else [IsAuthenticated()]

    def get_serializer_class(self):
        return CommentCreateSerializer if self.action == "create" else CommentSerializer

    def get_queryset(self):
        qs = Comment.objects.filter(status=Comment.APPROVED).select_related("user")
        if post_id := self.request.query_params.get("post"):
            qs = qs.filter(post_id=post_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, status=Comment.PENDING)


class AdminCommentViewSet(viewsets.ModelViewSet):
    """Moderation queue for Admin/Editor/Super Admin — comments.moderate."""
    permission_classes = [IsAuthenticated, IsAdminOrEditor]
    serializer_class = CommentSerializer
    queryset = Comment.objects.select_related("user", "post").all()

    def get_queryset(self):
        qs = super().get_queryset()
        if status_filter := self.request.query_params.get("status"):
            qs = qs.filter(status=status_filter)
        return qs

    @action(detail=True, methods=["post"])
    def moderate(self, request, pk=None):
        comment = self.get_object()
        serializer = ModerateCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment.status = serializer.validated_data["status"]
        comment.save(update_fields=["status"])
        return Response(CommentSerializer(comment).data)
