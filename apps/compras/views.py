from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.common.permissions import TenantRolePermission
from .models import SupplierInvoice, SupplierInvoiceItem
from .serializers import SupplierInvoiceSerializer, SupplierInvoiceUploadSerializer
from .services import extract_invoice_data
from django.db import transaction

class SupplierInvoiceViewSet(viewsets.ModelViewSet):
    permission_classes = [TenantRolePermission]
    role_permissions = {
        "list": TenantRolePermission.ALL_ROLES,
        "retrieve": TenantRolePermission.ALL_ROLES,
        "create": TenantRolePermission.WRITE_ROLES,
        "update": TenantRolePermission.WRITE_ROLES,
        "destroy": TenantRolePermission.WRITE_ROLES,
        "analyze": TenantRolePermission.WRITE_ROLES,
        "confirm": TenantRolePermission.WRITE_ROLES,
    }

    def get_queryset(self):
        return SupplierInvoice.objects.filter(empresa=self.request.empresa).order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "analyze":
            return SupplierInvoiceUploadSerializer
        return SupplierInvoiceSerializer

    @action(detail=False, methods=["post"], url_path="analisar-ai")
    def analyze(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        uploaded_file = serializer.validated_data["file"]
        
        # Guardar temporariamente para análise
        invoice = SupplierInvoice.objects.create(
            empresa=request.empresa,
            file=uploaded_file,
            status=SupplierInvoice.Status.PENDING
        )
        
        # Chamar serviço AI
        extracted_data = extract_invoice_data(invoice.file.path, uploaded_file.content_type)
        
        if extracted_data:
            with transaction.atomic():
                invoice.supplier_name = extracted_data.get("supplier_name")
                invoice.supplier_nif = extracted_data.get("supplier_nif")
                invoice.invoice_no = extracted_data.get("invoice_no")
                invoice.issue_date = extracted_data.get("issue_date")
                invoice.currency = extracted_data.get("currency", "AOA")
                invoice.subtotal = extracted_data.get("subtotal", 0)
                invoice.tax_total = extracted_data.get("tax_total", 0)
                invoice.grand_total = extracted_data.get("grand_total", 0)
                invoice.raw_ai_analysis = extracted_data
                invoice.save()
                
                # Criar itens
                for item in extracted_data.get("items", []):
                    SupplierInvoiceItem.objects.create(
                        empresa=request.empresa,
                        invoice=invoice,
                        description=item.get("description"),
                        quantity=item.get("quantity", 1),
                        unit_price=item.get("unit_price", 0),
                        tax_rate=item.get("tax_rate", 14),
                        total=item.get("total", 0)
                    )
            
            return Response(SupplierInvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)
        
        return Response({"detail": "Não foi possível extrair dados automaticamente."}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    @action(detail=True, methods=["post"], url_path="confirmar")
    def confirm(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status != SupplierInvoice.Status.PENDING:
            return Response({"detail": "Apenas facturas pendentes podem ser confirmadas."}, status=status.HTTP_400_BAD_REQUEST)
        
        invoice.status = SupplierInvoice.Status.VALIDATED
        invoice.save(update_fields=["status", "updated_at"])
        
        return Response(SupplierInvoiceSerializer(invoice).data)
