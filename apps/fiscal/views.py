from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.common.permissions import TenantRolePermission
from apps.fiscal.serializers import ElectronicBillingStatusSerializer, FiscalCertificateUploadSerializer
from apps.fiscal.services import (
    get_electronic_billing_state,
    start_electronic_billing_activation,
    upload_fiscal_certificate,
)


class ElectronicBillingViewSet(viewsets.GenericViewSet):
    serializer_class = ElectronicBillingStatusSerializer
    permission_classes = [TenantRolePermission]
    role_permissions = {
        "status": TenantRolePermission.ALL_ROLES,
        "start": TenantRolePermission.FISCAL_MANAGER_ROLES,
        "upload_certificate": TenantRolePermission.FISCAL_MANAGER_ROLES,
    }

    def _raise_drf_validation(self, exc: DjangoValidationError):
        if hasattr(exc, "message_dict"):
            raise ValidationError(exc.message_dict)
        raise ValidationError(exc.messages)

    @action(detail=False, methods=["get"], url_path="status")
    def status(self, request):
        state = get_electronic_billing_state(empresa=request.empresa)
        serializer = self.get_serializer(state.as_dict())
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="start")
    def start(self, request):
        state = start_electronic_billing_activation(empresa=request.empresa, user=request.user)
        serializer = self.get_serializer(state.as_dict())
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["post"],
        url_path="certificate",
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_certificate(self, request):
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
