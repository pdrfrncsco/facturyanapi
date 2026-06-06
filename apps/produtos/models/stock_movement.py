from django.db import models
from apps.common.models import TenantOwnedModel


class StockMovement(TenantOwnedModel):
    class Type(models.TextChoices):
        IN = "In", "Entrada"
        OUT = "Out", "Saída"

    product = models.ForeignKey("produtos.Product", on_delete=models.CASCADE, related_name="movements")
    type = models.CharField(max_length=3, choices=Type.choices)
    quantity = models.DecimalField(max_digits=18, decimal_places=3)
    reason = models.CharField(max_length=255)
    operator = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["empresa", "product", "timestamp"]),
        ]

    def __str__(self) -> str:
        return f"{self.type} {self.quantity} for {self.product.name}"
