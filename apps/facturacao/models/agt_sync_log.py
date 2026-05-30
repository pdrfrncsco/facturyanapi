from django.db import models

from apps.common.models import TenantOwnedModel


class AgtSyncLog(TenantOwnedModel):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pendente"
        SUCCESS = "Success", "Sucesso"
        ERROR = "Error", "Erro"

    invoice = models.ForeignKey(
        "facturacao.Invoice",
        on_delete=models.PROTECT,
        related_name="agt_sync_logs",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    response_code = models.CharField(max_length=128, blank=True)
    error_message = models.TextField(blank=True)
    attempt_count = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["empresa", "invoice", "status"]),
            models.Index(fields=["empresa", "status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"AGT {self.invoice_id} [{self.status}]"
