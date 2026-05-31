from django.conf import settings
from django.db import models

from apps.common.models import TenantOwnedModel


class SaftExportJob(TenantOwnedModel):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pendente"
        READY = "Ready", "Pronto"
        ERROR = "Error", "Erro"

    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    filename = models.CharField(max_length=255)
    file = models.FileField(upload_to="saft/exports/", blank=True)
    error_message = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="saft_export_jobs",
    )

    class Meta:
        indexes = [
            models.Index(fields=["empresa", "status", "created_at"]),
            models.Index(fields=["empresa", "year", "month"]),
        ]

    def __str__(self) -> str:
        return f"SAFT {self.empresa_id} {self.year}-{self.month:02d} [{self.status}]"
