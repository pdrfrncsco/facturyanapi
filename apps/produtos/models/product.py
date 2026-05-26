from django.db import models

from apps.common.models import TenantOwnedModel


class Product(TenantOwnedModel):
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=18, decimal_places=2)
    stock = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=14)
    exemption_code = models.CharField(max_length=32, blank=True)
    unit = models.CharField(max_length=16, default="UN")

    class Meta:
        ordering = ["code"]
        unique_together = [("empresa", "code")]
        indexes = [
            models.Index(fields=["empresa", "code"]),
            models.Index(fields=["empresa", "category"]),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"
