from django.db import models

from apps.common.models import TenantOwnedModel


class Client(TenantOwnedModel):
    name = models.CharField(max_length=255)
    nif = models.CharField(max_length=32)
    email = models.EmailField()
    phone = models.CharField(max_length=64, blank=True)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=120, default="Luanda")
    country = models.CharField(max_length=120, default="Angola")

    class Meta:
        ordering = ["name"]
        unique_together = [("empresa", "nif")]
        indexes = [
            models.Index(fields=["empresa", "nif"]),
            models.Index(fields=["empresa", "name"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.nif})"
