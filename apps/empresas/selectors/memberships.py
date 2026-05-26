from django.db.models import QuerySet

from apps.accounts.models import User
from apps.empresas.models import Empresa


def empresas_for_user(user: User) -> QuerySet[Empresa]:
    return Empresa.objects.filter(memberships__user=user, memberships__is_active=True, is_active=True).distinct()


def user_can_access_empresa(user: User, empresa_id: str | None = None, empresa_nif: str | None = None) -> Empresa | None:
    queryset = empresas_for_user(user)
    if empresa_id:
        return queryset.filter(id=empresa_id).first()
    if empresa_nif:
        return queryset.filter(nif=empresa_nif).first()
    return queryset.filter(memberships__is_default=True).first() or queryset.first()
