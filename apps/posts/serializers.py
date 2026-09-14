from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from apps.categories.models import Category, Tag
from apps.videos.models import Video

from .models import Post, PostApproval, PostRevision


class CategoryMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class TagMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]


class VideoMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ["id", "title", "playback_url", "thumbnail_url", "duration_seconds", "status"]


class PostApprovalSerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)

    class Meta:
        model = PostApproval
        fields = ["id", "action", "note", "actor", "created_at"]


class PostListSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    category = CategoryMiniSerializer(read_only=True)

    class Meta:
        model = Post
        fields = [
            "id", "title", "slug", "short_description", "featured_image_url",
            "author", "category", "status", "views", "is_breaking",
            "is_featured", "is_trending", "published_at", "created_at",
        ]


class PostDetailSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    category = CategoryMiniSerializer(read_only=True)
    tags = TagMiniSerializer(read_only=True, many=True)
    approval_history = PostApprovalSerializer(read_only=True, many=True)
    video = VideoMiniSerializer(read_only=True)

    class Meta:
        model = Post
        fields = [
            "id", "title", "slug", "short_description", "content",
            "featured_image_url", "video", "author", "category", "tags",
            "status", "review_note", "seo_title", "seo_description",
            "views", "is_breaking", "is_featured", "is_trending",
            "submitted_at", "published_at", "created_at", "updated_at",
            "approval_history",
        ]


class VideoFeedItemSerializer(serializers.ModelSerializer):
    """Public video feed item — a published post that has a video
    attached. Used by the Videos / Video Details pages."""
    video = VideoMiniSerializer(read_only=True)
    category = CategoryMiniSerializer(read_only=True)
    author = UserSerializer(read_only=True)

    class Meta:
        model = Post
        fields = [
            "id", "title", "slug", "short_description", "featured_image_url",
            "video", "category", "author", "views", "published_at", "created_at",
        ]


class PostWriteSerializer(serializers.ModelSerializer):
    """Used for create/update by authors & editors. `status` is intentionally
    excluded — it can only change via the dedicated workflow actions below."""
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )

    class Meta:
        model = Post
        fields = [
            "title", "short_description", "content", "featured_image_url",
            "video", "category", "tags", "seo_title", "seo_description",
        ]

    def validate_category(self, value):
        if value is None:
            raise serializers.ValidationError("Category is required.")
        return value


class RejectOrRequestChangesSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=2000, allow_blank=False)


class ApprovePostSerializer(serializers.Serializer):
    publish_immediately = serializers.BooleanField(default=False)
