import random
import string
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.facturacao.models import Invoice
from apps.pagamentos.models import MulticaixaReference
from apps.pagamentos.services.settlement import create_settlement_receipt, finalize_settlement

def generate_mock_reference() -> str:
    """Gera uma referência numérica aleatória de 9 dígitos."""
    return "".join(random.choices(string.digits, k=9))

@transaction.atomic
def create_multicaixa_reference(*, invoice: Invoice) -> MulticaixaReference:
    """
    Gera uma referência de pagamento Multicaixa para uma fatura.
    Se já existir uma pendente, retorna-a.
    """
    if hasattr(invoice, "multicaixa_reference"):
        ref = invoice.multicaixa_reference
        if ref.status == MulticaixaReference.Status.PENDING:
            return ref
        
    # Mock de integração com provedor de pagamentos
    entity_code = "00245" 
    reference_number = generate_mock_reference()
    
    reference = MulticaixaReference.objects.create(
        empresa=invoice.empresa,
        invoice=invoice,
        entity_code=entity_code,
        reference_number=reference_number,
        amount=invoice.grand_total,
        status=MulticaixaReference.Status.PENDING,
        expires_at=timezone.now() + timezone.timedelta(days=30)
    )
    
    return reference

@transaction.atomic
def process_payment_notification(*, entity_code: str, reference_number: str, amount: Decimal, transaction_id: str = None) -> MulticaixaReference:
    """
    Processa a notificação de pagamento recebida via webhook.
    Realiza a liquidação automática da fatura associada.
    """
    try:
        ref = MulticaixaReference.objects.select_for_update().get(
            entity_code=entity_code,
            reference_number=reference_number,
            status=MulticaixaReference.Status.PENDING
        )
    except MulticaixaReference.DoesNotExist:
        return None

    # Actualizar estado da referência
    ref.status = MulticaixaReference.Status.PAID
    ref.paid_at = timezone.now()
    ref.provider_id = transaction_id
    ref.save(update_fields=["status", "paid_at", "provider_id"])
    
    # Criar recibo e finalizar liquidação automaticamente
    invoice = ref.invoice
    
    receipt = create_settlement_receipt(
        empresa=invoice.empresa,
        client=invoice.client,
        items_data=[{"invoice_id": invoice.id, "amount": ref.amount}],
        payment_method="TR", 
        notes=f"Pagamento automático Multicaixa Ref: {reference_number}"
    )
    
    # Finalizar liquidação (assinar recibo, disparar webhooks, etc)
    finalize_settlement(receipt=receipt, user=invoice.created_by)
    
    return ref
