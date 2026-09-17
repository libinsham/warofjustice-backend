from django.contrib import admin

from .models import Magazine


@admin.register(Magazine)
class MagazineAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "issue_number",
        "publication_date",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "publication_date",
    )

    search_fields = (
        "title",
        "issue_number",
        "description",
    )

    ordering = (
        "-publication_date",
        "-created_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Magazine Information",
            {
                "fields": (
                    "title",
                    "issue_number",
                    "publication_date",
                    "description",
                )
            },
        ),
        (
            "Files",
            {
                "fields": (
                    "featured_image",
                    "pdf_file",
                )
            },
        ),
        (
            "Publication",
            {
                "fields": (
                    "status",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )