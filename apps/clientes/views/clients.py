from rest_framework import status, viewsets
from rest_framework.response import Response

from apps.clientes.selectors.clients import clients_for_empresa
from apps.clientes.serializers.clients import ClientSerializer
from apps.clientes.services.clients import create_client, delete_client, update_client
from apps.common.permissions import TenantRolePermission


class ClientViewSet(viewsets.ModelViewSet):
    serializer_class = ClientSerializer
    permission_classes = [TenantRolePermission]
    role_permissions = {
        "list": TenantRolePermission.ALL_ROLES,
        "retrieve": TenantRolePermission.ALL_ROLES,
        "create": TenantRolePermission.WRITE_ROLES,
        "update": TenantRolePermission.WRITE_ROLES,
        "partial_update": TenantRolePermission.WRITE_ROLES,
        "destroy": TenantRolePermission.FISCAL_MANAGER_ROLES,
    }
    search_fields = ["name", "nif", "email"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
    filterset_fields = ["city", "country"]

    def get_queryset(self):
        return clients_for_empresa(self.request.empresa)

    def perform_create(self, serializer):
        self.instance = create_client(
            empresa=self.request.empresa,
            user=self.request.user,
            data=serializer.validated_data,
            request=self.request,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(self.get_serializer(self.instance).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        self.instance = update_client(
            client=self.get_object(),
            user=self.request.user,
            data=serializer.validated_data,
            request=self.request,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(self.get_serializer(self.instance).data)

    def perform_destroy(self, instance):
        delete_client(client=instance, user=self.request.user, request=self.request)
