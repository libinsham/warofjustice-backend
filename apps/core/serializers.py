from rest_framework import serializers

from .models import SiteSettings


class SiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = ["id", "key", "value", "value_type", "updated_at"]
        read_only_fields = ["id", "updated_at"]
