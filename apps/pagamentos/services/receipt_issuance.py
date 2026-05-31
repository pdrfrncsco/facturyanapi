import hashlib
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.facturacao.models import FiscalSeries, Invoice
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


def receipt_fiscal_hash(*, previous_hash: str, receipt_number: str, receipt_date, total: Decimal, company_nif: str) -> str:
    source = f"{previous_hash}{receipt_number}{receipt_date.isoformat()}{money(total)}{company_nif}"
    return hashlib.sha1(source.encode("utf-8")).hexdigest()


def qr_code_receipt(*, receipt: Recibo) -> str:
    return (
        "https://portaldocontribuinte.minfin.gov.ao/verify"
        f"?doc={receipt.receipt_no}"
        f"&nif={receipt.empresa.nif}"
        f"&total={money(receipt.total_amount)}"
        f"&hash={receipt.receipt_hash}"
    )


@transaction.atomic
def allocate_receipt_number(*, receipt: Recibo) -> str:
    issue_date = timezone.localdate()
    fiscal_year = issue_date.year
    series, _ = FiscalSeries.objects.select_for_update().get_or_create(
        empresa=receipt.empresa,
        document_type="RE",
        fiscal_year=fiscal_year,
        code=str(fiscal_year),
        defaults={"current_number": 0, "is_active": True},
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
        previous_hash=receipt.previous_hash,
        receipt_number=receipt.receipt_no,
        receipt_date=receipt.issue_date,
        total=receipt.total_amount,
        company_nif=receipt.empresa.nif,
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
