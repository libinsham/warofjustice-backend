"""Super Admin user-management endpoints: list/manage all users, assign
roles, activate/suspend accounts. Kept separate from views.py (auth) for
clarity — these all require IsSuperAdmin."""
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import AuditLog
from apps.core.permissions import IsSuperAdmin

from .models import Role, User
from .serializers import UserSerializer


class AssignRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=[r[0] for r in Role.ROLE_CHOICES])


class SetStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[s[0] for s in User.STATUS_CHOICES])


class AdminUserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    /api/v1/super-admin/users/                - list all users, filterable
    /api/v1/super-admin/users/{id}/set-role/   - promote/demote a user
    /api/v1/super-admin/users/{id}/set-status/ - activate/suspend/approve pending authors
    """
    permission_classes = [IsSuperAdmin]
    serializer_class = UserSerializer
    queryset = User.objects.select_related("role", "profile").all()

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if role := params.get("role"):
            qs = qs.filter(role__name=role)
        if status_filter := params.get("status"):
            qs = qs.filter(status=status_filter)
        if search := params.get("search"):
            qs = qs.filter(email__icontains=search)
        return qs

    @action(detail=True, methods=["post"], url_path="set-role")
    def set_role(self, request, pk=None):
        user = self.get_object()
        serializer = AssignRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = Role.objects.get(name=serializer.validated_data["role"])
        old_role = user.role.name
        user.role = role
        user.save(update_fields=["role"])

        AuditLog.objects.create(
            actor=request.user, action="user.role_changed",
            target_type="User", target_id=str(user.id),
            metadata={"from": old_role, "to": role.name},
        )
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="set-status")
    def set_status(self, request, pk=None):
        user = self.get_object()
        serializer = SetStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old_status = user.status
        user.status = serializer.validated_data["status"]
        user.save(update_fields=["status"])

        AuditLog.objects.create(
            actor=request.user, action="user.status_changed",
            target_type="User", target_id=str(user.id),
            metadata={"from": old_status, "to": user.status},
        )
        return Response(UserSerializer(user).data)
