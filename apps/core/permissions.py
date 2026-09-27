
"""
Shared DRF permission classes implementing War of Justice's RBAC rules.

Every rule is enforced server-side.

Supported roles:
- super_super_admin
- super_admin
- admin
- author
- member
- contributor
- subscriber
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS


def is_authenticated_user(request):
    """Check whether the request has an authenticated user."""
    user = request.user
    return bool(user and user.is_authenticated)


def get_role_name(user):
    """Safely retrieve the user's role name."""
    return getattr(getattr(user, "role", None), "name", "")


def is_super_super_admin(user):
    """Check for the highest-level administrator role."""
    if get_role_name(user) == "super_super_admin":
        return True

    checker = getattr(user, "is_super_super_admin", None)
    return bool(callable(checker) and checker())


def is_super_admin(user):
    """
    Check for either Super Admin or Super Super Admin.
    """
    if is_super_super_admin(user):
        return True

    if get_role_name(user) == "super_admin":
        return True

    checker = getattr(user, "is_super_admin", None)
    return bool(callable(checker) and checker())


class IsSuperAdmin(BasePermission):
    """
    Allow Super Admin and Super Super Admin access.
    """

    def has_permission(self, request, view):
        return bool(
            is_authenticated_user(request)
            and is_super_admin(request.user)
        )


class IsAdminOrEditor(BasePermission):
    """
    Allow:
    - Super Super Admin
    - Super Admin
    - Admin
    """

    def has_permission(self, request, view):
        if not is_authenticated_user(request):
            return False

        user = request.user

        return bool(
            is_super_admin(user)
            or user.has_role("admin")
        )


class IsAuthorRole(BasePermission):
    """
    Allow:
    - Super Super Admin
    - Super Admin
    - Admin
    - Author
    """

    def has_permission(self, request, view):
        if not is_authenticated_user(request):
            return False

        user = request.user

        # Explicitly permit both administrator levels.
        if is_super_super_admin(user):
            return True

        if is_super_admin(user):
            return True

        return bool(user.has_role("admin", "author"))


class HasPermissionCode(BasePermission):
    """
    Usage:
        permission_classes = [HasPermissionCode("posts.approve")]

    Super administrators bypass individual permission codes.
    Other users must have the requested permission.
    """

    def __init__(self, codename):
        self.codename = codename

    def __call__(self):
        return self

    def has_permission(self, request, view):
        if not is_authenticated_user(request):
            return False

        user = request.user

        if is_super_admin(user):
            return True

        return bool(user.has_permission(self.codename))


class ReadOnlyOrAuthenticated(BasePermission):
    """
    Allow unrestricted safe methods.
    Require authentication for write operations.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        return is_authenticated_user(request)