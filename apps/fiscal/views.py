from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.common.permissions import TenantRolePermission
from apps.fiscal.models import FiscalEvent
from apps.fiscal.serializers import (
    ElectronicBillingStatusSerializer,
    FiscalCertificateUploadSerializer,
    FiscalEventSerializer,
    FiscalSeriesRequestSerializer,
)
from apps.fiscal.services import (
    get_electronic_billing_state,
    request_series_for_estabelecimento,
    start_electronic_billing_activation,
    upload_fiscal_certificate,
    validate_certificate_only,
)


class ElectronicBillingViewSet(viewsets.GenericViewSet):
    """
    ViewSet para gestão da faturação eletrónica e configuração fiscal.

    Endpoints:
      GET  /status/                 - Estado atual da configuração fiscal
      POST /start/                  - Iniciar processo de ativação
      POST /certificate/            - Carregar e persistir certificado .pfx/.p12
      POST /certificate/validate/   - Validar certificado sem persistir (dry-run)
      POST /series/request/         - Solicitar nova série fiscal à AGT
      GET  /events/                 - Listar eventos fiscais de auditoria
    """

    serializer_class = ElectronicBillingStatusSerializer
    permission_classes = [TenantRolePermission]
    role_permissions = {
        "status": TenantRolePermission.ALL_ROLES,
        "start": TenantRolePermission.FISCAL_MANAGER_ROLES,
        "upload_certificate": TenantRolePermission.FISCAL_MANAGER_ROLES,
        "validate_certificate": TenantRolePermission.FISCAL_MANAGER_ROLES,
        "request_series": TenantRolePermission.FISCAL_MANAGER_ROLES,
        "list_events": TenantRolePermission.AUDIT_READER_ROLES,
    }

    def _raise_drf_validation(self, exc: DjangoValidationError):
        if hasattr(exc, "message_dict"):
            raise ValidationError(exc.message_dict)
        raise ValidationError(exc.messages)

    # -------------------------------------------------------------------------
    # GET /api/v1/fiscal/electronic-billing/status/
    # -------------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="status")
    def status(self, request):
        """Retorna o estado atual da configuração de faturação eletrónica."""
        state = get_electronic_billing_state(empresa=request.empresa)
        serializer = self.get_serializer(state.as_dict())
        return Response(serializer.data)

    # -------------------------------------------------------------------------
    # POST /api/v1/fiscal/electronic-billing/start/
    # -------------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="start")
    def start(self, request):
        """Inicia o processo de ativação da faturação eletrónica."""
        state = start_electronic_billing_activation(empresa=request.empresa, user=request.user)
        serializer = self.get_serializer(state.as_dict())
        return Response(serializer.data, status=status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # POST /api/v1/fiscal/electronic-billing/certificate/
    # -------------------------------------------------------------------------
    @action(
        detail=False,
        methods=["post"],
        url_path="certificate",
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_certificate(self, request):
        """Carrega, valida e persiste um certificado .pfx/.p12."""
        serializer = FiscalCertificateUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            state = upload_fiscal_certificate(
                empresa=request.empresa,
                user=request.user,
                certificate_file=serializer.validated_data["certificate"],
                password=serializer.validated_data.get("password", ""),
            )
        except DjangoValidationError as exc:
            self._raise_drf_validation(exc)
        output = self.get_serializer(state.as_dict())
        return Response(output.data, status=status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # POST /api/v1/fiscal/electronic-billing/certificate/validate/
    # -------------------------------------------------------------------------
    @action(
        detail=False,
        methods=["post"],
        url_path="certificate/validate",
        parser_classes=[MultiPartParser, FormParser],
    )
    def validate_certificate(self, request):
        """
        Valida um certificado .pfx/.p12 sem o persistir (dry-run).
        Retorna metadata: serialNumber, expiresAt, commonName, nifMatches.
        """
        serializer = FiscalCertificateUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = validate_certificate_only(
                empresa=request.empresa,
                certificate_file=serializer.validated_data["certificate"],
                password=serializer.validated_data.get("password", ""),
            )
        except DjangoValidationError as exc:
            self._raise_drf_validation(exc)

        # Exclude raw private key from response; return only displayable metadata
        safe_result = {
            "serialNumber": result["serialNumber"],
            "subject": result["subject"],
            "commonName": result["commonName"],
            "issuedAt": result["issuedAt"].isoformat() if result.get("issuedAt") else None,
            "expiresAt": result["expiresAt"].isoformat() if result.get("expiresAt") else None,
            "nifMatches": result["nifMatches"],
            "chainLength": result["chainLength"],
            "isValid": True,
        }
        return Response(safe_result, status=status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # POST /api/v1/fiscal/electronic-billing/series/request/
    # -------------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="series/request")
    def request_series(self, request):
        """
        Solicita o registo de uma nova série fiscal junto da AGT.
        Em modo mock, aprova automaticamente.
        """
        serializer = FiscalSeriesRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            state = request_series_for_estabelecimento(
                empresa=request.empresa,
                user=request.user,
                estabelecimento_id=str(serializer.validated_data["estabelecimento_id"]),
                document_type=serializer.validated_data["document_type"],
                series_code=serializer.validated_data["series_code"],
            )
        except DjangoValidationError as exc:
            self._raise_drf_validation(exc)

        output = self.get_serializer(state.as_dict())
        return Response(output.data, status=status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # GET /api/v1/fiscal/electronic-billing/events/
    # -------------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="events")
    def list_events(self, request):
        """
        Lista os eventos fiscais de auditoria para a empresa.
        Suporta filtragem por:
          ?entity_type=invoice|empresa|series
          ?event_type=DOCUMENT_CREATED|DOCUMENT_SIGNED|...
          ?limit=50 (default 50, max 200)
        """
        qs = (
            FiscalEvent.objects.filter(empresa=request.empresa)
            .order_by("-created_at")
        )

        entity_type = request.query_params.get("entity_type")
        if entity_type:
            qs = qs.filter(entity_type=entity_type)

        event_type = request.query_params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)

        try:
            limit = min(int(request.query_params.get("limit", 50)), 200)
        except (ValueError, TypeError):
            limit = 50

        events = qs[:limit]
        serializer = FiscalEventSerializer(events, many=True)
        return Response(
            {"count": qs.count(), "results": serializer.data},
            status=status.HTTP_200_OK,
        )
