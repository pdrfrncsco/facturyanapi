from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth

from apps.auditoria.selectors.audit_logs import audit_logs_for_empresa
from apps.empresas.models import Empresa
from apps.facturacao.models import Invoice


def dashboard_stats_for_empresa(empresa: Empresa) -> dict:
    recent_activity = audit_logs_for_empresa(empresa)[:10]
    
    invoices = Invoice.objects.filter(empresa=empresa).exclude(status=Invoice.Status.DRAFT)
    drafts = Invoice.objects.filter(empresa=empresa, status=Invoice.Status.DRAFT).count()
    issued = invoices.filter(status__in=[Invoice.Status.ISSUED, Invoice.Status.PARTIAL]).count()
    paid = invoices.filter(status=Invoice.Status.PAID).count()
    
    totals = invoices.aggregate(
        total_invoiced=Sum("grand_total"),
        total_paid=Sum("paid_amount"),
        total_tax=Sum("tax_total"),
        total_withholding=Sum("withholding_tax_amount"),
    )
    
    total_invoiced = totals["total_invoiced"] or Decimal("0.00")
    total_paid = totals["total_paid"] or Decimal("0.00")
    total_tax = totals["total_tax"] or Decimal("0.00")
    total_withholding = totals["total_withholding"] or Decimal("0.00")
    
    pending = total_invoiced - total_paid
    
    # Monthly Revenue for the current year
    from django.utils import timezone
    current_year = timezone.now().year
    
    monthly_data = (
        invoices.filter(issue_date__year=current_year)
        .annotate(month=TruncMonth("issue_date"))
        .values("month")
        .annotate(
            value=Sum("grand_total"),
            tax=Sum("tax_total"),
            count=Count("id")
        )
        .order_by("month")
    )
    
    months = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    monthly_revenue = []
    
    data_dict = {item["month"].month: item for item in monthly_data if item["month"]}
    
    for i in range(1, 13):
        item = data_dict.get(i)
        if item:
            monthly_revenue.append({
                "month": months[i-1],
                "value": item["value"],
                "tax": item["tax"],
                "count": item["count"]
            })
        else:
            monthly_revenue.append({
                "month": months[i-1],
                "value": Decimal("0.00"),
                "tax": Decimal("0.00"),
                "count": 0
            })

    return {
        "totalInvoiced": total_invoiced,
        "revenueCollected": total_paid,
        "taxesCollected": total_tax,
        "withholdingCollected": total_withholding,
        "pendingAmount": pending,
        "draftCount": drafts,
        "issuedCount": issued,
        "paidCount": paid,
        "syncSuccessRate": 100,
        "monthlyRevenue": monthly_revenue,
        "categorySales": [],
        "recentActivity": recent_activity,
    }
