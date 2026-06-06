from django.db import models
from apps.common.models import TenantOwnedModel, UUIDModel


class Estabelecimento(TenantOwnedModel):
    code = models.CharField(max_length=32, help_text="Código oficial da AGT (ex: SEDE, LOJA01)")
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=120, default="Luanda")
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        unique_together = [("empresa", "code")]
        indexes = [
            models.Index(fields=["empresa", "code"]),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"
