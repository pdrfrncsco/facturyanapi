from django.conf import settings
from django.db import models

from apps.common.models import SoftDeleteModel, TimeStampedModel, UUIDModel


class Empresa(UUIDModel, TimeStampedModel, SoftDeleteModel):
    name = models.CharField(max_length=255)
    nif = models.CharField(max_length=32, unique=True)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=120, default="Luanda")
    country = models.CharField(max_length=120, default="Angola")
    fiscal_regime = models.CharField(max_length=255)
    logo_url = models.URLField(blank=True)
    agt_certificate_no = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["nif"]),
            models.Index(fields=["is_active", "is_deleted"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.nif})"


class EmpresaMembership(UUIDModel, TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Proprietário"
        ADMIN = "admin", "Administrador"
        MEMBER = "member", "Membro"
        AUDITOR = "auditor", "Auditor"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="empresa_memberships")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.MEMBER)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("user", "empresa")]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["empresa", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} -> {self.empresa}"
