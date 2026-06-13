from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import FileResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.common.permissions import TenantRolePermission
from apps.facturacao.models import Invoice, InvoiceDocument
from apps.facturacao.selectors.invoices import invoices_for_empresa
from apps.facturacao.serializers.documents import AgtSyncLogSerializer, InvoiceDocumentSerializer
from apps.facturacao.serializers.invoices import CancelInvoiceInputSerializer, DraftInvoiceInputSerializer, InvoiceSerializer
from apps.facturacao.services.agt_sync import enqueue_invoice_pdf, trigger_agt_sync
from apps.facturacao.services.invoices import (
    cancel_invoice,
    create_draft_invoice,
    delete_draft_invoice,
    issue_invoice,
    update_draft_invoice,
)


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
        "cancel": TenantRolePermission.FISCAL_MANAGER_ROLES,
        "sync_agt": TenantRolePermission.FISCAL_MANAGER_ROLES,
        "pdf": TenantRolePermission.ALL_ROLES,
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

    @action(detail=True, methods=["post"], url_path="cancelar")
    def cancel(self, request, pk=None):
        serializer = CancelInvoiceInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invoice = cancel_invoice(
                invoice=self.get_object(),
                user=request.user,
                reason=serializer.validated_data["reason"],
                request=request,
            )
        except DjangoValidationError as exc:
            self._raise_drf_validation(exc)
        return Response(self.get_serializer(invoice).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="sync-agt")
    def sync_agt(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status == Invoice.Status.DRAFT:
            raise ValidationError({"status": "Emita a factura antes de sincronizar com a AGT."})
        sync_log = trigger_agt_sync(invoice=invoice)
        return Response(
            AgtSyncLogSerializer(sync_log).data,
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"], url_path="validar-agt")
    def validate_agt(self, request, pk=None):
        from apps.facturacao.models import AgtSyncLog
        from apps.facturacao.services.agt_sync import poll_agt_status
        
        invoice = self.get_object()
        sync_log = invoice.agt_sync_logs.filter(status=AgtSyncLog.Status.WAITING).order_by("-created_at").first()
        
        if not sync_log:
            # Se não há log em espera, podemos tentar um sync se ainda não foi sincronizado
            if invoice.status in {Invoice.Status.ISSUED, Invoice.Status.AGT_ERROR}:
                return Response(
                    {"detail": "Não há pedido pendente de validação. Use 'Sincronizar' primeiro."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            return Response({"detail": "Documento já sincronizado ou em estado inválido para validação."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            poll_agt_status(sync_log_id=str(sync_log.id))
            invoice.refresh_from_db()
            return Response(self.get_serializer(invoice).data)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request, pk=None):
        invoice = self.get_object()
        document = invoice.documents.order_by("-created_at").first()
        if document is None or document.status == InvoiceDocument.Status.PENDING:
            enqueue_invoice_pdf(invoice=invoice)
            return Response(
                {"status": "pending", "detail": "PDF em geração. Tente novamente dentro de instantes."},
                status=status.HTTP_202_ACCEPTED,
            )
        if document.status == InvoiceDocument.Status.ERROR:
            return Response(
                {"status": "error", "detail": document.error_message or "Falha na geração do PDF."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if not document.file:
            return Response({"status": "missing", "detail": "PDF indisponível."}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(document.file.open("rb"), as_attachment=True, filename=document.file.name)

    @action(detail=True, methods=["get"], url_path="documento")
    def document_status(self, request, pk=None):
        invoice = self.get_object()
        document = invoice.documents.order_by("-created_at").first()
        if document is None:
            return Response({"status": "missing"}, status=status.HTTP_404_NOT_FOUND)
        return Response(InvoiceDocumentSerializer(document, context={"request": request}).data)
