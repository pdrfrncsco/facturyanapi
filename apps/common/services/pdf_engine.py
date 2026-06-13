import io
from typing import Any, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing

class PdfEngine:
    """
    Motor centralizado para geração de PDFs profissionais e conformes.
    """
    
    @staticmethod
    def get_styles():
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='FiscalInfo',
            fontSize=7,
            leading=8,
            textColor=colors.grey
        ))
        styles.add(ParagraphStyle(
            name='DocumentTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=20,
            textColor=colors.HexColor("#1e3a8a")
        ))
        styles.add(ParagraphStyle(
            name='DetailLabel',
            fontSize=8,
            textColor=colors.grey,
            textTransform='uppercase',
            fontName='Helvetica-Bold'
        ))
        styles.add(ParagraphStyle(
            name='DetailValue',
            fontSize=10,
            fontName='Helvetica'
        ))
        return styles

    @classmethod
    def generate_base_pdf(cls, buffer: io.BytesIO, elements: list):
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4, 
            leftMargin=15 * mm, 
            rightMargin=15 * mm, 
            topMargin=15 * mm, 
            bottomMargin=25 * mm
        )
        
        def footer(canvas, doc):
            canvas.saveState()
            styles = cls.get_styles()
            
            # Linha separadora
            canvas.setStrokeColor(colors.lightgrey)
            canvas.line(15 * mm, 20 * mm, 195 * mm, 20 * mm)
            
            # Informação do Software
            p = Paragraph("Processado por programa certificado n.º 0/AGT/2026 FACTURYAN ERP", styles['FiscalInfo'])
            w, h = p.wrap(doc.width, doc.bottomMargin)
            p.drawOn(canvas, doc.leftMargin, 12 * mm)
            
            # Numeração de página
            canvas.setFont('Helvetica', 8)
            canvas.drawRightString(195 * mm, 12 * mm, f"Página {doc.page}")
            canvas.restoreState()

        doc.build(elements, onFirstPage=footer, onLaterPages=footer)

    @staticmethod
    def create_qr_code(data: str, size: float = 30 * mm):
        qr_code = qr.QrCodeWidget(data)
        bounds = qr_code.getBounds()
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        d = Drawing(size, size, transform=[size / width, 0, 0, size / height, 0, 0])
        d.add(qr_code)
        return d

    @staticmethod
    def create_table(data: list, col_widths: list, is_totals: bool = False):
        if is_totals:
            ts = TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, -1), (-1, -1), 12),
                ('TOPPADDING', (0, -1), (-1, -1), 5),
            ])
        else:
            ts = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -1), 0.1, colors.lightgrey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ])
        
        return Table(data, colWidths=col_widths, style=ts)
