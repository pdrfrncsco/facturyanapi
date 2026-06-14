from django.db import models
from apps.common.models import TenantOwnedModel

class WebhookConfig(TenantOwnedModel):
    url = models.URLField(max_length=500)
    secret_key = models.CharField(max_length=255, help_text="Usada para assinar o payload (HMAC)")
    is_active = models.BooleanField(default=True)
    
    # Events selection
    event_invoice_issued = models.BooleanField(default=True)
    event_invoice_paid = models.BooleanField(default=True)
    event_invoice_cancelled = models.BooleanField(default=True)
    event_receipt_issued = models.BooleanField(default=True)

    def __str__(self):
        return f"Webhook for {self.empresa.name}: {self.url}"

class WebhookLog(TenantOwnedModel):
    webhook = models.ForeignKey(WebhookConfig, on_delete=models.CASCADE, related_name="logs")
    event_type = models.CharField(max_length=50)
    payload = models.JSONField()
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(null=True, blank=True)
    success = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Log {self.event_type} - {self.timestamp}"
