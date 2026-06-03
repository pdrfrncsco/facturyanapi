from decimal import Decimal
from django.db import transaction
from apps.facturacao.models import Invoice
from apps.pagamentos.models import Recibo, ReciboItem
from apps.pagamentos.services.receipt_issuance import issue_receipt
from apps.auditoria.services.audit_logs import create_audit_log


@transaction.atomic
def create_settlement_receipt(*, empresa, client, items_data, payment_method, notes=""):
    """
    items_data: list of dicts with {'invoice_id': UUID, 'amount': Decimal}
    """
    total_amount = sum(Decimal(item['amount']) for item in items_data)
    
    receipt = Recibo.objects.create(
        empresa=empresa,
        client=client,
        total_amount=total_amount,
        payment_method=payment_method,
        status=Recibo.Status.DRAFT,
        notes=notes
    )

    for item in items_data:
        invoice = Invoice.objects.get(pk=item['invoice_id'], empresa=empresa)
        ReciboItem.objects.create(
            empresa=empresa,
            recibo=receipt,
            invoice=invoice,
            amount_paid=Decimal(item['amount'])
        )

    return receipt


@transaction.atomic
def finalize_settlement(*, receipt: Recibo, user=None, request=None):
    """
    Issues the receipt, updates the invoices' paid amounts and statuses, and logs the action.
    """
    issued_receipt = issue_receipt(receipt=receipt)
    
    for item in issued_receipt.items.all():
        invoice = item.invoice
        invoice.paid_amount += item.amount_paid
        
        if invoice.paid_amount >= invoice.grand_total:
            invoice.status = Invoice.Status.PAID
        elif invoice.paid_amount > 0:
            invoice.status = Invoice.Status.PARTIAL
            
        invoice.save(update_fields=["status", "paid_amount", "updated_at"])

    create_audit_log(
        empresa=issued_receipt.empresa,
        user=user,
        action="ISSUE_RECEIPT",
        details=f"Recibo {issued_receipt.receipt_no} emitido para cliente {issued_receipt.client.name}. Total: {issued_receipt.total_amount}",
        request=request,
        entity_type="recibo",
        entity_id=str(issued_receipt.id)
    )
        
    return issued_receipt
