from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Magazine(models.Model):
    DRAFT = "draft"
    PUBLISHED = "published"

    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (PUBLISHED, "Published"),
    ]

    title = models.CharField(max_length=255)

    issue_number = models.CharField(
        max_length=100,
        blank=True,
    )

    publication_date = models.DateField()

    description = models.TextField(
        blank=True,
    )

    featured_image = models.ImageField(
        upload_to="emagazines/covers/",
    )

    pdf_file = models.FileField(
        upload_to="emagazines/pdfs/",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-publication_date", "-created_at"]

    def clean(self):
        super().clean()

        if self.pdf_file:
            file_name = self.pdf_file.name.lower()

            if not file_name.endswith(".pdf"):
                raise ValidationError(
                    {"pdf_file": "Only PDF files are allowed."}
                )

    def __str__(self):
        if self.issue_number:
            return f"{self.title} - {self.issue_number}"

        return self.title