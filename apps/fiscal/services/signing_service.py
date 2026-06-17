import jwt
import base64
from datetime import datetime
from cryptography.hazmat.primitives import serialization
from apps.fiscal.models import FiscalCertificate

class SigningService:
    def __init__(self, empresa):
        self.empresa = empresa
        self.certificate = self._get_active_certificate()

    def _get_active_certificate(self):
        try:
            return self.empresa.fiscal_certificate
        except FiscalCertificate.DoesNotExist:
            return None

    def sign_invoice(self, invoice) -> dict:
        """
        Gera o envelope de assinaturas JWS (RS256) exigido pela AGT.
        """
        if not self.certificate or not self.certificate.software_private_key:
            raise ValueError(f"Empresa {self.empresa.name} não possui chaves de assinatura configuradas.")

        # Carregar chave privada
        private_key = serialization.load_pem_private_key(
            self.certificate.software_private_key.encode('utf-8'),
            password=None
        )

        # 1. jwsDocumentSignature: Assina dados fiscais do documento
        doc_payload = {
            "documentNo": invoice.invoice_no,
            "issueDate": invoice.issue_date.isoformat(),
            "clientNif": invoice.client_nif,
            "grandTotal": f"{invoice.grand_total:.2f}",
            "hash": invoice.invoice_hash,
            "iat": int(datetime.now().timestamp())
        }
        jws_document = jwt.encode(doc_payload, private_key, algorithm="RS256")

        # 2. jwsSoftwareSignature: Assina dados do software produtor
        soft_payload = {
            "productId": "FACTURYAN ERP",
            "version": "1.5.0",
            "certificationNo": self.empresa.agt_certificate_no or "245/AGT/2026",
            "iat": int(datetime.now().timestamp())
        }
        jws_software = jwt.encode(soft_payload, private_key, algorithm="RS256")

        # 3. jwsSignature: Assina o envelope da requisição (Envelope Fiscal)
        envelope_payload = {
            "taxRegistrationNumber": self.empresa.nif,
            "submissionTimeStamp": datetime.now().isoformat(),
            "documentId": str(invoice.id),
            "iat": int(datetime.now().timestamp())
        }
        jws_envelope = jwt.encode(envelope_payload, private_key, algorithm="RS256")

        return {
            "jwsDocumentSignature": jws_document,
            "jwsSoftwareSignature": jws_software,
            "jwsSignature": jws_envelope
        }
