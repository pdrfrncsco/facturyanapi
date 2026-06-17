from apps.empresas.models import Empresa
from apps.empresas.services.crypto import encrypt_secret, generate_rsa_key_pair

def rotate_empresa_keys(empresa: Empresa) -> Empresa:
    """
    Generates a new RSA key pair for the company and saves it.
    This key is used for the SAF-T hash and JWS signatures.
    """
    private_pem, public_pem = generate_rsa_key_pair()
    empresa.software_private_key = encrypt_secret(private_pem)
    empresa.software_public_key = public_pem
    empresa.save(update_fields=["software_private_key", "software_public_key", "updated_at"])
    return empresa
