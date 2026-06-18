from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone

from apps.facturacao.models import Invoice
from apps.fiscal.models import DocumentSeries


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

    if settings.AGT_MOCK_SYNC:
        return

    try:
        certificate = invoice.empresa.fiscal_certificate
    except Exception:
        raise ValidationError({"certificate": "Configure um certificado fiscal valido antes de emitir."})

    has_private_key = bool(certificate.agt_private_key or invoice.empresa.agt_private_key)
    if not certificate.is_active or not has_private_key:
        raise ValidationError({"certificate": "O certificado fiscal nao esta ativo ou nao contem chave privada."})
    if certificate.expires_at and certificate.expires_at <= timezone.now():
        raise ValidationError({"certificate": "O certificado fiscal encontra-se expirado."})


def validate_fiscal_series_active(series: DocumentSeries) -> None:
    if not series.is_active:
        raise ValidationError({"series": "A serie fiscal seleccionada nao esta activa."})
    if series.status != DocumentSeries.Status.APPROVED:
        raise ValidationError({"series": f"A serie fiscal encontra-se em estado {series.get_status_display()}. Apenas series aprovadas podem emitir."})


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
