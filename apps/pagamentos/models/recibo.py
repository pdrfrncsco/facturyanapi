from django.db import models
from django.core.exceptions import ValidationError
from apps.common.models import TenantOwnedModel
from apps.facturacao.models import Invoice


class Recibo(TenantOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "Draft", "Rascunho"
        ISSUED = "Issued", "Emitido"
        CANCELLED = "Cancelled", "Cancelado"

    class PaymentMethod(models.TextChoices):
        CASH = "CH", "Numerário"
        TRANSFER = "TR", "Transferência Bancária"
        TPA = "TP", "TPA"
        DEPOSIT = "DP", "Depósito"
        OTHER = "OU", "Outro"

    client = models.ForeignKey("clientes.Client", on_delete=models.PROTECT, related_name="recibos")
    receipt_no = models.CharField(max_length=32, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=2, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    
    # Fiscal Fields
    previous_hash = models.CharField(max_length=255, blank=True)
    receipt_hash = models.CharField(max_length=255, blank=True)
    qrcode_string = models.TextField(blank=True)
    
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-issue_date", "-created_at"]
        indexes = [
            models.Index(fields=["empresa", "receipt_no"]),
            models.Index(fields=["empresa", "issue_date"]),
        ]

    def __str__(self):
        return f"{self.receipt_no or 'Rascunho'} - {self.client.name}"

    def save(self, *args, **kwargs):
        if self.pk and self.status != self.Status.DRAFT:
            # Check for immutable fields if already issued
            # For now, simple block
            pass
        super().save(*args, **kwargs)


class ReciboItem(TenantOwnedModel):
    recibo = models.ForeignKey(Recibo, on_delete=models.CASCADE, related_name="items")
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="receipt_items")
    amount_paid = models.DecimalField(max_digits=18, decimal_places=2)

    def __str__(self):
        return f"{self.invoice.invoice_no} - {self.amount_paid}"
