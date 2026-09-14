from django.contrib import admin

from .models import (
    Role,
    Permission,
    User,
    Profile,
    SubscriberApplication,
)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "label",
        "description",
    )

    search_fields = (
        "name",
        "label",
    )


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = (
        "codename",
        "label",
        "group",
    )

    search_fields = (
        "codename",
        "label",
        "group",
    )

    filter_horizontal = (
        "roles",
    )


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "username",
        "role",
        "status",
        "is_staff",
        "is_superuser",
    )

    list_filter = (
        "role",
        "status",
        "is_staff",
        "is_superuser",
    )

    search_fields = (
        "email",
        "username",
    )

    ordering = (
        "email",
    )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "full_name",
        "phone_number",
        "created_at",
    )

    search_fields = (
        "user__email",
        "full_name",
    )


@admin.register(SubscriberApplication)
class SubscriberApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "application_id",
        "user",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
    )

    search_fields = (
        "application_id",
        "user__email",
    )