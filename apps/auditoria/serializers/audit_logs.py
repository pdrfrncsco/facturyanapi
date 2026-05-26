from rest_framework import serializers

from apps.auditoria.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    timestamp = serializers.DateTimeField(source="created_at", read_only=True)
    userId = serializers.UUIDField(source="user_id", read_only=True)
    userName = serializers.CharField(source="user_name", read_only=True)
    ipAddress = serializers.IPAddressField(source="ip_address", read_only=True)
    tenantId = serializers.UUIDField(source="empresa_id", read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "timestamp", "userId", "userName", "action", "details", "ipAddress", "tenantId"]
