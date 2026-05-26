from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.permissions import TenantRolePermission
from apps.facturacao.selectors.invoices import invoices_for_empresa
from apps.facturacao.serializers.invoices import InvoiceSerializer


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [TenantRolePermission]
    role_permissions = {
        "list": TenantRolePermission.ALL_ROLES,
        "retrieve": TenantRolePermission.ALL_ROLES,
        "issue": TenantRolePermission.FISCAL_MANAGER_ROLES,
        "sync_agt": TenantRolePermission.FISCAL_MANAGER_ROLES,
    }
    search_fields = ["invoice_no", "client_name", "client_nif"]
    ordering_fields = ["created_at", "issue_date", "grand_total"]
    ordering = ["-created_at"]
    filterset_fields = ["type", "status"]

    def get_queryset(self):
        return invoices_for_empresa(self.request.empresa)

    @action(detail=True, methods=["post"], url_path="emitir")
    def issue(self, request, pk=None):
        return Response(
            {"detail": "Emissão fiscal será activada no milestone de facturação."},
            status=status.HTTP_409_CONFLICT,
        )

    @action(detail=True, methods=["post"], url_path="sync-agt")
    def sync_agt(self, request, pk=None):
        return Response(
            {"detail": "Sincronização AGT será activada com a fila assíncrona."},
            status=status.HTTP_409_CONFLICT,
        )
