from django.db import models

from apps.common.models import TenantOwnedModel


class InvoiceDocument(TenantOwnedModel):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pendente"
        READY = "Ready", "Pronto"
        ERROR = "Error", "Erro"

    invoice = models.ForeignKey(
        "facturacao.Invoice",
        on_delete=models.CASCADE,
        related_name="documents",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    file = models.FileField(upload_to="invoices/pdf/", blank=True)
    error_message = models.TextField(blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["empresa", "invoice", "status"])]

    def __str__(self) -> str:
        return f"PDF {self.invoice_id} [{self.status}]"
