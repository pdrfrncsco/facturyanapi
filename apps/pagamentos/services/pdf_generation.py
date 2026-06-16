import io
from django.core.files.base import ContentFile
from apps.common.services.pdf_engine import PdfEngine
from apps.pagamentos.models import Recibo
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

def generate_receipt_pdf_file(*, receipt: Recibo) -> ContentFile:
    buffer = io.BytesIO()
    styles = PdfEngine.get_styles()
    elements = []

    # 1. Header with modern layout
    header_data = [
        [
            Paragraph(f"<font size='14' color='#1e3a8a'><b>{receipt.empresa.name}</b></font><br/>"
                      f"<font color='grey' size='8'>NIF: {receipt.empresa.nif}<br/>"
                      f"{receipt.empresa.address}<br/>"
                      f"{receipt.empresa.city}, Angola</font>", styles["Normal"]),
            Paragraph(f"<font color='#1e3a8a' size='22'><b>RECIBO</b></font><br/>"
                      f"<font size='12'><b>{receipt.receipt_no or 'RASCUNHO'}</b></font><br/>"
                      f"<font color='grey' size='9'>Data: {receipt.issue_date}</font>", styles["Normal"]),
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
            Paragraph("<font color='#1e3a8a' size='8'><b>DADOS DO CLIENTE</b></font>", styles["Normal"]),
            ""
        ],
        [
            Paragraph(f"<font size='12'><b>{receipt.client.name}</b></font><br/>"
                      f"<font color='grey' size='9'>NIF: {receipt.client.nif}</font>", styles["Normal"]),
            Paragraph(f"<font color='#1e3a8a' size='8'>VALOR TOTAL LIQUIDADO</font><br/>"
                      f"<font size='16'><b>{receipt.total_amount:,.2f} AOA</b></font>", styles["Normal"])
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

    # 3. Liquidações Table
    elements.append(Paragraph("<font color='grey' size='8'><b>DOCUMENTOS LIQUIDADOS</b></font>", styles["Normal"]))
    elements.append(Spacer(1, 4 * mm))
    
    rows = [[
        Paragraph("DOCUMENTO", styles["TableHeader"]),
        Paragraph("DATA", styles["TableHeader"]),
        Paragraph("TOTAL DOC", styles["TableHeader"]),
        Paragraph("VALOR PAGO", styles["TableHeader"])
    ]]
    for item in receipt.items.all():
        rows.append([
            Paragraph(item.invoice.invoice_no, styles["TableCell"]),
            Paragraph(str(item.invoice.issue_date), styles["TableCell"]),
            Paragraph(f"{item.invoice.grand_total:,.2f} {item.invoice.currency}", styles["TableCell"]),
            Paragraph(f"{item.amount_paid:,.2f} {item.invoice.currency}", styles["TableCell"]),
        ])
    
    items_table = PdfEngine.create_table(rows, col_widths=[60 * mm, 35 * mm, 42.5 * mm, 42.5 * mm])
    elements.append(items_table)
    elements.append(Spacer(1, 10 * mm))

    # 4. Totals and Notes
    summary_data = [
        [
            Paragraph(f"<font size='8' color='grey'><b>OBSERVAÇÕES</b></font><br/>"
                      f"<font size='9'>{receipt.notes or '-'}</font>", styles["Normal"]),
            PdfEngine.create_table([
                [Paragraph("MÉTODO", styles["TableCell"]), Paragraph(receipt.get_payment_method_display().upper(), styles["TableCell"])],
                [Paragraph("TOTAL LIQUIDADO", styles["TableHeader"]), Paragraph(f"<b>{receipt.total_amount:,.2f} AOA</b>", styles["TableHeader"])],
            ], col_widths=[35 * mm, 45 * mm], is_totals=True)
        ]
    ]
    summary_table = Table(summary_data, colWidths=[100 * mm, 80 * mm])
    summary_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(summary_table)
    elements.append(Spacer(1, 15 * mm))

    # 5. Fiscal Section
    if receipt.receipt_hash:
        elements.append(Paragraph(f"<font color='#10b981' size='8'><b>ASSINATURA DIGITAL FISCAL (AGT)</b></font>", styles["Normal"]))
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph(f"<font face='Courier' size='7' color='grey'>{receipt.receipt_hash}</font>", styles["Normal"]))
        elements.append(Spacer(1, 8 * mm))

    if receipt.qrcode_string:
        elements.append(PdfEngine.create_qr_code(receipt.qrcode_string, size=35 * mm))
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph("<font size='7' color='grey'>Digitalize para validar na AGT</font>", styles["Normal"]))

    PdfEngine.generate_base_pdf(buffer, elements)
    buffer.seek(0)
    filename = f"{receipt.receipt_no.replace('/', '_') or 'RC_DRAFT'}.pdf"
    return ContentFile(buffer.read(), name=filename)
