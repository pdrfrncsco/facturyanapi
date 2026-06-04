import logging
from celery import shared_task
from django.utils import timezone
from django.db.models import F
from apps.facturacao.models import Invoice
from apps.notificacoes.services.email import send_payment_reminder

logger = logging.getLogger(__name__)

@shared_task(name="apps.notificacoes.tasks.check_overdue_invoices")
def check_overdue_invoices():
    """
    Task agendada para encontrar facturas vencidas e enviar lembretes.
    """
    today = timezone.localdate()
    
    # Encontrar facturas que venceram hoje ou estão vencidas há pouco tempo
    # Para evitar spam, podemos limitar a facturas que venceram nos últimos 3 dias e ainda não foram pagas
    overdue_invoices = Invoice.objects.filter(
        status__in=[
            Invoice.Status.ISSUED,
            Invoice.Status.PARTIAL,
            Invoice.Status.AGT_SYNCED,
            Invoice.Status.AGT_ERROR
        ],
        due_date__lt=today,
        grand_total__gt=F('paid_amount')
    )
    
    count = 0
    for invoice in overdue_invoices:
        success = send_payment_reminder(invoice=invoice)
        if success:
            count += 1
            
    logger.info(f"Processamento de cobranças concluído. {count} lembretes enviados.")
    return f"{count} lembretes enviados."
