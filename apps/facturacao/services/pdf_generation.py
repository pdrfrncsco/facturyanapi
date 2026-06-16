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

    # 1. Header with modern layout
    header_data = [
        [
            Paragraph(f"<font size='14' color='#1e3a8a'><b>{invoice.empresa.name}</b></font><br/>"
                      f"<font color='grey' size='8'>NIF: {invoice.empresa.nif}<br/>"
                      f"{invoice.empresa.address}<br/>"
                      f"{invoice.empresa.city}, Angola</font>", styles["Normal"]),
            Paragraph(f"<font color='#1e3a8a' size='22'><b>{invoice.get_type_display().upper()}</b></font><br/>"
                      f"<font size='12'><b>{invoice.invoice_no or 'RASCUNHO'}</b></font><br/>"
                      f"<font color='grey' size='9'>Data: {invoice.issue_date}</font>", styles["Normal"]),
        ]
    ]
    header_table = Table(header_data, colWidths=[110 * mm, 70 * mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 15 * mm))

    # 2. Cliente Highlight Box
    client_box_data = [
        [
            Paragraph("<font color='#1e3a8a' size='8'><b>ENTIDADE ADQUIRENTE</b></font>", styles["Normal"]),
            ""
        ],
        [
            Paragraph(f"<font size='12'><b>{invoice.client_name}</b></font><br/>"
                      f"<font color='grey' size='9'>NIF: {invoice.client_nif}<br/>"
                      f"{invoice.client_address}</font>", styles["Normal"]),
            Paragraph(f"<font color='#1e3a8a' size='8'>VALOR TOTAL DO DOCUMENTO</font><br/>"
                      f"<font size='16'><b>{invoice.grand_total:,.2f} {invoice.currency}</b></font>", styles["Normal"])
        ]
    ]
    client_table = Table(client_box_data, colWidths=[120 * mm, 60 * mm])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
        ('BOX', (0, 0), (-1, -1), 0.1, colors.lightgrey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 1), (1, 1), 'RIGHT'),
    ]))
    elements.append(client_table)
    elements.append(Spacer(1, 12 * mm))

    # 2.5 Goods Movement (Only if GR or has data)
    if invoice.type == Invoice.Type.GR or invoice.vehicle_plate:
        elements.append(Paragraph("<font color='grey' size='8'><b>CIRCULAÇÃO DE MERCADORIAS</b></font>", styles["Normal"]))
        elements.append(Spacer(1, 2 * mm))
        movement_data = [
            [
                Paragraph(f"<b>Viatura:</b> {invoice.vehicle_plate or '-'}<br/>"
                          f"<b>Motorista:</b> {invoice.driver_name or '-'}", styles["FiscalInfo"]),
                Paragraph(f"<b>Carga:</b> {invoice.loading_date or '-'}<br/>"
                          f"<b>Descarga:</b> {invoice.delivery_date or '-'}", styles["FiscalInfo"]),
                Paragraph(f"<b>Ponto de Carga:</b> {invoice.loading_point or '-'}<br/>"
                          f"<b>Ponto de Descarga:</b> {invoice.delivery_point or '-'}", styles["FiscalInfo"])
            ]
        ]
        movement_table = Table(movement_data, colWidths=[60 * mm, 60 * mm, 60 * mm])
        movement_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.1, colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(movement_table)
        elements.append(Spacer(1, 10 * mm))

    # 3. Itens Table
    rows = [[
        Paragraph("DESCRIÇÃO", styles["TableHeader"]),
        Paragraph("QTD", styles["TableHeader"]),
        Paragraph("PREÇO", styles["TableHeader"]),
        Paragraph("DESC%", styles["TableHeader"]),
        Paragraph("IVA%", styles["TableHeader"]),
        Paragraph("TOTAL", styles["TableHeader"])
    ]]
    for item in invoice.items.all():
        rows.append([
            Paragraph(item.product_name, styles["TableCell"]),
            Paragraph(f"{item.quantity:g}", styles["TableCell"]),
            Paragraph(f"{item.price:,.2f}", styles["TableCell"]),
            Paragraph(f"{item.discount:g}%", styles["TableCell"]),
            Paragraph(f"{item.tax_rate:g}%", styles["TableCell"]),
            Paragraph(f"{item.total:,.2f}", styles["TableCell"]),
        ])
    
    items_table = PdfEngine.create_table(rows, col_widths=[70 * mm, 15 * mm, 25 * mm, 15 * mm, 15 * mm, 40 * mm])
    elements.append(items_table)
    elements.append(Spacer(1, 10 * mm))

    # 4. Totals and Notes
    summary_data = [
        [
            Paragraph(f"<font size='8' color='grey'><b>OBSERVAÇÕES / REGIME FISCAL</b></font><br/>"
                      f"<font size='8'>{invoice.notes or '-'}</font><br/><br/>"
                      f"<font size='8' color='grey'>Regime:</font> <font size='8'>{invoice.empresa.fiscal_regime or 'REGIME GERAL'}</font>", styles["Normal"]),
            PdfEngine.create_table([
                [Paragraph("SUBTOTAL", styles["TableCell"]), Paragraph(f"{invoice.subtotal:,.2f}", styles["TableCell"])],
                [Paragraph("DESCONTO", styles["TableCell"]), Paragraph(f"{invoice.discount_total:,.2f}", styles["TableCell"])],
                [Paragraph("IVA", styles["TableCell"]), Paragraph(f"{invoice.tax_total:,.2f}", styles["TableCell"])],
                [Paragraph("RETENÇÃO", styles["TableCell"]), Paragraph(f"{invoice.withholding_tax_amount:,.2f}", styles["TableCell"])],
                [Paragraph("TOTAL A PAGAR", styles["TableHeader"]), Paragraph(f"<b>{invoice.grand_total:,.2f} {invoice.currency}</b>", styles["TableHeader"])],
            ], col_widths=[35 * mm, 45 * mm], is_totals=True)
        ]
    ]
    summary_table = Table(summary_data, colWidths=[100 * mm, 80 * mm])
    summary_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(summary_table)
    elements.append(Spacer(1, 15 * mm))

    # 5. Fiscal Section
    if invoice.invoice_hash:
        elements.append(Paragraph(f"<font color='#10b981' size='8'><b>ASSINATURA DIGITAL FISCAL (AGT)</b></font>", styles["Normal"]))
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph(f"<font face='Courier' size='7' color='grey'>{invoice.invoice_hash}</font>", styles["Normal"]))
        elements.append(Spacer(1, 8 * mm))

    if invoice.qrcode_string:
        elements.append(PdfEngine.create_qr_code(invoice.qrcode_string, size=35 * mm))
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph("<font size='7' color='grey'>Digitalize para validar na AGT</font>", styles["Normal"]))

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
