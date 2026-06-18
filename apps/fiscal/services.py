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
from apps.facturacao.models import AgtSyncLog
from apps.fiscal.models import FiscalCertificate, FiscalEvent, DocumentSeries


class ElectronicBillingStatus:
    NOT_STARTED = "NotStarted"
    ACTIVATION_STARTED = "ActivationStarted"
    CERTIFICATE_MISSING = "CertificateMissing"
    CERTIFICATE_INVALID = "CertificateInvalid"
    SERIES_PENDING = "SeriesPending"
    ACTIVE = "Active"
    INACTIVE = "Inactive"
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
        certificate = FiscalCertificate.objects.get(empresa=empresa)
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
        DocumentSeries.objects.filter(empresa=empresa, fiscal_year=fiscal_year)
        .select_related("estabelecimento")
        .order_by("document_type", "series_code")
    )
    return [
        {
            "id": str(item.id),
            "documentType": item.document_type,
            "code": item.series_code,
            "fiscalYear": item.fiscal_year,
            "currentNumber": item.current_number,
            "isActive": item.is_active,
            "status": item.status,
            "agtRegistrationId": item.agt_registration_id,
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
    has_approved_series = any(
        item["isActive"] and item["status"] == DocumentSeries.Status.APPROVED
        for item in series
    )
    has_any_series = bool(series)
    has_started = FiscalEvent.objects.filter(
        empresa=empresa,
        entity_type="empresa",
        event_type=FiscalEvent.EventType.ACTIVATION_STARTED,
    ).exists()

    if not has_profile:
        warnings.append("Complete os dados fiscais da empresa antes de iniciar a faturação eletrónica.")
    if settings.AGT_MOCK_SYNC:
        warnings.append("A comunicação AGT está em modo de simulação.")
    if certificate["exists"] and certificate["isExpired"]:
        warnings.append("O certificado fiscal encontra-se expirado.")
    if certificate["exists"] and not certificate["isValid"]:
        warnings.append("O certificado fiscal existe, mas ainda não está válido para emissão.")
    if not has_approved_series:
        warnings.append("Não existe série fiscal aprovada e ativa para o ano corrente.")

    if not has_started and not certificate["exists"] and not has_any_series:
        status = ElectronicBillingStatus.NOT_STARTED
    elif not certificate["exists"]:
        # has_started=True means user clicked "Iniciar Processo" → prompt to upload cert
        # has_started=False with no cert is an edge case (shouldn't normally occur after NOT_STARTED)
        status = ElectronicBillingStatus.ACTIVATION_STARTED if has_started else ElectronicBillingStatus.CERTIFICATE_MISSING
    elif not certificate["isValid"]:
        status = ElectronicBillingStatus.CERTIFICATE_INVALID
    elif not has_approved_series:
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
        event_type=FiscalEvent.EventType.ACTIVATION_STARTED,
        defaults={"payload": {"action": "ELECTRONIC_BILLING_ACTIVATION_STARTED", "userId": str(user.id)}},
    )
    return get_electronic_billing_state(empresa=empresa)


def request_series_for_estabelecimento(
    *,
    empresa: Empresa,
    user,
    estabelecimento_id: str,
    document_type: str,
    series_code: str,
) -> FiscalConfigurationState:
    """Solicita (ou re-solicita) o registo de uma série fiscal junto da AGT."""
    from apps.empresas.models import Estabelecimento
    from apps.facturacao.integrations.agt.client import AgtClient

    try:
        estabelecimento = Estabelecimento.objects.get(pk=estabelecimento_id, empresa=empresa)
    except Estabelecimento.DoesNotExist:
        from django.core.exceptions import ValidationError as DjangoValidationError
        raise DjangoValidationError({"estabelecimento_id": "Estabelecimento não encontrado."})

    fiscal_year = timezone.localdate().year

    series, created = DocumentSeries.objects.get_or_create(
        empresa=empresa,
        estabelecimento=estabelecimento,
        document_type=document_type,
        fiscal_year=fiscal_year,
        series_code=series_code,
        defaults={"current_number": 0, "is_active": True, "status": DocumentSeries.Status.DRAFT},
    )

    # Only request if not already approved
    if series.status == DocumentSeries.Status.APPROVED:
        return get_electronic_billing_state(empresa=empresa)

    series.status = DocumentSeries.Status.REQUESTED
    series.save(update_fields=["status", "updated_at"])

    FiscalEvent.objects.create(
        empresa=empresa,
        entity_type="series",
        entity_id=series.id,
        event_type=FiscalEvent.EventType.DOCUMENT_CREATED,
        payload={
            "action": "SERIES_REQUESTED",
            "userId": str(user.id),
            "seriesCode": series_code,
            "documentType": document_type,
            "fiscalYear": fiscal_year,
        },
    )

    client = AgtClient()
    result = client.request_series(
        empresa=empresa,
        estabelecimento=estabelecimento,
        document_type=document_type,
        year=fiscal_year,
    )

    if result.success:
        series.status = DocumentSeries.Status.APPROVED
        series.agt_registration_id = result.request_id
        series.save(update_fields=["status", "agt_registration_id", "updated_at"])

        FiscalEvent.objects.create(
            empresa=empresa,
            entity_type="series",
            entity_id=series.id,
            event_type=FiscalEvent.EventType.DOCUMENT_ACCEPTED,
            payload={
                "action": "SERIES_APPROVED",
                "agtRegistrationId": result.request_id,
                "responseCode": result.response_code,
            },
            agt_request_id=result.request_id,
        )
    else:
        series.status = DocumentSeries.Status.REJECTED
        series.save(update_fields=["status", "updated_at"])

        FiscalEvent.objects.create(
            empresa=empresa,
            entity_type="series",
            entity_id=series.id,
            event_type=FiscalEvent.EventType.DOCUMENT_REJECTED,
            payload={
                "action": "SERIES_REJECTED",
                "errorMessage": result.error_message,
                "responseCode": result.response_code,
            },
        )

        if not settings.AGT_MOCK_SYNC:
            from django.core.exceptions import ValidationError as DjangoValidationError
            raise DjangoValidationError({"series": f"Falha ao registar série na AGT: {result.error_message}"})

    return get_electronic_billing_state(empresa=empresa)


def validate_certificate_only(
    *,
    empresa: Empresa,
    certificate_file,
    password: str,
) -> dict[str, Any]:
    """Valida um certificado .pfx/.p12 sem o persistir. Retorna metadata do certificado."""
    content = certificate_file.read()
    return validate_certificate_upload(
        empresa=empresa,
        file_name=certificate_file.name,
        content=content,
        password=password,
    )
