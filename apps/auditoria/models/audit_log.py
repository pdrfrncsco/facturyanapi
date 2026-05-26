from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel, UUIDModel


class AuditLog(UUIDModel, TimeStampedModel):
    empresa = models.ForeignKey("empresas.Empresa", on_delete=models.PROTECT, related_name="audit_logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    user_name = models.CharField(max_length=255, blank=True)
    action = models.CharField(max_length=80, db_index=True)
    details = models.TextField()
    entity_type = models.CharField(max_length=80, blank=True)
    entity_id = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["empresa", "created_at"]),
            models.Index(fields=["empresa", "action"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise ValueError("Audit logs are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit logs cannot be deleted.")
