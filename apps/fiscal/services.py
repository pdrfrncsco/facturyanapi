from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from apps.empresas.models import Empresa
from apps.empresas.services.crypto import encrypt_secret
from apps.facturacao.models import AgtSyncLog, FiscalSeries
from apps.fiscal.models import FiscalCertificate, FiscalEvent


class ElectronicBillingStatus:
    NOT_STARTED = "NotStarted"
    ACTIVATION_STARTED = "ActivationStarted"
    CERTIFICATE_MISSING = "CertificateMissing"
    CERTIFICATE_INVALID = "CertificateInvalid"
    SERIES_PENDING = "SeriesPending"
    ACTIVE = "Active"
    ERROR = "Error"


@dataclass(frozen=True)
class FiscalConfigurationState:
    status: str
    can_start_activation: bool
    can_upload_certificate: bool
    can_issue_invoices: bool
    certificate: dict[str, Any]
    series: list[dict[str, Any]]
    last_agt_sync: dict[str, Any] | None
    warnings: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "canStartActivation": self.can_start_activation,
            "canUploadCertificate": self.can_upload_certificate,
            "canIssueInvoices": self.can_issue_invoices,
            "certificate": self.certificate,
            "series": self.series,
            "lastAgtSync": self.last_agt_sync,
            "warnings": self.warnings,
        }


def _certificate_state(*, empresa: Empresa) -> dict[str, Any]:
    try:
        certificate = empresa.fiscal_certificate
    except FiscalCertificate.DoesNotExist:
        return {
            "exists": False,
            "serialNumber": "",
            "issuedAt": None,
            "expiresAt": None,
            "isActive": False,
            "isExpired": False,
            "isValid": False,
        }

    now = timezone.now()
    is_expired = bool(certificate.expires_at and certificate.expires_at <= now)
    has_signing_material = bool(
        certificate.software_private_key
        or certificate.agt_private_key
        or empresa.software_private_key
        or empresa.agt_private_key
    )
    is_valid = bool(certificate.is_active and not is_expired and has_signing_material)
    return {
        "exists": True,
        "serialNumber": certificate.serial_number,
        "issuedAt": certificate.issued_at.isoformat() if certificate.issued_at else None,
        "expiresAt": certificate.expires_at.isoformat() if certificate.expires_at else None,
        "isActive": certificate.is_active,
        "isExpired": is_expired,
        "isValid": is_valid,
    }


def _certificate_subject(cert) -> str:
    return cert.subject.rfc4514_string()


def _certificate_common_name(cert) -> str:
    values = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    return values[0].value if values else ""


def _load_pkcs12_certificate(*, content: bytes, password: str):
    try:
        private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
            content,
            password.encode("utf-8") if password else None,
        )
    except Exception as exc:
        raise ValidationError({"certificate": "Certificado invalido ou password incorreta."}) from exc

    if certificate is None:
        raise ValidationError({"certificate": "O ficheiro nao contem um certificado valido."})
    if private_key is None:
        raise ValidationError({"certificate": "O certificado nao contem chave privada."})
    return private_key, certificate, additional_certificates


def validate_certificate_upload(*, empresa: Empresa, file_name: str, content: bytes, password: str) -> dict[str, Any]:
    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if extension not in {"pfx", "p12"}:
        raise ValidationError({"certificate": "Carregue um ficheiro .pfx ou .p12."})
    if len(content) > 2 * 1024 * 1024:
        raise ValidationError({"certificate": "O certificado nao pode exceder 2MB."})

    private_key, certificate, additional_certificates = _load_pkcs12_certificate(content=content, password=password)
    now = timezone.now()
    not_valid_before = certificate.not_valid_before_utc
    not_valid_after = certificate.not_valid_after_utc
    subject = _certificate_subject(certificate)
    common_name = _certificate_common_name(certificate)
    nif_matches = empresa.nif in subject

    if not_valid_after <= now:
        raise ValidationError({"certificate": "O certificado encontra-se expirado."})
    if not nif_matches:
        raise ValidationError({"certificate": "O certificado nao corresponde ao NIF da empresa."})

    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    return {
        "serialNumber": str(certificate.serial_number),
        "subject": subject,
        "commonName": common_name,
        "issuedAt": not_valid_before,
        "expiresAt": not_valid_after,
        "nifMatches": nif_matches,
        "chainLength": len(additional_certificates or []),
        "privateKeyPem": private_key_pem,
    }


def upload_fiscal_certificate(*, empresa: Empresa, user, certificate_file, password: str) -> FiscalConfigurationState:
    content = certificate_file.read()
    validation = validate_certificate_upload(
        empresa=empresa,
        file_name=certificate_file.name,
        content=content,
        password=password,
    )
    certificate_file.seek(0)

    fiscal_certificate, _ = FiscalCertificate.objects.update_or_create(
        empresa=empresa,
        defaults={
            "certificate_password": encrypt_secret(password),
            "serial_number": validation["serialNumber"],
            "issued_at": validation["issuedAt"],
            "expires_at": validation["expiresAt"],
            "is_active": True,
            "agt_private_key": encrypt_secret(validation["privateKeyPem"]),
        },
    )
    fiscal_certificate.certificate_file.save(certificate_file.name, certificate_file, save=True)

    empresa.agt_private_key = encrypt_secret(validation["privateKeyPem"])
    empresa.save(update_fields=["agt_private_key", "updated_at"])

    FiscalEvent.objects.create(
        empresa=empresa,
        entity_type="empresa",
        entity_id=empresa.id,
        event_type="CERTIFICATE_UPDATED",
        payload={
            "action": "FISCAL_CERTIFICATE_UPLOADED",
            "userId": str(user.id),
            "serialNumber": validation["serialNumber"],
            "subject": validation["subject"],
            "nifMatches": validation["nifMatches"],
            "expiresAt": validation["expiresAt"].isoformat(),
        },
    )
    return get_electronic_billing_state(empresa=empresa)


def _series_state(*, empresa: Empresa) -> list[dict[str, Any]]:
    fiscal_year = timezone.localdate().year
    series = (
        FiscalSeries.objects.filter(empresa=empresa, fiscal_year=fiscal_year)
        .select_related("estabelecimento")
        .order_by("document_type", "code")
    )
    return [
        {
            "id": str(item.id),
            "documentType": item.document_type,
            "code": item.code,
            "fiscalYear": item.fiscal_year,
            "currentNumber": item.current_number,
            "isActive": item.is_active,
            "estabelecimentoId": str(item.estabelecimento_id) if item.estabelecimento_id else None,
            "estabelecimentoCode": item.estabelecimento.code if item.estabelecimento else None,
        }
        for item in series
    ]


def _last_agt_sync(*, empresa: Empresa) -> dict[str, Any] | None:
    sync_log = (
        AgtSyncLog.objects.filter(empresa=empresa)
        .select_related("invoice")
        .order_by("-created_at")
        .first()
    )
    if sync_log is None:
        return None
    return {
        "id": str(sync_log.id),
        "invoiceId": str(sync_log.invoice_id),
        "invoiceNo": sync_log.invoice.invoice_no,
        "status": sync_log.status,
        "responseCode": sync_log.response_code,
        "errorMessage": sync_log.error_message,
        "requestId": sync_log.request_id,
        "createdAt": sync_log.created_at.isoformat(),
        "updatedAt": sync_log.updated_at.isoformat(),
    }


def get_electronic_billing_state(*, empresa: Empresa) -> FiscalConfigurationState:
    warnings: list[str] = []
    certificate = _certificate_state(empresa=empresa)
    series = _series_state(empresa=empresa)
    last_sync = _last_agt_sync(empresa=empresa)

    has_profile = bool(empresa.name and empresa.nif and empresa.address and empresa.city)
    has_series = any(item["isActive"] for item in series)
    has_started = FiscalEvent.objects.filter(
        empresa=empresa,
        entity_type="empresa",
        event_type="CERTIFICATE_UPDATED",
        payload__action="ELECTRONIC_BILLING_ACTIVATION_STARTED",
    ).exists()

    if not has_profile:
        warnings.append("Complete os dados fiscais da empresa antes de iniciar a faturação eletrónica.")
    if settings.AGT_MOCK_SYNC:
        warnings.append("A comunicação AGT está em modo de simulação.")
    if certificate["exists"] and certificate["isExpired"]:
        warnings.append("O certificado fiscal encontra-se expirado.")
    if certificate["exists"] and not certificate["isValid"]:
        warnings.append("O certificado fiscal existe, mas ainda não está válido para emissão.")
    if not has_series:
        warnings.append("Não existe série fiscal ativa para o ano corrente.")

    if not has_started and not certificate["exists"] and not has_series:
        status = ElectronicBillingStatus.NOT_STARTED
    elif not certificate["exists"]:
        status = ElectronicBillingStatus.CERTIFICATE_MISSING if has_started else ElectronicBillingStatus.ACTIVATION_STARTED
    elif not certificate["isValid"]:
        status = ElectronicBillingStatus.CERTIFICATE_INVALID
    elif not has_series:
        status = ElectronicBillingStatus.SERIES_PENDING
    elif last_sync and last_sync["status"] == AgtSyncLog.Status.ERROR:
        status = ElectronicBillingStatus.ERROR
    else:
        status = ElectronicBillingStatus.ACTIVE

    can_start_activation = has_profile and status == ElectronicBillingStatus.NOT_STARTED
    can_upload_certificate = has_profile and status in {
        ElectronicBillingStatus.ACTIVATION_STARTED,
        ElectronicBillingStatus.CERTIFICATE_MISSING,
        ElectronicBillingStatus.CERTIFICATE_INVALID,
    }
    can_issue_invoices = status == ElectronicBillingStatus.ACTIVE

    return FiscalConfigurationState(
        status=status,
        can_start_activation=can_start_activation,
        can_upload_certificate=can_upload_certificate,
        can_issue_invoices=can_issue_invoices,
        certificate=certificate,
        series=series,
        last_agt_sync=last_sync,
        warnings=warnings,
    )


def start_electronic_billing_activation(*, empresa: Empresa, user) -> FiscalConfigurationState:
    FiscalEvent.objects.get_or_create(
        empresa=empresa,
        entity_type="empresa",
        entity_id=empresa.id,
        event_type="CERTIFICATE_UPDATED",
        payload={"action": "ELECTRONIC_BILLING_ACTIVATION_STARTED", "userId": str(user.id)},
    )
    return get_electronic_billing_state(empresa=empresa)
