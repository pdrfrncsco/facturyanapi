from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgtSubmissionResult:
    success: bool
    response_code: str
    response_payload: dict[str, Any]
    error_message: str = ""


class AgtClient:
    """Cliente AGT isolado; a implementação real entra na fase Celery/async."""

    api_version = "v1"

    def build_invoice_payload(self, *, invoice) -> dict[str, Any]:
        return {
            "action": "issue",
            "apiVersion": self.api_version,
            "documentType": invoice.type,
            "documentNumber": invoice.invoice_no,
            "issueDate": invoice.issue_date.isoformat() if invoice.issue_date else None,
            "companyNif": invoice.empresa.nif,
            "clientNif": invoice.client_nif,
            "grandTotal": str(invoice.grand_total),
            "invoiceHash": invoice.invoice_hash,
            "qrCode": invoice.qrcode_string,
        }

    def build_cancellation_payload(self, *, invoice) -> dict[str, Any]:
        return {
            "action": "cancel",
            "apiVersion": self.api_version,
            "documentType": invoice.type,
            "documentNumber": invoice.invoice_no,
            "issueDate": invoice.issue_date.isoformat() if invoice.issue_date else None,
            "cancelledAt": invoice.cancelled_at.isoformat() if invoice.cancelled_at else None,
            "companyNif": invoice.empresa.nif,
            "clientNif": invoice.client_nif,
            "grandTotal": str(invoice.grand_total),
            "invoiceHash": invoice.invoice_hash,
            "cancellationReason": invoice.cancellation_reason,
        }

    def submit_invoice(self, *, payload: dict[str, Any]) -> AgtSubmissionResult:
        return AgtSubmissionResult(
            success=False,
            response_code="NOT_CONFIGURED",
            response_payload={"detail": "Integração AGT assíncrona ainda não activada."},
            error_message="AGT async queue not enabled",
        )
