from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import Comment


class CommentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "post", "user", "parent", "body", "status", "created_at"]
        read_only_fields = ["status"]


class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ["post", "parent", "body"]


class ModerateCommentSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["approved", "spam", "rejected"])
