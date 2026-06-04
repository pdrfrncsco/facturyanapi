from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import TenantRolePermission
from apps.relatorios.selectors.reports import (
    generate_account_statement,
    generate_aging_report,
    generate_iva_map,
)


class IvaMapView(APIView):
    permission_classes = [TenantRolePermission]
    read_roles = TenantRolePermission.ALL_ROLES

    def get(self, request):
        year = int(request.query_params.get('year', 0))
        month = int(request.query_params.get('month', 0))
        
        if not year or not month:
            return Response({"error": "year e month são obrigatórios"}, status=400)
            
        report = generate_iva_map(request.empresa, year, month)
        return Response(report)


class AccountStatementView(APIView):
    permission_classes = [TenantRolePermission]
    read_roles = TenantRolePermission.ALL_ROLES

    def get(self, request, client_id):
        statement = generate_account_statement(request.empresa, client_id)
        return Response(statement)


class AgingReportView(APIView):
    permission_classes = [TenantRolePermission]
    read_roles = TenantRolePermission.ALL_ROLES

    def get(self, request):
        report = generate_aging_report(request.empresa)
        return Response(report)
