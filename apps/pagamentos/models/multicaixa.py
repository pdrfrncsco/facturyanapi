from django.db import models
from apps.common.models import TenantOwnedModel

class MulticaixaReference(TenantOwnedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        PAID = "PAID", "Pago"
        EXPIRED = "EXPIRED", "Expirado"
        CANCELLED = "CANCELLED", "Cancelado"

    invoice = models.OneToOneField(
        "facturacao.Invoice", on_delete=models.CASCADE, related_name="multicaixa_reference"
    )
    entity_code = models.CharField(max_length=5, help_text="Código da Entidade (ex: 00245)")
    reference_number = models.CharField(max_length=9, unique=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    expires_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Provider-specific tracking (ex: Proxypay, etc)
    provider_id = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return f"Ref {self.reference_number} - {self.invoice.invoice_no}"
