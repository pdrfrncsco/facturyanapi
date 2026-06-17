import hashlib
import json
from decimal import Decimal

class HashService:
    @staticmethod
    def compute_chain_hash(invoice) -> str:
        """
        Gera o hash encadeado (SHA-256) conforme normas da AGT.
        Inclui dados do documento actual e o hash do documento anterior da mesma série.
        """
        # Formatar dados para formato canónico (JSON sem espaços)
        fields = {
            "invoiceNo": invoice.invoice_no,
            "issueDate": invoice.issue_date.isoformat() if hasattr(invoice.issue_date, 'isoformat') else str(invoice.issue_date),
            "clientNif": invoice.client_nif,
            "grandTotal": f"{invoice.grand_total:.2f}",
            "previousHash": invoice.previous_hash or "",
        }
        
        # Gerar string canónica ordenada por chaves
        canonical_str = json.dumps(fields, sort_keys=True, separators=(',', ':'))
        
        # Calcular SHA-256
        return hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()
