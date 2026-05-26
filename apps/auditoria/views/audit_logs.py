from rest_framework import viewsets

from apps.auditoria.selectors.audit_logs import audit_logs_for_empresa
from apps.auditoria.serializers.audit_logs import AuditLogSerializer
from apps.common.permissions import TenantRolePermission


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [TenantRolePermission]
    read_roles = TenantRolePermission.AUDIT_READER_ROLES
    search_fields = ["action", "details", "user_name"]
    ordering_fields = ["created_at", "action"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return audit_logs_for_empresa(self.request.empresa)
