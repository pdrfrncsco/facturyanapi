import hmac
import hashlib
import json
import requests
from django.conf import settings
from celery import shared_task
from .models import WebhookConfig, WebhookLog

def generate_signature(payload, secret):
    return hmac.new(
        secret.encode('utf-8'),
        json.dumps(payload).encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

@shared_task(name="dispatch_webhook_event")
def dispatch_webhook_event(empresa_id, event_type, payload):
    webhooks = WebhookConfig.objects.filter(empresa_id=empresa_id, is_active=True)
    
    # Filter by specific event
    event_field_map = {
        "invoice.issued": "event_invoice_issued",
        "invoice.paid": "event_invoice_paid",
        "invoice.cancelled": "event_invoice_cancelled",
        "receipt.issued": "event_receipt_issued",
    }
    
    field_name = event_field_map.get(event_type)
    if field_name:
        webhooks = webhooks.filter(**{field_name: True})

    for webhook in webhooks:
        signature = generate_signature(payload, webhook.secret_key)
        headers = {
            "Content-Type": "application/json",
            "X-Facturyan-Event": event_type,
            "X-Facturyan-Signature": signature,
        }
        
        try:
            response = requests.post(
                webhook.url, 
                json=payload, 
                headers=headers, 
                timeout=10
            )
            success = response.status_code >= 200 and response.status_code < 300
            
            WebhookLog.objects.create(
                empresa_id=empresa_id,
                webhook=webhook,
                event_type=event_type,
                payload=payload,
                response_status=response.status_code,
                response_body=response.text[:1000],
                success=success
            )
        except Exception as e:
            WebhookLog.objects.create(
                empresa_id=empresa_id,
                webhook=webhook,
                event_type=event_type,
                payload=payload,
                response_body=str(e),
                success=False
            )

def trigger_webhook(empresa_id, event_type, payload):
    """
    Trigger webhook dispatching (async via Celery).
    """
    dispatch_webhook_event.delay(empresa_id, event_type, payload)
