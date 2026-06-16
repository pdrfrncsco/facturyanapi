from decimal import Decimal
from django.db import transaction
from apps.facturacao.models import Invoice
from apps.pagamentos.models import Recibo, ReciboItem
from apps.pagamentos.services.receipt_issuance import issue_receipt
from apps.auditoria.services.audit_logs import create_audit_log
from apps.integracoes.services import trigger_webhook


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
        
        old_status = invoice.status
        if invoice.paid_amount >= invoice.grand_total:
            invoice.status = Invoice.Status.PAID
        elif invoice.paid_amount > 0:
            invoice.status = Invoice.Status.PARTIAL
            
        invoice.save(update_fields=["status", "paid_amount", "updated_at"])
        
        # Webhook for invoice status change (paid/partial)
        if invoice.status != old_status and invoice.status == Invoice.Status.PAID:
            trigger_webhook(
                empresa_id=invoice.empresa_id,
                event_type="invoice.paid",
                payload={
                    "id": str(invoice.id),
                    "invoiceNo": invoice.invoice_no,
                    "paidAmount": float(invoice.paid_amount),
                    "grandTotal": float(invoice.grand_total),
                    "status": invoice.status
                }
            )

    create_audit_log(
        empresa=issued_receipt.empresa,
        user=user,
        action="ISSUE_RECEIPT",
        details=f"Recibo {issued_receipt.receipt_no} emitido para cliente {issued_receipt.client.name}. Total: {issued_receipt.total_amount}",
        request=request,
        entity_type="recibo",
        entity_id=str(issued_receipt.id)
    )

    # Webhook for receipt
    trigger_webhook(
        empresa_id=issued_receipt.empresa_id,
        event_type="receipt.issued",
        payload={
            "id": str(issued_receipt.id),
            "receiptNo": issued_receipt.receipt_no,
            "clientName": issued_receipt.client.name,
            "totalAmount": float(issued_receipt.total_amount),
            "paymentMethod": issued_receipt.payment_method,
            "status": issued_receipt.status
        }
    )
        
    return issued_receipt


@transaction.atomic
def cancel_receipt(*, receipt: Recibo, user=None, request=None):
    if receipt.status == Recibo.Status.CANCELLED:
        return receipt
    
    receipt.status = Recibo.Status.CANCELLED
    receipt.save(update_fields=["status", "updated_at"])

    for item in receipt.items.all():
        invoice = item.invoice
        invoice.paid_amount -= item.amount_paid
        
        if invoice.paid_amount <= 0:
            invoice.status = Invoice.Status.ISSUED
            invoice.paid_amount = Decimal("0.00")
        else:
            invoice.status = Invoice.Status.PARTIAL
            
        invoice.save(update_fields=["status", "paid_amount", "updated_at"])

    create_audit_log(
        empresa=receipt.empresa,
        user=user,
        action="CANCEL_RECEIPT",
        details=f"Recibo {receipt.receipt_no} cancelado. Estornos realizados nas facturas associadas.",
        request=request,
        entity_type="recibo",
        entity_id=str(receipt.id)
    )

    trigger_webhook(
        empresa_id=receipt.empresa_id,
        event_type="receipt.cancelled",
        payload={
            "id": str(receipt.id),
            "receiptNo": receipt.receipt_no,
            "status": receipt.status
        }
    )

    return receipt
