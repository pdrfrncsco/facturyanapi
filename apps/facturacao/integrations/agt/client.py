from dataclasses import dataclass
from typing import Any

from django.conf import settings


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

    def submit(self, *, payload: dict[str, Any]) -> AgtSubmissionResult:
        if settings.AGT_MOCK_SYNC:
            import time
            import random
            import sys

            action = payload.get("action", "issue")
            is_testing = "pytest" in sys.modules or "test" in sys.argv

            # Simulate network latency (skip in tests)
            if not is_testing:
                time.sleep(random.uniform(0.1, 0.5))

            # Simulate random failure (10% chance) to test Celery retries (skip in tests)
            if not is_testing and random.random() < 0.1:
                return AgtSubmissionResult(
                    success=False,
                    response_code="SIMULATED_ERROR",
                    response_payload={"detail": "Falha simulada para teste de retry."},
                    error_message="Simulated temporary network failure.",
                )

            return AgtSubmissionResult(
                success=True,
                response_code="MOCK_OK",
                response_payload={
                    "detail": f"Sincronização AGT simulada ({action}).",
                    "action": action,
                    "mock": True,
                },
            )
        return AgtSubmissionResult(
            success=False,
            response_code="NOT_CONFIGURED",
            response_payload={"detail": "Integração AGT real ainda não configurada."},
            error_message="AGT API credentials not configured",
        )
