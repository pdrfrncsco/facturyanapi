import logging
from dataclasses import dataclass
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgtSubmissionResult:
    success: bool
    response_code: str
    response_payload: dict[str, Any]
    error_message: str = ""
    is_transient: bool = False


class AgtClient:
    """
    Cliente AGT isolado para comunicação síncrona com os webservices fiscais.
    Em produção, utiliza SOAP via Zeep ou Requests para os endpoints reais.
    """

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
        """
        Submete o documento para a AGT. 
        Implementação Mock habilitada via AGT_MOCK_SYNC.
        """
        if settings.AGT_MOCK_SYNC:
            return self._mock_submit(payload)
        
        # SKELETON: Real SOAP/REST implementation would go here
        # try:
        #     response = requests.post(f"{settings.AGT_URL}/submit", json=payload, timeout=10)
        #     return AgtSubmissionResult(...)
        # except requests.exceptions.RequestException as e:
        #     return AgtSubmissionResult(success=False, ..., is_transient=True)
        
        return AgtSubmissionResult(
            success=False,
            response_code="NOT_CONFIGURED",
            response_payload={"detail": "Integração AGT real ainda não configurada."},
            error_message="AGT API credentials not configured",
            is_transient=False,
        )

    def _mock_submit(self, payload: dict[str, Any]) -> AgtSubmissionResult:
        import time
        import random
        import sys

        action = payload.get("action", "issue")
        is_testing = "pytest" in sys.modules or "test" in sys.argv

        # Simulate network latency (skip in tests)
        if not is_testing:
            time.sleep(random.uniform(0.1, 0.4))

        # Logic to simulate specific failure scenarios based on NIF for testing
        client_nif = payload.get("clientNif", "")
        
        # NIF ending in '99' simulates a terminal error (Validation Error)
        if client_nif.endswith("99"):
            return AgtSubmissionResult(
                success=False,
                response_code="400_BAD_REQUEST",
                response_payload={"detail": "NIF do adquirente inválido para o regime fiscal selecionado."},
                error_message="Erro de validação estrutural no portal AGT.",
                is_transient=False,
            )

        # 10% chance of random transient failure (Network/500)
        if not is_testing and random.random() < 0.10:
            return AgtSubmissionResult(
                success=False,
                response_code="503_SERVICE_UNAVAILABLE",
                response_payload={"detail": "O servidor da AGT está temporariamente sobrecarregado."},
                error_message="Simulated temporary network/service failure.",
                is_transient=True,
            )

        return AgtSubmissionResult(
            success=True,
            response_code="200_OK",
            response_payload={
                "detail": f"Sincronização AGT simulada com sucesso ({action}).",
                "action": action,
                "mock": True,
            },
        )
