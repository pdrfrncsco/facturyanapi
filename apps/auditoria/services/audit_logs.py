from django.contrib.auth import get_user_model
from django.http import HttpRequest

from apps.auditoria.models import AuditLog
from apps.empresas.models import Empresa


def create_audit_log(
    *,
    empresa: Empresa,
    user,
    action: str,
    details: str,
    request: HttpRequest | None = None,
    entity_type: str = "",
    entity_id: str = "",
) -> AuditLog:
    ip_address = None
    if request is not None:
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else request.META.get("REMOTE_ADDR")

    user_model = get_user_model()
    authenticated_user = user if isinstance(user, user_model) and user.is_authenticated else None
    user_name = authenticated_user.get_full_name() or authenticated_user.username if authenticated_user else ""

    return AuditLog.objects.create(
        empresa=empresa,
        user=authenticated_user,
        user_name=user_name,
        action=action,
        details=details,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=ip_address,
    )
