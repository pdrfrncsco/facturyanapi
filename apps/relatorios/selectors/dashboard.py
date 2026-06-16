from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.auditoria.selectors.audit_logs import audit_logs_for_empresa
from apps.empresas.models import Empresa
from apps.facturacao.models import Invoice, InvoiceItem
from apps.pagamentos.models import ReciboItem


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
    
    # Time window for charts: Current Year
    current_year = timezone.now().year
    
    # 1. Monthly Billing (Area Chart)
    billing_data = (
        invoices.filter(issue_date__year=current_year)
        .annotate(month_date=TruncMonth("issue_date"))
        .values("month_date")
        .annotate(amount=Sum("grand_total"))
        .order_by("month_date")
    )
    
    # 2. Projected vs Realized (Bar Chart)
    # Projected: Based on Due Date
    projected_data = (
        invoices.filter(due_date__year=current_year)
        .annotate(month_date=TruncMonth("due_date"))
        .values("month_date")
        .annotate(amount=Sum("grand_total"))
        .order_by("month_date")
    )
    
    # Realized: Based on Receipt Issue Date
    realized_data = (
        ReciboItem.objects.filter(empresa=empresa, recibo__issue_date__year=current_year, recibo__status="Issued")
        .annotate(month_date=TruncMonth("recibo__issue_date"))
        .values("month_date")
        .annotate(amount=Sum("amount_paid"))
        .order_by("month_date")
    )
    
    months = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    monthly_revenue = []
    
    billing_dict = {item["month_date"].month: item["amount"] for item in billing_data if item["month_date"]}
    projected_dict = {item["month_date"].month: item["amount"] for item in projected_data if item["month_date"]}
    realized_dict = {item["month_date"].month: item["amount"] for item in realized_data if item["month_date"]}
    
    for i in range(1, 13):
        monthly_revenue.append({
            "month": months[i-1],
            "amount": float(billing_dict.get(i, Decimal("0.00"))),
            "projected": float(projected_dict.get(i, Decimal("0.00"))),
            "realized": float(realized_dict.get(i, Decimal("0.00"))),
        })

    # 3. Category Sales (Donut Chart)
    category_data = (
        InvoiceItem.objects.filter(empresa=empresa, invoice__status__in=["Issued", "Paid", "Partial"])
        .values("product__category")
        .annotate(value=Sum("total"))
        .order_by("-value")[:5]
    )
    
    category_sales = [
        {"category": item["product__category"] or "Diversos", "value": float(item["value"])}
        for item in category_data
    ]

    return {
        "totalInvoiced": float(total_invoiced),
        "revenueCollected": float(total_paid),
        "taxesCollected": float(total_tax),
        "withholdingCollected": float(total_withholding),
        "pendingAmount": float(pending),
        "draftCount": drafts,
        "issuedCount": issued,
        "paidCount": paid,
        "syncSuccessRate": 100,
        "monthlyRevenue": monthly_revenue,
        "categorySales": category_sales,
        "recentActivity": recent_activity,
    }
