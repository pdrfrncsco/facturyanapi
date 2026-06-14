from celery import shared_task
from django.utils import timezone
from django.db import transaction
from apps.facturacao.models import RecurringInvoice, Invoice
from apps.facturacao.services.invoices import create_draft_invoice, issue_invoice
import logging

logger = logging.getLogger(__name__)

@shared_task(name="process_recurring_invoices")
def process_recurring_invoices():
    today = timezone.localdate()
    recurring_configs = RecurringInvoice.objects.filter(
        is_active=True,
        next_run__lte=today
    ).select_related('empresa', 'client')

    count = 0
    for config in recurring_configs:
        if config.end_date and config.end_date < today:
            config.is_active = False
            config.save(update_fields=['is_active'])
            continue

        try:
            with transaction.atomic():
                # Prepare data for draft creation
                invoice_data = {
                    "client_id": str(config.client_id),
                    "type": config.invoice_type,
                    "currency": config.currency,
                    "withholding_tax_rate": float(config.withholding_tax_rate),
                    "notes": f"{config.notes}\nGerado automaticamente via agendamento recorrente.",
                    "items": []
                }

                for item in config.items.all():
                    invoice_data["items"].append({
                        "product_id": str(item.product_id),
                        "quantity": float(item.quantity),
                        "price": float(item.price) if item.price else float(item.product.price),
                        "discount": float(item.discount)
                    })

                # Create the draft
                # Note: We need a 'user' for create_draft_invoice. 
                # For automated tasks, we'll use the tenant owner or a system user.
                # Assuming the first admin user or owner.
                user = config.empresa.members.filter(membership_role='owner').first() or \
                       config.empresa.members.first()
                
                if not user:
                    logger.error(f"No user found for empresa {config.empresa.name} to process recurring invoice {config.id}")
                    continue

                invoice = create_draft_invoice(
                    empresa=config.empresa,
                    user=user.user,
                    data=invoice_data
                )

                if config.auto_issue:
                    issue_invoice(invoice=invoice, user=user.user)

                # Update recurring config
                config.last_run = today
                config.next_run = config.calculate_next_run()
                config.save(update_fields=['last_run', 'next_run'])
                count += 1
                
        except Exception as e:
            logger.error(f"Error processing recurring invoice {config.id}: {str(e)}")

    return f"Processed {count} recurring invoices."
