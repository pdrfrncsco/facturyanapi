from rest_framework import viewsets
from apps.common.permissions import TenantRolePermission
from apps.empresas.models import Estabelecimento
from rest_framework import serializers


class EstabelecimentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estabelecimento
        fields = ["id", "code", "name", "address", "city", "phone", "email", "is_active"]


class EstabelecimentoViewSet(viewsets.ModelViewSet):
    serializer_class = EstabelecimentoSerializer
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
        return Estabelecimento.objects.filter(empresa=self.request.empresa)

    def perform_create(self, serializer):
        serializer.save(empresa=self.request.empresa)
