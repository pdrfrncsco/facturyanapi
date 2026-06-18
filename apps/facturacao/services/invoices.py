from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.auditoria.services.audit_logs import create_audit_log
from apps.empresas.models import Empresa, Estabelecimento
from apps.facturacao.models import Invoice, InvoiceItem, ExchangeRate, FISCAL_IMMUTABLE_FIELDS
from apps.facturacao.services.agt_sync import enqueue_invoice_pdf, queue_agt_cancellation, queue_agt_sync
from apps.facturacao.validators.fiscal import validate_can_cancel_invoice
from apps.facturacao.services.decimal_utils import money, quantity
from apps.facturacao.services.fiscal_issuance import apply_fiscal_issuance
from apps.facturacao.validators.invoices import (
    decimal_value,
    validate_invoice_header,
    validate_invoice_is_draft,
    validate_invoice_items,
)
from apps.integracoes.services import trigger_webhook
from apps.fiscal.models import FiscalEvent


def _draft_number(invoice_type: str) -> str:
    return f"DRAFT-{invoice_type}-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"


def _get_exchange_rate(*, empresa: Empresa, currency: str, date) -> Decimal:
    if currency == "AOA":
        return Decimal("1.0000")
    
    rate_obj = ExchangeRate.objects.filter(
        empresa=empresa,
        currency_code=currency,
        date__lte=date
    ).order_by("-date").first()
    
    if not rate_obj:
        raise ValidationError({"currency": f"Nenhuma taxa de câmbio encontrada para {currency} até a data {date}."})
    
    return rate_obj.rate


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

    estabelecimento_id = data.get("estabelecimento_id")
    if estabelecimento_id:
        estabelecimento = Estabelecimento.objects.get(empresa=empresa, pk=estabelecimento_id)
    else:
        estabelecimento = Estabelecimento.objects.filter(empresa=empresa, code="SEDE").first() or \
                         Estabelecimento.objects.filter(empresa=empresa).first()

    currency = data.get("currency", "AOA")
    exchange_rate = data.get("exchange_rate")
    if not exchange_rate:
        exchange_rate = _get_exchange_rate(empresa=empresa, currency=currency, date=timezone.localdate())

    invoice = Invoice.objects.create(
        empresa=empresa,
        estabelecimento=estabelecimento,
        invoice_no=_draft_number(data["type"]),
        type=data["type"],
        status=Invoice.Status.DRAFT,
        currency=currency,
        exchange_rate=exchange_rate,
        issue_date=data.get("issue_date") or timezone.localdate(),
        due_date=data.get("due_date"),
        client=client,
        client_name=client.name,
        client_nif=client.nif,
        client_address=f"{client.address}, {client.city}",
        withholding_tax_rate=withholding_tax_rate,
        notes=data.get("notes", ""),
        origin_document_id=data.get("origin_document_id"),
        rectification_reason=data.get("rectification_reason", ""),
        created_by=user,
        
        # Goods Movement (GR)
        vehicle_plate=data.get("vehicle_plate"),
        driver_name=data.get("driver_name"),
        loading_point=data.get("loading_point"),
        delivery_point=data.get("delivery_point"),
        loading_date=data.get("loading_date"),
        delivery_date=data.get("delivery_date"),
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
    
    if "estabelecimento_id" in data:
        invoice.estabelecimento = Estabelecimento.objects.get(empresa=invoice.empresa, pk=data["estabelecimento_id"])
    
    if "currency" in data:
        invoice.currency = data["currency"]
        if "exchange_rate" in data:
            invoice.exchange_rate = data["exchange_rate"]
        else:
            invoice.exchange_rate = _get_exchange_rate(empresa=invoice.empresa, currency=invoice.currency, date=timezone.localdate())

    if "origin_document_id" in data:
        invoice.origin_document_id = data["origin_document_id"]
    if "rectification_reason" in data:
        invoice.rectification_reason = data["rectification_reason"]

    # Goods Movement
    if "vehicle_plate" in data: invoice.vehicle_plate = data["vehicle_plate"]
    if "driver_name" in data: invoice.driver_name = data["driver_name"]
    if "loading_point" in data: invoice.loading_point = data["loading_point"]
    if "delivery_point" in data: invoice.delivery_point = data["delivery_point"]
    if "loading_date" in data: invoice.loading_date = data["loading_date"]
    if "delivery_date" in data: invoice.delivery_date = data["delivery_date"]

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
def convert_proforma_to_invoice(*, proforma: Invoice, user, target_type: str, request=None) -> Invoice:
    if proforma.type != Invoice.Type.PP:
        raise ValidationError("Apenas documentos Proforma podem ser convertidos.")
    
    if proforma.status == Invoice.Status.CANCELLED:
        raise ValidationError("Documentos cancelados nao podem ser convertidos.")

    # Create a copy of the proforma as a new invoice draft
    invoice_data = {
        "client_id": str(proforma.client_id),
        "type": target_type,
        "currency": proforma.currency,
        "exchange_rate": proforma.exchange_rate,
        "withholding_tax_rate": proforma.withholding_tax_rate,
        "notes": proforma.notes,
        "estabelecimento_id": str(proforma.estabelecimento_id) if proforma.estabelecimento_id else None,
        "items": []
    }

    for item in proforma.items.all():
        invoice_data["items"].append({
            "product_id": str(item.product_id),
            "quantity": float(item.quantity),
            "price": float(item.price),
            "discount": float(item.discount)
        })

    new_invoice = create_draft_invoice(empresa=proforma.empresa, user=user, data=invoice_data, request=request)
    
    # link proforma to new invoice
    new_invoice.origin_document = proforma
    new_invoice.save(update_fields=["origin_document"])

    # Automatically issue if possible
    return issue_invoice(invoice=new_invoice, user=user, request=request)


@transaction.atomic
def issue_invoice(*, invoice: Invoice, user, request=None) -> Invoice:
    invoice = Invoice.objects.select_for_update().select_related("empresa", "estabelecimento").get(pk=invoice.pk)

    apply_fiscal_issuance(invoice=invoice)
    invoice.agt_response_code = "PENDING"
    invoice.save(update_fields=list(FISCAL_IMMUTABLE_FIELDS) + ["agt_response_code", "status"])

    FiscalEvent.objects.create(
        empresa=invoice.empresa,
        entity_type="invoice",
        entity_id=invoice.id,
        event_type="DOCUMENT_SIGNED",
        payload={
            "invoiceNo": invoice.invoice_no,
            "hash": invoice.invoice_hash,
            "previousHash": invoice.previous_hash,
            "qrCode": invoice.qrcode_string,
        },
    )

    sync_log = queue_agt_sync(invoice=invoice)
    enqueue_invoice_pdf(invoice=invoice)
    invoice.refresh_from_db()

    FiscalEvent.objects.create(
        empresa=invoice.empresa,
        entity_type="invoice",
        entity_id=invoice.id,
        event_type="DOCUMENT_SENT",
        payload={
            "syncLogId": str(sync_log.id),
            "status": sync_log.status,
            "responseCode": sync_log.response_code,
        },
    )

    # Log de auditoria padrão
    create_audit_log(
        empresa=invoice.empresa,
        user=user,
        action="ISSUE_INVOICE",
        details=f"Factura {invoice.invoice_no} emitida e colocada na fila de sincronizacao AGT.",
        request=request,
        entity_type="invoice",
        entity_id=str(invoice.id),
    )

    # Webhook
    trigger_webhook(
        empresa_id=invoice.empresa_id,
        event_type="invoice.issued",
        payload={
            "id": str(invoice.id),
            "invoiceNo": invoice.invoice_no,
            "type": invoice.type,
            "clientName": invoice.client_name,
            "clientNif": invoice.client_nif,
            "grandTotal": float(invoice.grand_total),
            "status": invoice.status
        }
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

    invoice.refresh_from_db()

    create_audit_log(
        empresa=invoice.empresa,
        user=user,
        action="CANCEL_INVOICE",
        details=f"Factura {invoice.invoice_no} cancelada. Motivo: {invoice.cancellation_reason}",
        request=request,
        entity_type="invoice",
        entity_id=str(invoice.id),
    )

    # Webhook
    trigger_webhook(
        empresa_id=invoice.empresa_id,
        event_type="invoice.cancelled",
        payload={
            "id": str(invoice.id),
            "invoiceNo": invoice.invoice_no,
            "reason": reason,
            "status": invoice.status
        }
    )

    return invoice
