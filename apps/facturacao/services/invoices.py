from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.auditoria.services.audit_logs import create_audit_log
from apps.empresas.models import Empresa
from apps.facturacao.models import Invoice, InvoiceItem
from apps.facturacao.services.agt_sync import queue_agt_cancellation, queue_agt_sync
from apps.facturacao.validators.fiscal import validate_can_cancel_invoice
from apps.facturacao.services.decimal_utils import money, quantity
from apps.facturacao.services.fiscal_issuance import apply_fiscal_issuance
from apps.facturacao.validators.invoices import (
    decimal_value,
    validate_invoice_header,
    validate_invoice_is_draft,
    validate_invoice_items,
)


def _draft_number(invoice_type: str) -> str:
    return f"DRAFT-{invoice_type}-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"


def _calculate_line(*, price: Decimal, qty: Decimal, discount: Decimal, tax_rate: Decimal) -> dict:
    gross_base = price * qty
    discount_amount = gross_base * (discount / Decimal("100"))
    subtotal = gross_base - discount_amount
    total_tax = subtotal * (tax_rate / Decimal("100"))
    total = subtotal + total_tax
    return {
        "subtotal": money(subtotal),
        "total_tax": money(total_tax),
        "total": money(total),
    }


def _replace_items(*, invoice: Invoice, empresa: Empresa, items: list[tuple]) -> dict:
    invoice.items.all().delete()

    subtotal = Decimal("0")
    discount_total = Decimal("0")
    tax_total = Decimal("0")

    for product, item in items:
        qty = quantity(item["quantity"])
        price = money(item["price"])
        discount = money(item["discount"])
        line = _calculate_line(price=price, qty=qty, discount=discount, tax_rate=product.tax_rate)
        gross_base = price * qty
        discount_total += gross_base * (discount / Decimal("100"))
        subtotal += gross_base
        tax_total += line["total_tax"]

        InvoiceItem.objects.create(
            empresa=empresa,
            invoice=invoice,
            product=product,
            product_name=product.name,
            quantity=qty,
            price=price,
            tax_rate=product.tax_rate,
            discount=discount,
            subtotal=line["subtotal"],
            total_tax=line["total_tax"],
            total=line["total"],
        )

    return {
        "subtotal": money(subtotal),
        "discount_total": money(discount_total),
        "tax_total": money(tax_total),
    }


@transaction.atomic
def create_draft_invoice(*, empresa: Empresa, user, data: dict, request=None) -> Invoice:
    client = validate_invoice_header(
        empresa=empresa,
        client_id=data["client_id"],
        invoice_type=data["type"],
    )
    validated_items = validate_invoice_items(empresa=empresa, items=data["items"])

    withholding_tax_rate = decimal_value(data.get("withholding_tax_rate", 0), "withholdingTaxRate")
    if withholding_tax_rate < 0 or withholding_tax_rate > 100:
        raise ValidationError({"withholdingTaxRate": "A retencao deve estar entre 0 e 100."})

    invoice = Invoice.objects.create(
        empresa=empresa,
        invoice_no=_draft_number(data["type"]),
        type=data["type"],
        status=Invoice.Status.DRAFT,
        issue_date=data.get("issue_date") or timezone.localdate(),
        due_date=data.get("due_date"),
        client=client,
        client_name=client.name,
        client_nif=client.nif,
        client_address=f"{client.address}, {client.city}",
        withholding_tax_rate=withholding_tax_rate,
        notes=data.get("notes", ""),
        created_by=user,
    )

    totals = _replace_items(invoice=invoice, empresa=empresa, items=validated_items)
    net_before_tax = totals["subtotal"] - totals["discount_total"]
    withholding_tax_amount = money(net_before_tax * (withholding_tax_rate / Decimal("100")))

    invoice.subtotal = totals["subtotal"]
    invoice.discount_total = totals["discount_total"]
    invoice.tax_total = totals["tax_total"]
    invoice.withholding_tax_amount = withholding_tax_amount
    invoice.grand_total = money(net_before_tax + totals["tax_total"] - withholding_tax_amount)
    invoice.save()

    create_audit_log(
        empresa=empresa,
        user=user,
        action="CREATE_INVOICE_DRAFT",
        details=f"Rascunho {invoice.invoice_no} criado para {invoice.client_name}.",
        request=request,
        entity_type="invoice",
        entity_id=str(invoice.id),
    )
    return invoice


@transaction.atomic
def update_draft_invoice(*, invoice: Invoice, user, data: dict, request=None) -> Invoice:
    validate_invoice_is_draft(invoice)
    client = validate_invoice_header(
        empresa=invoice.empresa,
        client_id=data.get("client_id", str(invoice.client_id)),
        invoice_type=data.get("type", invoice.type),
    )
    validated_items = validate_invoice_items(empresa=invoice.empresa, items=data.get("items", []))

    withholding_tax_rate = decimal_value(data.get("withholding_tax_rate", invoice.withholding_tax_rate), "withholdingTaxRate")
    if withholding_tax_rate < 0 or withholding_tax_rate > 100:
        raise ValidationError({"withholdingTaxRate": "A retencao deve estar entre 0 e 100."})

    invoice.type = data.get("type", invoice.type)
    invoice.due_date = data.get("due_date", invoice.due_date)
    invoice.client = client
    invoice.client_name = client.name
    invoice.client_nif = client.nif
    invoice.client_address = f"{client.address}, {client.city}"
    invoice.withholding_tax_rate = withholding_tax_rate
    invoice.notes = data.get("notes", invoice.notes)

    totals = _replace_items(invoice=invoice, empresa=invoice.empresa, items=validated_items)
    net_before_tax = totals["subtotal"] - totals["discount_total"]
    withholding_tax_amount = money(net_before_tax * (withholding_tax_rate / Decimal("100")))

    invoice.subtotal = totals["subtotal"]
    invoice.discount_total = totals["discount_total"]
    invoice.tax_total = totals["tax_total"]
    invoice.withholding_tax_amount = withholding_tax_amount
    invoice.grand_total = money(net_before_tax + totals["tax_total"] - withholding_tax_amount)
    invoice.save()

    create_audit_log(
        empresa=invoice.empresa,
        user=user,
        action="UPDATE_INVOICE_DRAFT",
        details=f"Rascunho {invoice.invoice_no} actualizado.",
        request=request,
        entity_type="invoice",
        entity_id=str(invoice.id),
    )
    return invoice


def delete_draft_invoice(*, invoice: Invoice, user, request=None) -> None:
    validate_invoice_is_draft(invoice)
    invoice.delete()
    create_audit_log(
        empresa=invoice.empresa,
        user=user,
        action="DELETE_INVOICE_DRAFT",
        details=f"Rascunho {invoice.invoice_no} removido.",
        request=request,
        entity_type="invoice",
        entity_id=str(invoice.id),
    )


@transaction.atomic
def issue_invoice(*, invoice: Invoice, user, request=None) -> Invoice:
    invoice = Invoice.objects.select_for_update().select_related("empresa").get(pk=invoice.pk)
    invoice = apply_fiscal_issuance(invoice=invoice)
    invoice.agt_response_code = "PENDING"
    invoice.save(
        update_fields=[
            "invoice_no",
            "issue_date",
            "previous_hash",
            "invoice_hash",
            "qrcode_string",
            "status",
            "agt_response_code",
            "updated_at",
        ]
    )
    queue_agt_sync(invoice=invoice)

    create_audit_log(
        empresa=invoice.empresa,
        user=user,
        action="ISSUE_INVOICE",
        details=f"Factura {invoice.invoice_no} emitida com hash fiscal {invoice.invoice_hash}.",
        request=request,
        entity_type="invoice",
        entity_id=str(invoice.id),
    )
    return invoice


@transaction.atomic
def cancel_invoice(*, invoice: Invoice, user, reason: str, request=None) -> Invoice:
    invoice = Invoice.objects.select_for_update().select_related("empresa").get(pk=invoice.pk)
    validate_can_cancel_invoice(invoice, reason=reason)

    invoice.status = Invoice.Status.CANCELLED
    invoice.cancelled_at = timezone.now()
    invoice.cancellation_reason = reason.strip()
    invoice.cancelled_by = user
    invoice.agt_response_code = "CANCEL_PENDING"
    invoice.save(
        update_fields=[
            "status",
            "cancelled_at",
            "cancellation_reason",
            "cancelled_by",
            "agt_response_code",
            "updated_at",
        ]
    )
    queue_agt_cancellation(invoice=invoice)

    create_audit_log(
        empresa=invoice.empresa,
        user=user,
        action="CANCEL_INVOICE",
        details=f"Factura {invoice.invoice_no} cancelada. Motivo: {invoice.cancellation_reason}",
        request=request,
        entity_type="invoice",
        entity_id=str(invoice.id),
    )
    return invoice
