from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from apps.core.permissions import IsSuperAdmin

from .models import SiteSettings
from .serializers import SiteSettingsSerializer


class SiteSettingsViewSet(viewsets.ModelViewSet):
    """
    GET is public (site name, logo, social links, etc. are needed to
    render the public site). Only Super Admin can create/update/delete —
    matches "Configure platform settings" being Super Admin-only per spec.
    Uses `key` as the lookup so the frontend can PUT /settings/site_name/
    directly instead of looking up an id first.
    """
    queryset = SiteSettings.objects.all()
    serializer_class = SiteSettingsSerializer
    lookup_field = "key"

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsSuperAdmin()]
