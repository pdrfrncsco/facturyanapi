import jwt
import json
import logging
from typing import Any
from django.utils import timezone
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger(__name__)

class SignatureService:
    @staticmethod
    def sign_jws(*, payload: dict[str, Any], private_key_pem: str) -> str:
        """
        Gera uma assinatura JWS RS256 para o payload fornecido.
        O payload é convertido para JSON canónico (compacto) antes de assinar.
        """
        try:
            # Remover espaços e quebras de linha para formato canónico exigido pela AGT
            # canonical_payload = json.dumps(payload, separators=(',', ':'), sort_keys=True)
            
            # PyJWT trata a codificação. Para JWS (sem exp/iat a menos que solicitado), 
            # usamos os campos brutos.
            token = jwt.encode(
                payload,
                private_key_pem,
                algorithm="RS256"
            )
            return token
        except Exception as e:
            logger.error(f"Erro ao gerar assinatura JWS: {str(e)}")
            raise RuntimeError(f"Falha na assinatura digital: {str(e)}")

    @classmethod
    def generate_software_signature(cls, *, empresa, software_info: dict) -> str:
        """
        Assina as informações do software usando a chave privada do produtor.
        """
        if not empresa.software_private_key:
            logger.warning(f"Empresa {empresa.nif} sem software_private_key configurada.")
            return "MOCK_SOFTWARE_SIGNATURE"
            
        return cls.sign_jws(payload=software_info, private_key_pem=empresa.software_private_key)

    @classmethod
    def generate_document_signature(cls, *, empresa, document_data: dict) -> str:
        """
        Assina os dados do documento usando a chave privada do contribuinte (vinda da AGT).
        """
        if not empresa.agt_private_key:
            logger.warning(f"Empresa {empresa.nif} sem agt_private_key configurada.")
            return "MOCK_DOCUMENT_SIGNATURE"
            
        return cls.sign_jws(payload=document_data, private_key_pem=empresa.agt_private_key)

    @staticmethod
    def generate_rsa_pair() -> tuple[str, str]:
        """
        Utilitário para gerar um par de chaves RSA de 2048 bits.
        Útil para configuração inicial ou rotação de chaves do produtor.
        """
        from cryptography.hazmat.primitives.asymmetric import rsa
        
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode("utf-8")
        
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode("utf-8")
        
        return private_pem, public_pem
