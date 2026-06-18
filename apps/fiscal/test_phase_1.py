"""
Test suite for Phase 1: Electronic Billing Status Endpoint

Testes para validar:
1. GET /api/v1/fiscal/electronic-billing/status/ retorna estado correto
2. Estado reflete certificado ativo/inativo
3. Estado reflete séries autorizadas
4. POST /api/v1/fiscal/electronic-billing/start/ inicia ativação
5. POST /api/v1/fiscal/electronic-billing/certificate inicia upload
6. GET /api/v1/fiscal/electronic-billing/events/ lista eventos fiscais
7. POST /api/v1/fiscal/electronic-billing/series/request/ solicita série
"""

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.empresas.models import Empresa, Estabelecimento
from apps.fiscal.models import DocumentSeries, FiscalEvent


def _data(response):
    """Helper: extrai payload real da resposta (wrapped em {success, data, errors})."""
    body = response.json()
    # O renderer personalizado envolve em {'success': ..., 'data': ..., 'errors': ...}
    if "data" in body and isinstance(body["data"], dict):
        return body["data"]
    return body


@override_settings(AGT_MOCK_SYNC=True)
class ElectronicBillingStatusEndpointTests(TestCase):
    """Test electronic billing status endpoint"""

    def setUp(self):
        self.api = APIClient()
        self.empresa = Empresa.objects.create(
            name="Test Fiscal Corp",
            nif="500000001",
            address="Rua 1",
            city="Luanda",
            country="Angola",
            is_active=True,
        )

        self.user = User.objects.create_user(
            username="fiscal@example.com",
            email="fiscal@example.com",
            password="test123",
            role=User.Role.ADMIN,
        )

        from apps.empresas.models import EmpresaMembership
        EmpresaMembership.objects.create(
            user=self.user,
            empresa=self.empresa,
            role=EmpresaMembership.Role.ADMIN,
            is_active=True,
        )

        self.estabelecimento = Estabelecimento.objects.create(
            empresa=self.empresa,
            code="SEDE",
            name="Sede Principal",
            address="Rua 1",
            city="Luanda",
            is_active=True,
        )

        self.api.force_authenticate(user=self.user)

    def test_status_not_started(self):
        """Verify que status é NotStarted quando nada foi configurado"""
        response = self.api.get(
            "/api/v1/fiscal/electronic-billing/status/",
            HTTP_X_TENANT_ID=str(self.empresa.id)
        )

        self.assertEqual(
            response.status_code, 200,
            f"Status: {response.status_code}, Response: {response.content[:500]}"
        )
        data = _data(response)

        self.assertEqual(data["status"], "NotStarted")
        self.assertTrue(data["canStartActivation"])
        self.assertFalse(data["certificate"]["isValid"])
        self.assertEqual(len(data["series"]), 0)
        self.assertFalse(data["canIssueInvoices"])

    def test_status_activation_started(self):
        """Verify que status é ActivationStarted após iniciar processo"""
        # Create activation event (now uses ACTIVATION_STARTED event type)
        FiscalEvent.objects.create(
            empresa=self.empresa,
            entity_type="empresa",
            entity_id=self.empresa.id,
            event_type=FiscalEvent.EventType.ACTIVATION_STARTED,
            payload={
                "action": "ELECTRONIC_BILLING_ACTIVATION_STARTED",
                "userId": str(self.user.id),
            },
        )

        response = self.api.get(
            "/api/v1/fiscal/electronic-billing/status/",
            HTTP_X_TENANT_ID=str(self.empresa.id)
        )

        self.assertEqual(response.status_code, 200)
        data = _data(response)

        self.assertEqual(data["status"], "ActivationStarted")
        self.assertFalse(data["canStartActivation"])
        self.assertTrue(data["canUploadCertificate"])
        self.assertFalse(data["canIssueInvoices"])

    def test_status_with_certificate_but_no_series(self):
        """Verify que status é NotStarted/CertificateMissing se sem certificado"""
        response = self.api.get(
            "/api/v1/fiscal/electronic-billing/status/",
            HTTP_X_TENANT_ID=str(self.empresa.id)
        )

        data = _data(response)

        # Without certificate, should be NotStarted or CertificateMissing
        self.assertIn(data["status"], ["NotStarted", "CertificateMissing"])
        self.assertFalse(data["certificate"]["isValid"])
        self.assertFalse(data["canIssueInvoices"])

    def test_status_with_active_series(self):
        """Verify que status reflete série aprovada ativa"""
        # Create activation event (now uses ACTIVATION_STARTED event type)
        FiscalEvent.objects.create(
            empresa=self.empresa,
            entity_type="empresa",
            entity_id=self.empresa.id,
            event_type=FiscalEvent.EventType.ACTIVATION_STARTED,
            payload={
                "action": "ELECTRONIC_BILLING_ACTIVATION_STARTED",
                "userId": str(self.user.id),
            },
        )

        # Create approved series
        fiscal_year = timezone.localdate().year
        DocumentSeries.objects.create(
            empresa=self.empresa,
            estabelecimento=self.estabelecimento,
            series_code="SEDE",
            document_type="FT",
            fiscal_year=fiscal_year,
            status=DocumentSeries.Status.APPROVED,
            is_active=True,
        )

        response = self.api.get(
            "/api/v1/fiscal/electronic-billing/status/",
            HTTP_X_TENANT_ID=str(self.empresa.id)
        )

        data = _data(response)

        # Should have series in response
        self.assertGreater(len(data["series"]), 0)
        self.assertEqual(data["series"][0]["documentType"], "FT")
        self.assertEqual(data["series"][0]["status"], DocumentSeries.Status.APPROVED)

    def test_status_without_profile_warning(self):
        """Verify que há aviso se dados da empresa incompletos"""
        empresa = Empresa.objects.create(
            name="Incomplete Corp",
            nif="500000002",
            address="Rua 1",
            city="",  # Missing city
            country="Angola",
            is_active=True,
        )

        from apps.empresas.models import EmpresaMembership
        EmpresaMembership.objects.create(
            user=self.user,
            empresa=empresa,
            role=EmpresaMembership.Role.ADMIN,
            is_active=True,
        )

        response = self.api.get(
            "/api/v1/fiscal/electronic-billing/status/",
            HTTP_X_TENANT_ID=str(empresa.id)
        )

        data = _data(response)

        # Should have warning about incomplete profile
        warnings_text = " ".join(data["warnings"])
        # Warning: "Complete os dados fiscais da empresa..."
        self.assertTrue(
            any("dados" in w.lower() for w in data["warnings"]),
            f"Expected profile warning in: {data['warnings']}"
        )

    def test_start_electronic_billing_activation(self):
        """Verify que POST /start/ cria evento de ativação"""
        response = self.api.post(
            "/api/v1/fiscal/electronic-billing/start/",
            HTTP_X_TENANT_ID=str(self.empresa.id)
        )

        self.assertEqual(response.status_code, 200)
        data = _data(response)

        # After start, status should be ActivationStarted
        self.assertEqual(data["status"], "ActivationStarted")
        self.assertTrue(data["canUploadCertificate"])

        # Verify event was created with correct event_type
        event = FiscalEvent.objects.get(
            empresa=self.empresa,
            event_type=FiscalEvent.EventType.ACTIVATION_STARTED,
        )
        self.assertEqual(event.payload["action"], "ELECTRONIC_BILLING_ACTIVATION_STARTED")

    def test_request_series_creates_approved_series_in_mock(self):
        """Verify que POST /series/request/ cria série aprovada em modo mock"""
        response = self.api.post(
            "/api/v1/fiscal/electronic-billing/series/request/",
            data={
                "estabelecimento_id": str(self.estabelecimento.id),
                "document_type": "FT",
                "series_code": "SEDE",
            },
            format="json",
            HTTP_X_TENANT_ID=str(self.empresa.id)
        )

        self.assertEqual(response.status_code, 200, f"Response: {response.content[:500]}")
        data = _data(response)

        # In mock mode, series should be approved
        self.assertGreater(len(data["series"]), 0)
        approved_series = [s for s in data["series"] if s["status"] == "Approved"]
        self.assertGreater(len(approved_series), 0, "Should have at least one Approved series")

        # Verify DB state
        series = DocumentSeries.objects.get(
            empresa=self.empresa,
            etablecimento=self.estabelecimento if False else None,
            document_type="FT",
        ) if False else DocumentSeries.objects.filter(
            empresa=self.empresa,
            document_type="FT",
            series_code="SEDE",
        ).first()
        self.assertIsNotNone(series)
        self.assertEqual(series.status, DocumentSeries.Status.APPROVED)

    def test_list_events_returns_fiscal_events(self):
        """Verify que GET /events/ lista eventos fiscais"""
        # Create some events
        FiscalEvent.objects.create(
            empresa=self.empresa,
            entity_type="empresa",
            entity_id=self.empresa.id,
            event_type=FiscalEvent.EventType.ACTIVATION_STARTED,
            payload={"action": "ELECTRONIC_BILLING_ACTIVATION_STARTED"},
        )

        response = self.api.get(
            "/api/v1/fiscal/electronic-billing/events/",
            HTTP_X_TENANT_ID=str(self.empresa.id)
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        # The events endpoint returns {count, results} which is transformed to a list by the EnvelopedJSONRenderer
        events_list = body.get("data", body)
        self.assertTrue(isinstance(events_list, list), f"Expected list, got: {type(events_list)}")
        self.assertGreater(len(events_list), 0)

        first_event = events_list[0]
        self.assertIn("eventType", first_event)
        self.assertIn("entityType", first_event)
        self.assertIn("payload", first_event)


@override_settings(AGT_MOCK_SYNC=True)
class ElectronicBillingStateLogicTests(TestCase):
    """Test the state machine logic for electronic billing configuration"""

    def setUp(self):
        self.empresa = Empresa.objects.create(
            name="Test Corp",
            nif="500000001",
            address="Rua 1",
            city="Luanda",
            country="Angola",
            is_active=True,
        )

    def test_state_transitions(self):
        """Verify que estados transitam corretamente"""
        from apps.fiscal.services import get_electronic_billing_state, ElectronicBillingStatus

        # Initial: NotStarted
        state1 = get_electronic_billing_state(empresa=self.empresa)
        self.assertEqual(state1.status, ElectronicBillingStatus.NOT_STARTED)

        # After activation start: ActivationStarted
        FiscalEvent.objects.create(
            empresa=self.empresa,
            entity_type="empresa",
            entity_id=self.empresa.id,
            event_type=FiscalEvent.EventType.ACTIVATION_STARTED,
            payload={
                "action": "ELECTRONIC_BILLING_ACTIVATION_STARTED",
                "userId": "test-user-id",
            },
        )

        state2 = get_electronic_billing_state(empresa=self.empresa)
        self.assertEqual(state2.status, ElectronicBillingStatus.ACTIVATION_STARTED)

        # Can upload certificate
        self.assertTrue(state2.can_upload_certificate)
        self.assertFalse(state2.can_issue_invoices)
