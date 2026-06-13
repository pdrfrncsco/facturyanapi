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


from apps.common.services.pdf_engine import PdfEngine


def generate_invoice_pdf_file(*, invoice: Invoice) -> ContentFile:
    buffer = io.BytesIO()
    styles = PdfEngine.get_styles()
    elements = []

    # 1. Header: Empresa vs Documento
    header_data = [
        [
            Paragraph(f"<b>{invoice.empresa.name}</b>", styles["Heading3"]),
            Paragraph(f"<b>{invoice.type}</b>", styles["DocumentTitle"]),
        ],
        [
            Paragraph(f"NIF: {invoice.empresa.nif}<br/>{invoice.empresa.address}", styles["Normal"]),
            Paragraph(f"<font color='#1e3a8a'>NÚMERO:</font> <b>{invoice.invoice_no or 'RASCUNHO'}</b><br/>DATA: {invoice.issue_date}", styles["Normal"]),
        ]
    ]
    header_table = Table(header_data, colWidths=[100 * mm, 80 * mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 15 * mm))

    # 2. Cliente
    client_data = [
        [
            Paragraph("ENTIDADE ADQUIRENTE", styles["DetailLabel"]),
            ""
        ],
        [
            Paragraph(f"<b>{invoice.client_name}</b>", styles["DetailValue"]),
            Paragraph(f"NIF: {invoice.client_nif}", styles["DetailValue"])
        ],
        [
            Paragraph(f"{invoice.client_address}", styles["Normal"]),
            ""
        ]
    ]
    client_table = Table(client_data, colWidths=[120 * mm, 60 * mm])
    client_table.setStyle(TableStyle([
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(client_table)
    elements.append(Spacer(1, 10 * mm))

    # 3. Itens
    rows = [["DESCRIÇÃO", "QTD", "PREÇO", "DESC%", "IVA%", "TOTAL"]]
    for item in invoice.items.all():
        rows.append([
            item.product_name,
            f"{item.quantity:g}",
            f"{item.price:,.2f}",
            f"{item.discount:g}%",
            f"{item.tax_rate:g}%",
            f"{item.total:,.2f}",
        ])
    
    items_table = PdfEngine.create_table(rows, col_widths=[75 * mm, 15 * mm, 25 * mm, 15 * mm, 15 * mm, 35 * mm])
    elements.append(items_table)
    elements.append(Spacer(1, 10 * mm))

    # 4. Totais e Fiscal
    footer_row = [
        [
            # Coluna Fiscal
            Paragraph(f"<b>Hash:</b> {invoice.invoice_hash[:4]}-{invoice.invoice_hash[-4:]}", styles["FiscalInfo"]) if invoice.invoice_hash else "",
            # Coluna Totais
            PdfEngine.create_table([
                ["SUBTOTAL", f"{invoice.subtotal:,.2f} {invoice.currency}"],
                ["DESCONTO", f"{invoice.discount_total:,.2f}"],
                ["IVA", f"{invoice.tax_total:,.2f}"],
                ["RETENÇÃO", f"{invoice.withholding_tax_amount:,.2f}"],
                ["TOTAL", f"{invoice.grand_total:,.2f} {invoice.currency}"],
            ], col_widths=[30 * mm, 40 * mm], is_totals=True)
        ]
    ]
    footer_table = Table(footer_row, colWidths=[110 * mm, 70 * mm])
    footer_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(footer_table)
    
    if invoice.qrcode_string:
        elements.append(Spacer(1, 5 * mm))
        elements.append(PdfEngine.create_qr_code(invoice.qrcode_string, size=35 * mm))

    PdfEngine.generate_base_pdf(buffer, elements)
    buffer.seek(0)
    filename = f"{invoice.invoice_no.replace('/', '_') or 'DRAFT'}.pdf"
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
