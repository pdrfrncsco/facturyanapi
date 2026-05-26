from django.db.models import QuerySet

from apps.auditoria.models import AuditLog
from apps.empresas.models import Empresa


def audit_logs_for_empresa(empresa: Empresa) -> QuerySet[AuditLog]:
    return AuditLog.objects.filter(empresa=empresa).select_related("user", "empresa")
