from rest_framework import serializers

from .models import Magazine


class MagazineSerializer(serializers.ModelSerializer):
    featured_image_url = serializers.SerializerMethodField()
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Magazine
        fields = [
            "id",
            "title",
            "issue_number",
            "publication_date",
            "description",
            "featured_image",
            "featured_image_url",
            "pdf_file",
            "pdf_url",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "featured_image_url",
            "pdf_url",
            "created_at",
            "updated_at",
        ]

    def get_featured_image_url(self, obj):
        request = self.context.get("request")

        if not obj.featured_image:
            return None

        url = obj.featured_image.url

        if request:
            return request.build_absolute_uri(url)

        return url

    def get_pdf_url(self, obj):
        request = self.context.get("request")

        if not obj.pdf_file:
            return None

        url = obj.pdf_file.url

        if request:
            return request.build_absolute_uri(url)

        return url

    def validate_pdf_file(self, value):
        file_name = value.name.lower()

        if not file_name.endswith(".pdf"):
            raise serializers.ValidationError(
                "Only PDF files are allowed."
            )

        return value