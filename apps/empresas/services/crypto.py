import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization


FERNET_PREFIX = "fernet:"


def _fernet() -> Fernet:
    key_source = getattr(settings, "FISCAL_SECRET_KEY", settings.SECRET_KEY)
    digest = hashlib.sha256(key_source.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    if not value or value.startswith(FERNET_PREFIX):
        return value
    token = _fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{FERNET_PREFIX}{token}"


def decrypt_secret(value: str) -> str:
    if not value or not value.startswith(FERNET_PREFIX):
        return value
    token = value.removeprefix(FERNET_PREFIX).encode("utf-8")
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Segredo fiscal encriptado invalido.") from exc


def generate_rsa_key_pair() -> tuple[str, str]:
    """
    Generates a 2048-bit RSA key pair for digital signatures.
    Returns (private_key_pem, public_key_pem) as strings.
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode("utf-8")

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")

    return private_pem, public_pem
