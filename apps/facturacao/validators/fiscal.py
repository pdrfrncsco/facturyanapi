from django.core.exceptions import ValidationError

from apps.facturacao.models import FiscalSeries, Invoice


CANCELLABLE_STATUSES = {
    Invoice.Status.ISSUED,
    Invoice.Status.PAID,
    Invoice.Status.PARTIAL,
    Invoice.Status.AGT_SYNCED,
    Invoice.Status.AGT_ERROR,
}


def validate_can_issue_invoice(invoice: Invoice) -> None:
    if invoice.status != Invoice.Status.DRAFT:
        raise ValidationError({"status": "Apenas rascunhos podem ser emitidos fiscalmente."})

    if not invoice.items.exists():
        raise ValidationError({"items": "Nao e possivel emitir uma factura sem linhas."})

    if invoice.grand_total <= 0:
        raise ValidationError({"grandTotal": "O total da factura deve ser superior a zero."})


def validate_fiscal_series_active(series: FiscalSeries) -> None:
    if not series.is_active:
        raise ValidationError({"series": "A serie fiscal seleccionada nao esta activa."})


def validate_can_cancel_invoice(invoice: Invoice, *, reason: str = "") -> None:
    if invoice.status == Invoice.Status.CANCELLED:
        raise ValidationError({"status": "Esta factura ja se encontra cancelada."})

    if invoice.status == Invoice.Status.DRAFT:
        raise ValidationError({"status": "Rascunhos devem ser removidos, nao cancelados fiscalmente."})

    if invoice.status not in CANCELLABLE_STATUSES:
        raise ValidationError({"status": "O estado actual da factura nao permite cancelamento."})

    cleaned_reason = (reason or "").strip()
    if len(cleaned_reason) < 3:
        raise ValidationError({"reason": "Indique o motivo do cancelamento (minimo 3 caracteres)."})
