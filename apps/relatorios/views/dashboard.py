from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auditoria.serializers.audit_logs import AuditLogSerializer
from apps.common.permissions import TenantAccessPermission
from apps.relatorios.selectors.dashboard import dashboard_stats_for_empresa


class DashboardStatsView(APIView):
    permission_classes = [TenantAccessPermission]

    def get(self, request):
        stats = dashboard_stats_for_empresa(request.empresa)
        stats["recentActivity"] = AuditLogSerializer(stats["recentActivity"], many=True).data
        return Response(stats)
