from apps.auditoria.services.audit_logs import create_audit_log
from apps.empresas.models import Empresa


def request_saft_export(*, empresa: Empresa, user, year: int, month: int, request=None) -> dict:
    create_audit_log(
        empresa=empresa,
        user=user,
        action="EXPORT_SAFT",
        details=f"Pedido de exportação SAF-T (AO) para {year}-{month:02d}.",
        request=request,
        entity_type="saft_export",
    )
    return {
        "filename": f"SAFT_AO_{empresa.nif}_{year}_{month:02d}.xml",
        "status": "queued",
    }
