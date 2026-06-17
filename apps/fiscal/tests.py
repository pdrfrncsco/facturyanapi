from datetime import timedelta
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.empresas.services.crypto import decrypt_secret
from apps.empresas.models import Empresa, EmpresaMembership, Estabelecimento
from apps.facturacao.models import FiscalSeries
from apps.fiscal.models import FiscalCertificate, FiscalEvent


@override_settings(AGT_MOCK_SYNC=True)
class ElectronicBillingStatusAPITests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.empresa = Empresa.objects.create(
            name="Empresa Fiscal",
            nif="500000001",
            address="Rua 1",
            city="Luanda",
            fiscal_regime="Regime Geral",
        )
        self.user = User.objects.create_user(
            username="finance",
            email="finance@example.com",
            password="pass12345",
            role="Financial_Director",
        )
        EmpresaMembership.objects.create(user=self.user, empresa=self.empresa, role="member", is_default=True)
        self.api.force_authenticate(user=self.user)
        self.api.credentials(HTTP_X_ORGANIZATION_ID=str(self.empresa.id))

    def test_status_initial_contract(self):
        response = self.api.get("/api/v1/fiscal/electronic-billing/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "NotStarted")
        self.assertTrue(response.data["canStartActivation"])
        self.assertFalse(response.data["canIssueInvoices"])
        self.assertFalse(response.data["certificate"]["exists"])
        self.assertEqual(response.data["series"], [])

    def test_start_requires_fiscal_manager_role(self):
        self.user.role = "Billing_Clerk"
        self.user.save(update_fields=["role"])

        response = self.api.post("/api/v1/fiscal/electronic-billing/start/", {}, format="json")

        self.assertEqual(response.status_code, 403)

    def test_start_activation_records_fiscal_event(self):
        response = self.api.post("/api/v1/fiscal/electronic-billing/start/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "CertificateMissing")
        self.assertTrue(response.data["canUploadCertificate"])
        self.assertEqual(
            FiscalEvent.objects.filter(
                empresa=self.empresa,
                entity_type="empresa",
                payload__action="ELECTRONIC_BILLING_ACTIVATION_STARTED",
            ).count(),
            1,
        )

    def test_status_active_when_certificate_and_series_are_ready(self):
        now = timezone.now()
        FiscalCertificate.objects.create(
            empresa=self.empresa,
            serial_number="CERT-001",
            issued_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=365),
            is_active=True,
            software_private_key="configured",
        )
        estabelecimento = Estabelecimento.objects.create(
            empresa=self.empresa,
            code="SEDE",
            name="Sede",
            address="Rua 1",
            city="Luanda",
            is_active=True,
        )
        FiscalSeries.objects.create(
            empresa=self.empresa,
            estabelecimento=estabelecimento,
            code="SEDE",
            document_type="FT",
            fiscal_year=timezone.localdate().year,
            current_number=Decimal("0"),
            is_active=True,
        )

        response = self.api.get("/api/v1/fiscal/electronic-billing/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "Active")
        self.assertTrue(response.data["canIssueInvoices"])
        self.assertTrue(response.data["certificate"]["isValid"])
        self.assertEqual(response.data["series"][0]["documentType"], "FT")

    def _p12_upload(self, *, nif: str = "500000001", password: str = "secret"):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "AO"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Empresa Fiscal"),
                x509.NameAttribute(NameOID.COMMON_NAME, f"Empresa Fiscal {nif}"),
                x509.NameAttribute(NameOID.SERIAL_NUMBER, nif),
            ]
        )
        now = timezone.now()
        certificate = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=365))
            .sign(private_key, hashes.SHA256())
        )
        p12 = pkcs12.serialize_key_and_certificates(
            name=b"agt-cert",
            key=private_key,
            cert=certificate,
            cas=None,
            encryption_algorithm=serialization.BestAvailableEncryption(password.encode("utf-8")),
        )
        return SimpleUploadedFile("certificado.p12", p12, content_type="application/x-pkcs12")

    def test_upload_certificate_accepts_valid_p12_and_encrypts_secret(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.api.post(
                "/api/v1/fiscal/electronic-billing/certificate/",
                {"certificate": self._p12_upload(), "password": "secret"},
                format="multipart",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["certificate"]["isValid"], True)
        self.assertEqual(response.data["status"], "SeriesPending")
        certificate = FiscalCertificate.objects.get(empresa=self.empresa)
        self.assertTrue(certificate.certificate_password.startswith("fernet:"))
        self.assertEqual(decrypt_secret(certificate.certificate_password), "secret")
        self.assertTrue(certificate.agt_private_key.startswith("fernet:"))
        self.empresa.refresh_from_db()
        self.assertTrue(self.empresa.agt_private_key.startswith("fernet:"))

    def test_upload_certificate_rejects_mismatched_nif(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.api.post(
                "/api/v1/fiscal/electronic-billing/certificate/",
                {"certificate": self._p12_upload(nif="599999999"), "password": "secret"},
                format="multipart",
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(FiscalCertificate.objects.filter(empresa=self.empresa).exists())
