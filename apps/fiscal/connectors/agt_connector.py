import requests
import json
from django.conf import settings
from datetime import datetime

class AGTConnector:
    """
    Cliente REST para comunicação com o Webservice da AGT.
    """
    
    def __init__(self, empresa):
        self.empresa = empresa
        self.base_url = getattr(settings, "AGT_API_URL", "https://sifphml.minfin.gov.ao")
        self.username = getattr(settings, "AGT_USERNAME", "PRODUTOR_TESTE")
        self.password = getattr(settings, "AGT_PASSWORD", "PASSWORD_TESTE")
        self.auth = (self.username, self.password)

    def register_invoice(self, invoice, signatures: dict) -> str:
        """
        Submete o documento fiscal à AGT.
        Retorna o requestID para polling.
        """
        payload = {
            "schemaVersion": "1.0",
            "taxRegistrationNumber": self.empresa.nif,
            "submissionTimeStamp": datetime.now().isoformat(),
            "softwareInfo": {
                "productId": "FACTURYAN ERP",
                "version": "1.5.0",
                "certificationNo": self.empresa.agt_certificate_no or "245/AGT/2026",
                "jwsSoftwareSignature": signatures["jwsSoftwareSignature"]
            },
            "document": {
                "id": str(invoice.id),
                "type": invoice.type,
                "number": invoice.invoice_no,
                "date": invoice.issue_date.isoformat(),
                "jwsDocumentSignature": signatures["jwsDocumentSignature"]
            },
            "jwsSignature": signatures["jwsSignature"]
        }

        # Em produção, chamar o endpoint real: /sigt/fe/v1/registarFactura
        # Por agora, simulamos sucesso e retorno de requestID
        return f"REQ-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def get_status(self, request_id: str) -> dict:
        """
        Consulta o estado de processamento de uma submissão.
        """
        # Simulação de resposta da AGT
        return {
            "status": "ACCEPTED", # ACCEPTED, REJECTED, PROCESSING
            "message": "Documento validado com sucesso.",
            "agt_request_id": request_id
        }

    def request_series(self, estabelecimento, doc_type: str) -> dict:
        """
        Solicita uma nova série fiscal à AGT.
        """
        # Simulação
        return {
            "seriesCode": f"{estabelecimento.code[:4]}{datetime.now().year}",
            "agt_registration_id": f"SER-{random_string(8)}"
        }

def random_string(length=8):
    import random
    import string
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
