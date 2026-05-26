from rest_framework.permissions import BasePermission

from apps.empresas.selectors.memberships import user_can_access_empresa


class TenantAccessPermission(BasePermission):
    message = "Empresa inválida ou sem acesso para o utilizador autenticado."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        empresa = user_can_access_empresa(
            user=request.user,
            empresa_id=getattr(request, "tenant_id", None),
            empresa_nif=getattr(request, "tenant_nif", None),
        )
        if empresa is None:
            return False
        request.empresa = empresa
        return True

    def has_object_permission(self, request, view, obj):
        empresa = getattr(request, "empresa", None)
        return bool(empresa and getattr(obj, "empresa_id", None) == empresa.id)
