from django.db import models
from apps.common.models import TenantOwnedModel
from django.utils import timezone
from dateutil.relativedelta import relativedelta


class RecurringInvoice(TenantOwnedModel):
    class Frequency(models.TextChoices):
        WEEKLY = "WEEKLY", "Semanal"
        MONTHLY = "MONTHLY", "Mensal"
        QUARTERLY = "QUARTERLY", "Trimestral"
        YEARLY = "YEARLY", "Anual"

    client = models.ForeignKey("clientes.Client", on_delete=models.CASCADE, related_name="recurring_invoices")
    description = models.CharField(max_length=255)
    frequency = models.CharField(max_length=20, choices=Frequency.choices, default=Frequency.MONTHLY)
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    last_run = models.DateField(null=True, blank=True)
    next_run = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True)
    
    # Template fields
    invoice_type = models.CharField(max_length=8, default="FT")
    currency = models.CharField(max_length=3, default="AOA")
    withholding_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    
    # Auto-issue flag
    auto_issue = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"Recorrente {self.description} - {self.client.name}"

    def calculate_next_run(self):
        if self.frequency == self.Frequency.WEEKLY:
            return self.next_run + relativedelta(weeks=1)
        elif self.frequency == self.Frequency.MONTHLY:
            return self.next_run + relativedelta(months=1)
        elif self.frequency == self.Frequency.QUARTERLY:
            return self.next_run + relativedelta(months=3)
        elif self.frequency == self.Frequency.YEARLY:
            return self.next_run + relativedelta(years=1)
        return self.next_run


class RecurringInvoiceItem(TenantOwnedModel):
    recurring_invoice = models.ForeignKey(RecurringInvoice, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("produtos.Product", on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=18, decimal_places=3)
    price = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    def __str__(self) -> str:
        return f"{self.product.name} x {self.quantity}"
