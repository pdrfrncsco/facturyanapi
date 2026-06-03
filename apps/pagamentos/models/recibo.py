from django.db import models
from django.core.exceptions import ValidationError
from apps.common.models import TenantOwnedModel
from apps.facturacao.models import Invoice


FISCAL_IMMUTABLE_FIELDS = (
    "receipt_no",
    "issue_date",
    "client_id",
    "total_amount",
    "payment_method",
    "receipt_hash",
    "previous_hash",
    "qrcode_string",
)


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
            models.Index(fields=["empresa", "client_id"]),
            models.Index(fields=["client_id", "issue_date"], name="idx_recibo_client_date"),
        ]

    def __str__(self):
        return f"{self.receipt_no or 'Rascunho'} - {self.client.name}"

    def delete(self, using=None, keep_parents=False):
        if self.status != self.Status.DRAFT:
            raise ValidationError("Recibos emitidos nao podem ser removidos.")
        super().delete(using=using, keep_parents=keep_parents)

    def save(self, *args, **kwargs):
        if self.pk and self.status != self.Status.DRAFT:
            previous = Recibo.objects.filter(pk=self.pk).first()
            if previous and previous.status != self.Status.DRAFT:
                if self.status == self.Status.CANCELLED and previous.status != self.Status.CANCELLED:
                    pass
                else:
                    for field in FISCAL_IMMUTABLE_FIELDS:
                        if getattr(self, field) != getattr(previous, field):
                            raise ValidationError(
                                "Recibos emitidos sao imutaveis. Alteracoes nao permitidas."
                            )
        super().save(*args, **kwargs)


class ReciboItem(TenantOwnedModel):
    recibo = models.ForeignKey(Recibo, on_delete=models.CASCADE, related_name="items")
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="receipt_items")
    amount_paid = models.DecimalField(max_digits=18, decimal_places=2)

    def __str__(self):
        return f"{self.invoice.invoice_no} - {self.amount_paid}"

    def save(self, *args, **kwargs):
        if self.pk and self.recibo.status != Recibo.Status.DRAFT:
            raise ValidationError("Itens de recibos emitidos nao podem ser alterados.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.recibo.status != Recibo.Status.DRAFT:
            raise ValidationError("Itens de recibos emitidos nao podem ser removidos.")
        super().delete(*args, **kwargs)
