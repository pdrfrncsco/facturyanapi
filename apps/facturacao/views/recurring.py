from rest_framework import viewsets
from apps.common.permissions import TenantRolePermission
from apps.facturacao.models import RecurringInvoice
from apps.facturacao.serializers.recurring import RecurringInvoiceSerializer, RecurringInvoiceCreateSerializer

class RecurringInvoiceViewSet(viewsets.ModelViewSet):
    permission_classes = [TenantRolePermission]
    role_permissions = {
        "list": TenantRolePermission.ALL_ROLES,
        "retrieve": TenantRolePermission.ALL_ROLES,
        "create": TenantRolePermission.WRITE_ROLES,
        "update": TenantRolePermission.WRITE_ROLES,
        "partial_update": TenantRolePermission.WRITE_ROLES,
        "destroy": TenantRolePermission.WRITE_ROLES,
    }

    def get_queryset(self):
        return RecurringInvoice.objects.filter(empresa=self.request.empresa).select_related('client').prefetch_related('items', 'items__product')

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return RecurringInvoiceCreateSerializer
        return RecurringInvoiceSerializer
