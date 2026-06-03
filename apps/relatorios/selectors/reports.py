from decimal import Decimal
from django.db.models import Sum

from apps.empresas.models import Empresa
from apps.facturacao.models import Invoice, InvoiceItem
from apps.pagamentos.models import Recibo


def generate_iva_map(empresa: Empresa, year: int, month: int) -> dict:
    invoices = Invoice.objects.filter(
        empresa=empresa,
        issue_date__year=year,
        issue_date__month=month,
    ).exclude(status=Invoice.Status.DRAFT)
    
    total_sales = invoices.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
    total_tax = invoices.aggregate(total=Sum('tax_total'))['total'] or Decimal('0.00')
    
    items = InvoiceItem.objects.filter(invoice__in=invoices)
    
    # Agrupar por taxa de IVA
    tax_rates = items.values('tax_rate').annotate(
        base_amount=Sum('subtotal'),
        tax_amount=Sum('total_tax')
    ).order_by('tax_rate')
    
    rates_summary = []
    exempt_amount = Decimal('0.00')
    
    for rate in tax_rates:
        if rate['tax_rate'] == 0:
            exempt_amount += rate['base_amount']
        else:
            rates_summary.append({
                "rate": rate['tax_rate'],
                "baseAmount": rate['base_amount'],
                "taxAmount": rate['tax_amount']
            })
            
    return {
        "period": f"{year}-{month:02d}",
        "totalSales": total_sales,
        "totalTax": total_tax,
        "exemptAmount": exempt_amount,
        "taxRates": rates_summary
    }


def generate_account_statement(empresa: Empresa, client_id: str) -> dict:
    invoices = Invoice.objects.filter(
        empresa=empresa,
        client_id=client_id
    ).exclude(status=Invoice.Status.DRAFT).order_by('issue_date', 'created_at')
    
    receipts = Recibo.objects.filter(
        empresa=empresa,
        client_id=client_id
    ).exclude(status=Recibo.Status.DRAFT).order_by('issue_date', 'created_at')
    
    transactions = []
    balance = Decimal('0.00')
    
    for inv in invoices:
        if inv.type == Invoice.Type.NC:
            credit = inv.grand_total
            debit = Decimal('0.00')
            balance -= credit
            doc_type = "Nota de Crédito"
        else:
            debit = inv.grand_total
            credit = Decimal('0.00')
            balance += debit
            doc_type = "Factura"
            
        transactions.append({
            "date": inv.issue_date,
            "documentNo": inv.invoice_no,
            "description": f"{doc_type} Emitida",
            "debit": debit,
            "credit": credit,
            "balance": balance
        })
        
    for rec in receipts:
        credit = rec.total_amount
        debit = Decimal('0.00')
        balance -= credit
        
        transactions.append({
            "date": rec.issue_date,
            "documentNo": rec.receipt_no,
            "description": f"Recibo (Pagamento via {rec.get_payment_method_display()})",
            "debit": debit,
            "credit": credit,
            "balance": balance
        })
        
    # Sort by date
    transactions.sort(key=lambda x: x["date"])
    
    # Recalculate balance chronologically
    running_balance = Decimal('0.00')
    for tx in transactions:
        running_balance = running_balance + tx["debit"] - tx["credit"]
        tx["balance"] = running_balance
        
    return {
        "clientId": client_id,
        "currentBalance": running_balance,
        "transactions": transactions
    }