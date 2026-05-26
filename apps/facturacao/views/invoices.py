from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.common.permissions import TenantRolePermission
from apps.facturacao.selectors.invoices import invoices_for_empresa
from apps.facturacao.serializers.invoices import DraftInvoiceInputSerializer, InvoiceSerializer
from apps.facturacao.services.invoices import create_draft_invoice, delete_draft_invoice, issue_invoice, update_draft_invoice


class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [TenantRolePermission]
    role_permissions = {
        "list": TenantRolePermission.ALL_ROLES,
        "retrieve": TenantRolePermission.ALL_ROLES,
        "create": TenantRolePermission.WRITE_ROLES,
        "update": TenantRolePermission.WRITE_ROLES,
        "partial_update": TenantRolePermission.WRITE_ROLES,
        "destroy": TenantRolePermission.WRITE_ROLES,
        "issue": TenantRolePermission.FISCAL_MANAGER_ROLES,
        "sync_agt": TenantRolePermission.FISCAL_MANAGER_ROLES,
    }
    search_fields = ["invoice_no", "client_name", "client_nif"]
    ordering_fields = ["created_at", "issue_date", "grand_total"]
    ordering = ["-created_at"]
    filterset_fields = ["type", "status"]

    def get_queryset(self):
        return invoices_for_empresa(self.request.empresa)

    def _raise_drf_validation(self, exc: DjangoValidationError):
        if hasattr(exc, "message_dict"):
            raise ValidationError(exc.message_dict)
        raise ValidationError(exc.messages)

    def create(self, request, *args, **kwargs):
        serializer = DraftInvoiceInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invoice = create_draft_invoice(
                empresa=request.empresa,
                user=request.user,
                data=serializer.validated_data,
                request=request,
            )
        except DjangoValidationError as exc:
            self._raise_drf_validation(exc)
        return Response(self.get_serializer(invoice).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        invoice = self.get_object()
        serializer = DraftInvoiceInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invoice = update_draft_invoice(
                invoice=invoice,
                user=request.user,
                data=serializer.validated_data,
                request=request,
            )
        except DjangoValidationError as exc:
            self._raise_drf_validation(exc)
        return Response(self.get_serializer(invoice).data)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        try:
            delete_draft_invoice(invoice=instance, user=self.request.user, request=self.request)
        except DjangoValidationError as exc:
            self._raise_drf_validation(exc)

    @action(detail=True, methods=["post"], url_path="emitir")
    def issue(self, request, pk=None):
        try:
            invoice = issue_invoice(invoice=self.get_object(), user=request.user, request=request)
        except DjangoValidationError as exc:
            self._raise_drf_validation(exc)
        return Response(self.get_serializer(invoice).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="sync-agt")
    def sync_agt(self, request, pk=None):
        return Response(
            {"detail": "Sincronização AGT será activada com a fila assíncrona."},
            status=status.HTTP_409_CONFLICT,
        )
