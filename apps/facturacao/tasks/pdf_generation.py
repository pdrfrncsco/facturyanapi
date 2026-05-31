import logging

from celery import shared_task
from django.db import transaction

from apps.facturacao.models import InvoiceDocument
from apps.facturacao.services.pdf_generation import mark_invoice_pdf_error, store_invoice_pdf

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
    queue="default",
)
def generate_invoice_pdf(self, document_id: str):
    try:
        document = InvoiceDocument.objects.select_related("invoice", "invoice__empresa", "empresa").get(pk=document_id)
        invoice = document.invoice
        with transaction.atomic():
            store_invoice_pdf(document=document, invoice=invoice)
    except Exception as exc:
        logger.exception("PDF generation failed for document %s", document_id)
        document = InvoiceDocument.objects.filter(pk=document_id).first()
        if document:
            mark_invoice_pdf_error(document=document, error_message=str(exc))
        raise exc
