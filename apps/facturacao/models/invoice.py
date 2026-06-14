import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TenantOwnedModel


FISCAL_IMMUTABLE_FIELDS = (
    "invoice_no",
    "type",
    "issue_date",
    "estabelecimento_id",
    "currency",
    "exchange_rate",
    "client_id",
    "client_name",
    "client_nif",
    "client_address",
    "subtotal",
    "discount_total",
    "tax_total",
    "withholding_tax_rate",
    "withholding_tax_amount",
    "grand_total",
    "invoice_hash",
    "previous_hash",
    "qrcode_string",
    "origin_document_id",
    "rectification_reason",
)


class FiscalSeries(TenantOwnedModel):
    estabelecimento = models.ForeignKey(
        "empresas.Estabelecimento", 
        on_delete=models.CASCADE, 
        related_name="series",
        null=True,
        blank=True
    )
    code = models.CharField(max_length=24)
    document_type = models.CharField(max_length=8)
    fiscal_year = models.PositiveIntegerField()
    current_number = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("empresa", "estabelecimento", "code", "document_type", "fiscal_year")]
        indexes = [models.Index(fields=["empresa", "estabelecimento", "document_type", "is_active"])]

    def __str__(self) -> str:
        branch = self.estabelecimento.code if self.estabelecimento else "GLOBAL"
        return f"{self.document_type} {self.fiscal_year}/{self.code} ({branch})"


class Invoice(TenantOwnedModel):
    class Type(models.TextChoices):
        FT = "FT", "Factura"
        FR = "FR", "Factura-Recibo"
        VD = "VD", "Venda a Dinheiro"
        NC = "NC", "Nota de Crédito"
        PP = "PP", "Factura Proforma"

    class Status(models.TextChoices):
        DRAFT = "Draft", "Rascunho"
        ISSUED = "Issued", "Emitida"
        PAID = "Paid", "Paga"
        PARTIAL = "Partial", "Parcial"
        CANCELLED = "Cancelled", "Cancelada"
        AGT_SYNCED = "AGT_Synced", "Sincronizada AGT"
        AGT_ERROR = "AGT_Error", "Erro AGT"

    invoice_no = models.CharField(max_length=64, blank=True)
    estabelecimento = models.ForeignKey(
        "empresas.Estabelecimento",
        on_delete=models.PROTECT,
        related_name="invoices",
        null=True,
        blank=True
    )
    type = models.CharField(max_length=8, choices=Type.choices)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    
    # Currency fields
    currency = models.CharField(max_length=3, default="AOA")
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=4, default=1)
    
    issue_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    client = models.ForeignKey("clientes.Client", on_delete=models.PROTECT, related_name="invoices")
    client_name = models.CharField(max_length=255)
    client_nif = models.CharField(max_length=32)
    client_address = models.CharField(max_length=255)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    withholding_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    withholding_tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    invoice_hash = models.CharField(max_length=128, blank=True)
    previous_hash = models.CharField(max_length=128, blank=True)
    qrcode_string = models.TextField(blank=True)
    agt_sync_date = models.DateTimeField(null=True, blank=True)
    agt_response_code = models.CharField(max_length=128, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cancelled_invoices",
    )
    notes = models.TextField(blank=True)
    origin_document = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credit_notes",
        help_text="Factura original em caso de Nota de Crédito",
    )
    rectification_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_invoices")

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("empresa", "invoice_no")]
        indexes = [
            models.Index(fields=["empresa", "status"]),
            models.Index(fields=["empresa", "issue_date"]),
            models.Index(fields=["empresa", "due_date"]),
            models.Index(fields=["empresa", "invoice_no"]),
            models.Index(fields=["empresa", "type", "issue_date"], name="idx_empresa_type_date"),
            models.Index(fields=["client_id", "issue_date"], name="idx_client_date"),
        ]

    def delete(self, using=None, keep_parents=False):
        if self.status != self.Status.DRAFT:
            raise ValidationError("Documentos fiscais emitidos nao podem ser removidos.")
        super().delete(using=using, keep_parents=keep_parents)

    def save(self, *args, **kwargs):
        if self.pk and self.status != self.Status.DRAFT:
            previous = Invoice.objects.filter(pk=self.pk).first()
            if previous and previous.status != self.Status.DRAFT:
                if self.status == self.Status.CANCELLED and previous.status != self.Status.CANCELLED:
                    pass
                else:
                    for field in FISCAL_IMMUTABLE_FIELDS:
                        if getattr(self, field) != getattr(previous, field):
                            raise ValidationError(
                                f"Documentos fiscais emitidos sao imutaveis. Alteracoes no campo {field} nao permitidas."
                            )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.invoice_no or f"{self.type} draft"


class InvoiceItem(TenantOwnedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("produtos.Product", on_delete=models.PROTECT)
    product_name = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=18, decimal_places=3)
    price = models.DecimalField(max_digits=18, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        indexes = [models.Index(fields=["empresa", "invoice"])]

    def save(self, *args, **kwargs):
        if self.pk and self.invoice.status != Invoice.Status.DRAFT:
            raise ValidationError("Itens de documentos fiscais emitidos nao podem ser alterados.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.invoice.status != Invoice.Status.DRAFT:
            raise ValidationError("Itens de documentos fiscais emitidos nao podem ser removidos.")
        super().delete(*args, **kwargs)
