import io

import qrcode
from django.core.files.base import ContentFile
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from apps.facturacao.models import Invoice, InvoiceDocument


def _qr_image_bytes(data: str) -> bytes:
    qr = qrcode.QRCode(version=1, box_size=4, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    buffer = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
    return buffer.getvalue()


def generate_invoice_pdf_file(*, invoice: Invoice) -> ContentFile:
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    elements = []

    elements.append(Paragraph(f"<b>{invoice.empresa.name}</b>", styles["Title"]))
    elements.append(Paragraph(f"NIF: {invoice.empresa.nif}", styles["Normal"]))
    elements.append(Paragraph(f"{invoice.empresa.address}", styles["Normal"]))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph(f"<b>{invoice.type} {invoice.invoice_no}</b>", styles["Heading2"]))
    elements.append(Paragraph(f"Estado: {invoice.status}", styles["Normal"]))
    elements.append(Paragraph(f"Data: {invoice.issue_date}", styles["Normal"]))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph(f"<b>Cliente:</b> {invoice.client_name}", styles["Normal"]))
    elements.append(Paragraph(f"NIF Cliente: {invoice.client_nif}", styles["Normal"]))
    elements.append(Paragraph(invoice.client_address, styles["Normal"]))
    elements.append(Spacer(1, 10))

    rows = [["Produto", "Qtd", "Preço", "IVA%", "Total"]]
    for item in invoice.items.all():
        rows.append([
            item.product_name,
            str(item.quantity),
            str(item.price),
            str(item.tax_rate),
            str(item.total),
        ])
    table = Table(rows, colWidths=[80 * mm, 20 * mm, 25 * mm, 18 * mm, 25 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 12))

    totals = [
        ["Subtotal", str(invoice.subtotal)],
        ["Desconto", str(invoice.discount_total)],
        ["IVA", str(invoice.tax_total)],
        ["Retenção", str(invoice.withholding_tax_amount)],
        ["Total", str(invoice.grand_total)],
    ]
    totals_table = Table(totals, colWidths=[40 * mm, 40 * mm])
    totals_table.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]))
    elements.append(totals_table)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph(f"<b>Hash fiscal:</b> {invoice.invoice_hash}", styles["Normal"]))
    if invoice.qrcode_string:
        elements.append(Image(io.BytesIO(_qr_image_bytes(invoice.qrcode_string)), width=35 * mm, height=35 * mm))

    doc.build(elements)
    buffer.seek(0)
    filename = f"{invoice.invoice_no.replace('/', '_')}.pdf"
    return ContentFile(buffer.read(), name=filename)


def create_or_reset_invoice_document(*, invoice: Invoice) -> InvoiceDocument:
    document, _ = InvoiceDocument.objects.get_or_create(
        empresa=invoice.empresa,
        invoice=invoice,
        defaults={"status": InvoiceDocument.Status.PENDING},
    )
    if document.status != InvoiceDocument.Status.PENDING:
        document.status = InvoiceDocument.Status.PENDING
        document.error_message = ""
        document.save(update_fields=["status", "error_message", "updated_at"])
    return document


def store_invoice_pdf(*, document: InvoiceDocument, invoice: Invoice) -> InvoiceDocument:
    pdf_file = generate_invoice_pdf_file(invoice=invoice)
    document.file.save(pdf_file.name, pdf_file, save=False)
    document.status = InvoiceDocument.Status.READY
    document.generated_at = timezone.now()
    document.error_message = ""
    document.save(update_fields=["file", "status", "generated_at", "error_message", "updated_at"])
    return document


def mark_invoice_pdf_error(*, document: InvoiceDocument, error_message: str) -> None:
    document.status = InvoiceDocument.Status.ERROR
    document.error_message = error_message[:2000]
    document.save(update_fields=["status", "error_message", "updated_at"])
