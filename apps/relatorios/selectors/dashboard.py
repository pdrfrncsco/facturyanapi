from decimal import Decimal

from apps.auditoria.selectors.audit_logs import audit_logs_for_empresa
from apps.empresas.models import Empresa


def dashboard_stats_for_empresa(empresa: Empresa) -> dict:
    recent_activity = audit_logs_for_empresa(empresa)[:10]
    return {
        "totalInvoiced": Decimal("0.00"),
        "revenueCollected": Decimal("0.00"),
        "taxesCollected": Decimal("0.00"),
        "withholdingCollected": Decimal("0.00"),
        "pendingAmount": Decimal("0.00"),
        "draftCount": 0,
        "issuedCount": 0,
        "paidCount": 0,
        "syncSuccessRate": 100,
        "monthlyRevenue": [],
        "categorySales": [],
        "recentActivity": recent_activity,
    }
