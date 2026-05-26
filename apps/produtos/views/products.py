from rest_framework import status, viewsets
from rest_framework.response import Response

from apps.common.permissions import TenantRolePermission
from apps.produtos.selectors.products import products_for_empresa
from apps.produtos.serializers.products import ProductSerializer
from apps.produtos.services.products import create_product, delete_product, update_product


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [TenantRolePermission]
    role_permissions = {
        "list": TenantRolePermission.ALL_ROLES,
        "retrieve": TenantRolePermission.ALL_ROLES,
        "create": TenantRolePermission.WRITE_ROLES,
        "update": TenantRolePermission.WRITE_ROLES,
        "partial_update": TenantRolePermission.WRITE_ROLES,
        "destroy": TenantRolePermission.FISCAL_MANAGER_ROLES,
    }
    search_fields = ["code", "name", "category"]
    ordering_fields = ["code", "name", "price", "created_at"]
    ordering = ["code"]
    filterset_fields = ["category", "unit", "tax_rate"]

    def get_queryset(self):
        return products_for_empresa(self.request.empresa)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = create_product(
            empresa=request.empresa,
            user=request.user,
            data=serializer.validated_data,
            request=request,
        )
        return Response(self.get_serializer(product).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        product = update_product(
            product=self.get_object(),
            user=request.user,
            data=serializer.validated_data,
            request=request,
        )
        return Response(self.get_serializer(product).data)

    def perform_destroy(self, instance):
        delete_product(product=instance, user=self.request.user, request=self.request)
