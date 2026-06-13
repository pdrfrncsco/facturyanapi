import logging
import uuid
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.common.services.signature import SignatureService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgtSubmissionResult:
    success: bool
    response_code: str
    response_payload: dict[str, Any]
    error_message: str = ""
    is_transient: bool = False
    request_id: str = ""


class AgtClient:
    """
    Cliente AGT isolado para comunicação síncrona com os webservices fiscais.
    Em produção, utiliza SOAP via Zeep ou Requests para os endpoints reais.
    """

    api_version = "v1"

    def _get_software_info(self, empresa):
        info = {
            "productId": "FACTURYAN ERP",
            "productVersion": "1.0.0",
            "softwareValidationNumber": empresa.agt_certificate_no or "0",
        }
        info["jwsSoftwareSignature"] = SignatureService.generate_software_signature(
            empresa=empresa, 
            software_info=info
        )
        return info

    def build_invoice_payload(self, *, invoice) -> dict[str, Any]:
        empresa = invoice.empresa
        
        doc_data = {
            "documentNumber": invoice.invoice_no,
            "companyNif": empresa.nif,
            "documentType": invoice.type,
            "issueDate": invoice.issue_date.isoformat() if invoice.issue_date else None,
            "grandTotal": str(invoice.grand_total),
        }
        
        payload = {
            "submissionUUID": str(uuid.uuid4()),
            "taxRegistrationNumber": empresa.nif,
            "submissionTimeStamp": timezone.now().isoformat(),
            "schemaVersion": self.api_version,
            "action": "issue",
            "document": doc_data,
            "jwsDocumentSignature": SignatureService.generate_document_signature(
                empresa=empresa,
                document_data=doc_data
            ),
            "softwareInfo": self._get_software_info(empresa),
        }
        
        # Final request envelope signature
        envelope_data = {
            "nif": empresa.nif,
            "uuid": payload["submissionUUID"],
            "timestamp": payload["submissionTimeStamp"]
        }
        payload["jwsSignature"] = SignatureService.generate_document_signature(
            empresa=empresa,
            document_data=envelope_data
        )
        
        return payload

    def build_cancellation_payload(self, *, invoice) -> dict[str, Any]:
        empresa = invoice.empresa
        
        doc_data = {
            "action": "cancel",
            "documentType": invoice.type,
            "documentNumber": invoice.invoice_no,
            "cancelledAt": invoice.cancelled_at.isoformat() if invoice.cancelled_at else None,
            "cancellationReason": invoice.cancellation_reason,
        }

        payload = {
            "submissionUUID": str(uuid.uuid4()),
            "taxRegistrationNumber": empresa.nif,
            "submissionTimeStamp": timezone.now().isoformat(),
            "schemaVersion": self.api_version,
            "document": doc_data,
            "jwsDocumentSignature": SignatureService.generate_document_signature(
                empresa=empresa,
                document_data=doc_data
            ),
            "softwareInfo": self._get_software_info(empresa),
        }
        
        return payload

    def request_series(self, *, empresa, estabelecimento, document_type, year) -> AgtSubmissionResult:
        """
        Solicita uma nova série de faturação à AGT via /solicitarSerie.
        """
        request_data = {
            "establishmentCode": estabelecimento.code,
            "documentType": document_type,
            "fiscalYear": year
        }
        
        payload = {
            "submissionUUID": str(uuid.uuid4()),
            "taxRegistrationNumber": empresa.nif,
            "submissionTimeStamp": timezone.now().isoformat(),
            "schemaVersion": self.api_version,
            "action": "solicitarSerie",
            "request": request_data,
            "jwsSignature": SignatureService.generate_document_signature(
                empresa=empresa,
                document_data=request_data
            ),
            "softwareInfo": self._get_software_info(empresa),
        }
        
        return self.submit(payload=payload)

    def get_status(self, *, empresa, request_id) -> AgtSubmissionResult:
        """
        Consulta o estado de processamento de um pedido via /obterEstado.
        """
        payload = {
            "submissionUUID": str(uuid.uuid4()),
            "taxRegistrationNumber": empresa.nif,
            "submissionTimeStamp": timezone.now().isoformat(),
            "schemaVersion": self.api_version,
            "action": "obterEstado",
            "requestID": request_id,
            "softwareInfo": self._get_software_info(empresa),
        }
        
        return self.submit(payload=payload)

    def _get_base_url(self):
        if settings.AGT_ENVIRONMENT == "prod":
            return settings.AGT_API_URL_PROD
        return settings.AGT_API_URL_TEST

    def _get_auth_headers(self):
        import base64
        auth_str = f"{settings.AGT_API_USERNAME}:{settings.AGT_API_PASSWORD}"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        return {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def submit(self, *, payload: dict[str, Any]) -> AgtSubmissionResult:
        """
        Submete o documento para a AGT. 
        Implementação Real com fallback para Mock via AGT_MOCK_SYNC.
        """
        if settings.AGT_MOCK_SYNC:
            return self._mock_submit(payload)
        
        import requests
        
        action = payload.get("action", "issue")
        # No payload de cancelamento, o 'action' pode estar dentro de 'document'
        if action == "issue" and payload.get("document", {}).get("action") == "cancel":
            action = "cancel"

        endpoint_map = {
            "issue": "/sigt/fe/v1/registarFactura",
            "cancel": "/sigt/fe/v1/registarFactura",
            "solicitarSerie": "/sigt/fe/v1/solicitarSerie",
            "obterEstado": "/sigt/fe/v1/obterEstado",
        }
        
        path = endpoint_map.get(action)
        if not path:
            return AgtSubmissionResult(
                success=False,
                response_code="INVALID_ACTION",
                response_payload={},
                error_message=f"Ação AGT desconhecida: {action}",
                is_transient=False,
            )
             
        url = f"{self._get_base_url()}{path}"
        
        try:
            logger.info(f"Enviando pedido AGT '{action}' para {url}")
            response = requests.post(
                url, 
                json=payload, 
                headers=self._get_auth_headers(),
                timeout=30
            )
            
            status_code = response.status_code
            
            try:
                data = response.json()
            except ValueError:
                data = {"raw_content": response.text}

            if status_code >= 500:
                return AgtSubmissionResult(
                    success=False,
                    response_code=str(status_code),
                    response_payload=data,
                    error_message=f"Erro de servidor AGT ({status_code})",
                    is_transient=True
                )
            
            success = status_code in (200, 201, 202)
            error_msg = ""
            if not success:
                error_msg = data.get("detail") or data.get("message") or f"Erro AGT {status_code}"

            return AgtSubmissionResult(
                success=success,
                response_code=str(status_code),
                response_payload=data,
                request_id=data.get("requestID") or data.get("requestId", ""),
                error_message=error_msg,
                is_transient=status_code in (429, 502, 503, 504)
            )
            
        except requests.exceptions.Timeout:
            return AgtSubmissionResult(
                success=False,
                response_code="TIMEOUT",
                response_payload={},
                error_message="Timeout na comunicação com a AGT.",
                is_transient=True
            )
        except requests.exceptions.RequestException as e:
            logger.exception("Erro de comunicação AGT")
            return AgtSubmissionResult(
                success=False,
                response_code="CONNECTION_ERROR",
                response_payload={},
                error_message=f"Erro de conexão com AGT: {str(e)}",
                is_transient=True
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
        doc = payload.get("document", {})
        client_nif = doc.get("clientNif", "")
        
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
                "requestID": str(uuid.uuid4())
            },
            request_id=str(uuid.uuid4())
        )
