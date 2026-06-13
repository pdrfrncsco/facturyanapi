import logging
from django.core.mail import EmailMessage, send_mail
from django.conf import settings
from django.template.loader import render_to_string
from apps.facturacao.models import Invoice

logger = logging.getLogger(__name__)

def send_invoice_email(*, invoice: Invoice) -> bool:
    """
    Envia a factura por e-mail para o cliente, anexando o PDF.
    """
    try:
        from apps.facturacao.services.pdf_generation import generate_invoice_pdf_file
        
        subject = f"Factura {invoice.invoice_no or 'Rascunho'} - {invoice.empresa.name}"
        recipient_list = [invoice.client.email] if invoice.client.email else []
        
        if not recipient_list:
            logger.warning(f"Cliente {invoice.client_name} não tem e-mail configurado.")
            return False

        body = f"""
        Prezado(a) {invoice.client_name},
        
        Segue em anexo a factura {invoice.invoice_no or ''} referente aos nossos serviços/produtos.
        
        Detalhes do Documento:
        - Número: {invoice.invoice_no or 'Provisório'}
        - Data: {invoice.issue_date}
        - Total: {invoice.grand_total:,.2f} {invoice.currency}
        
        Agradecemos a sua preferência.
        
        Atentamente,
        {invoice.empresa.name}
        """

        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list,
        )

        # Gerar e anexar PDF
        pdf_content = generate_invoice_pdf_file(invoice=invoice)
        email.attach(pdf_content.name, pdf_content.read(), "application/pdf")

        email.send(fail_silently=False)
        
        logger.info(f"Factura {invoice.invoice_no} enviada por e-mail para {recipient_list}")
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar e-mail de factura: {str(e)}")
        return False

def send_payment_reminder(*, invoice: Invoice) -> bool:
    """
    Envia um lembrete de pagamento por e-mail para o cliente da factura.
    """
    try:
        subject = f"Lembrete de Pagamento: Factura {invoice.invoice_no}"
        context = {
            "client_name": invoice.client_name,
            "invoice_no": invoice.invoice_no,
            "due_date": invoice.due_date,
            "total_amount": invoice.grand_total,
            "pending_amount": invoice.grand_total - invoice.paid_amount,
            "company_name": invoice.empresa.name,
        }
        
        # In a real system, we'd use a nice HTML template
        # message = render_to_string("emails/payment_reminder.html", context)
        
        plain_message = f"""
        Olá {invoice.client_name},
        
        Este é um lembrete amigável de que a factura {invoice.invoice_no} venceu em {invoice.due_date}.
        
        Valor Total: {invoice.grand_total} AOA
        Valor Pendente: {invoice.grand_total - invoice.paid_amount} AOA
        
        Por favor, ignore este e-mail se o pagamento já tiver sido efectuado.
        
        Atentamente,
        A equipa {invoice.empresa.name}
        """
        
        recipient_list = [invoice.client.email] if invoice.client.email else []
        
        if not recipient_list:
            logger.warning(f"Cliente {invoice.client_name} não tem e-mail configurado.")
            return False

        # If in debug mode and no real SMTP, it will print to console if configured
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        
        logger.info(f"Lembrete de pagamento enviado para {invoice.client.email} (Factura {invoice.invoice_no})")
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar lembrete de pagamento: {str(e)}")
        return False
