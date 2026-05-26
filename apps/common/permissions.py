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


class TenantRolePermission(TenantAccessPermission):
    """Tenant permission with a small role matrix per view/action."""

    message = "O utilizador não tem permissão para executar esta operação."

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    ALL_ROLES = {
        "Admin",
        "Financial_Director",
        "Billing_Clerk",
        "Auditor",
    }
    WRITE_ROLES = {
        "Admin",
        "Financial_Director",
        "Billing_Clerk",
    }
    FISCAL_MANAGER_ROLES = {
        "Admin",
        "Financial_Director",
    }
    AUDIT_READER_ROLES = {
        "Admin",
        "Financial_Director",
        "Auditor",
    }

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return self._role_allowed(request, view)

    def _role_allowed(self, request, view) -> bool:
        user_role = getattr(request.user, "role", None)
        allowed_roles = self._allowed_roles_for_request(request, view)
        return user_role in allowed_roles

    def _allowed_roles_for_request(self, request, view) -> set[str]:
        role_matrix = getattr(view, "role_permissions", None)
        if role_matrix:
            action = getattr(view, "action", None) or request.method.lower()
            if action in role_matrix:
                return set(role_matrix[action])

        if request.method in self.SAFE_METHODS:
            return set(getattr(view, "read_roles", self.ALL_ROLES))
        return set(getattr(view, "write_roles", self.WRITE_ROLES))
