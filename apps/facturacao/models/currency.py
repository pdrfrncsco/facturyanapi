from django.db import models
from apps.common.models import TenantOwnedModel


class ExchangeRate(TenantOwnedModel):
    """
    Taxas de câmbio diárias para conversão de moedas estrangeiras para AOA.
    """
    currency_code = models.CharField(max_length=3, help_text="Ex: USD, EUR")
    rate = models.DecimalField(max_digits=18, decimal_places=4, help_text="Taxa para 1 unidade da moeda estrangeira em AOA")
    date = models.DateField()

    class Meta:
        ordering = ["-date"]
        unique_together = [("empresa", "currency_code", "date")]
        indexes = [
            models.Index(fields=["empresa", "currency_code", "date"]),
        ]

    def __str__(self) -> str:
        return f"{self.currency_code} @ {self.date}: {self.rate} AOA"
