"""
Shared DRF permission classes implementing War of Justice's RBAC rules.
Every rule here is enforced server-side — the frontend hiding a button
(e.g. "Publish") is a UX nicety, never the actual authorization boundary.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_super_admin())


class IsAdminOrEditor(BasePermission):
    """Admin/Editor role, or Super Admin (who can do anything)."""
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_super_admin() or u.has_role("admin")))


class IsAuthorRole(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_super_admin() or u.has_role("admin", "author")))


class HasPermissionCode(BasePermission):
    """Usage: permission_classes = [HasPermissionCode('posts.approve')]"""
    def __init__(self, codename):
        self.codename = codename

    def __call__(self):
        return self

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.has_permission(self.codename))


class ReadOnlyOrAuthenticated(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)
