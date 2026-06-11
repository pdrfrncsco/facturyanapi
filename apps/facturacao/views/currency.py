from rest_framework import viewsets, serializers
from apps.common.permissions import TenantRolePermission
from apps.facturacao.models import ExchangeRate


class ExchangeRateSerializer(serializers.ModelSerializer):
    currencyCode = serializers.CharField(source="currency_code")

    class Meta:
        model = ExchangeRate
        fields = ["id", "currencyCode", "rate", "date"]


class ExchangeRateViewSet(viewsets.ModelViewSet):
    serializer_class = ExchangeRateSerializer
    permission_classes = [TenantRolePermission]
    role_permissions = {
        "list": TenantRolePermission.ALL_ROLES,
        "retrieve": TenantRolePermission.ALL_ROLES,
        "create": TenantRolePermission.FISCAL_MANAGER_ROLES,
        "update": TenantRolePermission.FISCAL_MANAGER_ROLES,
        "partial_update": TenantRolePermission.FISCAL_MANAGER_ROLES,
        "destroy": TenantRolePermission.FISCAL_MANAGER_ROLES,
    }

    def get_queryset(self):
        return ExchangeRate.objects.filter(empresa=self.request.empresa)

    def perform_create(self, serializer):
        serializer.save(empresa=self.request.empresa)
