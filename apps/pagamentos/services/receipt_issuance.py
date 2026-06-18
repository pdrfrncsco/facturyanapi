import hashlib
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.facturacao.models import Invoice
from apps.fiscal.models import DocumentSeries
from apps.facturacao.services.decimal_utils import money
from apps.pagamentos.models import Recibo


def receipt_fiscal_number(*, fiscal_year: int, sequence: int) -> str:
    return f"RE {fiscal_year}/{sequence:06d}"


def previous_receipt_hash(*, empresa, receipt: Recibo) -> str:
    previous = (
        Recibo.objects.filter(empresa=empresa)
        .exclude(pk=receipt.pk)
        .exclude(receipt_hash="")
        .order_by("-issue_date", "-created_at")
        .first()
    )
    return previous.receipt_hash if previous else ""


from apps.facturacao.services.fiscal_issuance import sign_string

def receipt_fiscal_hash(*, empresa, previous_hash: str, receipt_number: str, receipt_date, system_date, total: Decimal) -> str:
    receipt_date_str = receipt_date.strftime("%Y-%m-%d")
    system_date_str = system_date.strftime("%Y-%m-%dT%H:%M:%S")
    total_str = f"{total:.2f}"
    
    source = f"{receipt_date_str};{system_date_str};{receipt_number};{total_str};{previous_hash}"
    return sign_string(empresa.software_private_key, source)


def qr_code_receipt(*, receipt: Recibo) -> str:
    return (
        f"A:{receipt.empresa.nif}*"
        f"B:{receipt.receipt_no}*"
        f"C:{receipt.issue_date.strftime('%Y-%m-%d')}*"
        f"D:0.00*"
        f"E:{receipt.total_amount:.2f}*"
        f"F:{receipt.receipt_hash[:10]}*"
        f"G:{receipt.receipt_hash[-10:]}"
    )


@transaction.atomic
def allocate_receipt_number(*, receipt: Recibo) -> str:
    issue_date = timezone.localdate()
    fiscal_year = issue_date.year
    
    from apps.empresas.models import Estabelecimento
    estabelecimento = Estabelecimento.objects.filter(empresa=receipt.empresa, code="SEDE").first() or \
                      Estabelecimento.objects.filter(empresa=receipt.empresa).first()
    
    if not estabelecimento:
        estabelecimento = Estabelecimento.objects.create(
            empresa=receipt.empresa,
            code="SEDE",
            name="Sede Principal",
            address=receipt.empresa.address or "Rua Sede",
            city=receipt.empresa.city or "Luanda",
            is_active=True
        )

    series, _ = DocumentSeries.objects.select_for_update().get_or_create(
        empresa=receipt.empresa,
        estabelecimento=estabelecimento,
        document_type="RE",
        fiscal_year=fiscal_year,
        series_code=str(fiscal_year),
        defaults={"current_number": 0, "is_active": True, "status": DocumentSeries.Status.APPROVED},
    )
    
    series.current_number += 1
    series.save(update_fields=["current_number", "updated_at"])

    return receipt_fiscal_number(
        fiscal_year=fiscal_year,
        sequence=series.current_number,
    )


@transaction.atomic
def issue_receipt(*, receipt: Recibo) -> Recibo:
    if receipt.status != Recibo.Status.DRAFT:
        raise ValueError("Apenas recibos em rascunho podem ser emitidos.")
    
    if receipt.total_amount <= 0:
        raise ValueError("O valor total do recibo deve ser superior a zero.")

    receipt.receipt_no = allocate_receipt_number(receipt=receipt)
    receipt.issue_date = timezone.localdate()
    receipt.previous_hash = previous_receipt_hash(empresa=receipt.empresa, receipt=receipt)
    receipt.receipt_hash = receipt_fiscal_hash(
        empresa=receipt.empresa,
        previous_hash=receipt.previous_hash,
        receipt_number=receipt.receipt_no,
        receipt_date=receipt.issue_date,
        system_date=timezone.now(),
        total=receipt.total_amount,
    )
    receipt.qrcode_string = qr_code_receipt(receipt=receipt)
    receipt.status = Recibo.Status.ISSUED
    receipt.save()

    # Update related invoices
    for item in receipt.items.all():
        invoice = item.invoice
        # Here we could update a 'paid_amount' field on Invoice if it existed
        # For now, let's assume we check if fully paid
        # This logic will be expanded in a settlement service
        pass

    return receipt
