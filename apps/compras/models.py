from django.db import models
from apps.common.models import TenantOwnedModel

class SupplierInvoice(TenantOwnedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente de Revisão"
        VALIDATED = "VALIDATED", "Confirmada"
        PAID = "PAID", "Paga"
        CANCELLED = "CANCELLED", "Anulada"

    supplier_name = models.CharField(max_length=255, null=True, blank=True)
    supplier_nif = models.CharField(max_length=32, null=True, blank=True)
    invoice_no = models.CharField(max_length=100, null=True, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    
    currency = models.CharField(max_length=3, default="AOA")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    file = models.FileField(upload_to="supplier_invoices/%Y/%m/", null=True, blank=True)
    raw_ai_analysis = models.JSONField(null=True, blank=True, help_text="Resposta bruta da IA")
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Compra {self.invoice_no or 'Rascunho'} - {self.supplier_name or 'Desconhecido'}"

class SupplierInvoiceItem(TenantOwnedModel):
    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=18, decimal_places=3)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=14)
    total = models.DecimalField(max_digits=18, decimal_places=2)

    def __str__(self):
        return f"{self.description} x {self.quantity}"
