import io
from django.core.files.base import ContentFile
from apps.common.services.pdf_engine import PdfEngine
from apps.pagamentos.models import Recibo
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

def generate_receipt_pdf_file(*, receipt: Recibo) -> ContentFile:
    buffer = io.BytesIO()
    styles = PdfEngine.get_styles()
    elements = []

    # 1. Header
    header_data = [
        [
            Paragraph(f"<b>{receipt.empresa.name}</b>", styles["Heading3"]),
            Paragraph("<b>RECIBO</b>", styles["DocumentTitle"]),
        ],
        [
            Paragraph(f"NIF: {receipt.empresa.nif}<br/>{receipt.empresa.address}", styles["Normal"]),
            Paragraph(f"<font color='#1e3a8a'>NÚMERO:</font> <b>{receipt.receipt_no or 'RASCUNHO'}</b><br/>DATA: {receipt.issue_date}", styles["Normal"]),
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
            Paragraph("CLIENTE", styles["DetailLabel"]),
            ""
        ],
        [
            Paragraph(f"<b>{receipt.client.name}</b>", styles["DetailValue"]),
            Paragraph(f"NIF: {receipt.client.nif}", styles["DetailValue"])
        ]
    ]
    client_table = Table(client_data, colWidths=[120 * mm, 60 * mm])
    elements.append(client_table)
    elements.append(Spacer(1, 10 * mm))

    # 3. Liquidações
    rows = [["DOCUMENTO", "DATA EMISSÃO", "TOTAL DOC", "VALOR PAGO"]]
    for item in receipt.items.all():
        rows.append([
            item.invoice.invoice_no,
            str(item.invoice.issue_date),
            f"{item.invoice.grand_total:,.2f} {item.invoice.currency}",
            f"{item.amount_paid:,.2f} {item.invoice.currency}",
        ])
    
    items_table = PdfEngine.create_table(rows, col_widths=[60 * mm, 40 * mm, 40 * mm, 40 * mm])
    elements.append(items_table)
    elements.append(Spacer(1, 10 * mm))

    # 4. Totais e Fiscal
    footer_row = [
        [
            # Coluna Fiscal
            Paragraph(f"<b>Hash:</b> {receipt.receipt_hash[:4]}-{receipt.receipt_hash[-4:]}", styles["FiscalInfo"]) if receipt.receipt_hash else "",
            # Coluna Totais
            PdfEngine.create_table([
                ["MÉTODO", receipt.get_payment_method_display()],
                ["TOTAL PAGO", f"{receipt.total_amount:,.2f} AOA"],
            ], col_widths=[30 * mm, 40 * mm], is_totals=True)
        ]
    ]
    footer_table = Table(footer_row, colWidths=[110 * mm, 70 * mm])
    footer_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(footer_table)
    
    if receipt.qrcode_string:
        elements.append(Spacer(1, 5 * mm))
        elements.append(PdfEngine.create_qr_code(receipt.qrcode_string, size=35 * mm))

    PdfEngine.generate_base_pdf(buffer, elements)
    buffer.seek(0)
    filename = f"{receipt.receipt_no.replace('/', '_') or 'RC_DRAFT'}.pdf"
    return ContentFile(buffer.read(), name=filename)
