import hashlib
import base64
from decimal import Decimal

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization

from django.db import transaction
from django.utils import timezone
from django.conf import settings

from apps.empresas.models import Empresa
from apps.facturacao.models import FiscalSeries, Invoice
from apps.facturacao.services.decimal_utils import money
from apps.facturacao.validators.fiscal import validate_can_issue_invoice, validate_fiscal_series_active


def fiscal_number(*, invoice_type: str, fiscal_year: int, sequence: int, branch_code: str = "SEDE") -> str:
    # Formato AGT: [Tipo] [Série]/[Sequência]
    # Usamos o código do estabelecimento como parte da série
    return f"{invoice_type} {branch_code}{fiscal_year}/{sequence:06d}"


def previous_fiscal_hash(*, empresa: Empresa, invoice: Invoice) -> str:
    # O hash deve ser encadeado dentro da mesma série (Estabelecimento + Tipo + Ano)
    previous_invoice = (
        Invoice.objects.filter(
            empresa=empresa,
            estabelecimento=invoice.estabelecimento,
            type=invoice.type,
            issue_date__year=invoice.issue_date.year if invoice.issue_date else timezone.localdate().year
        )
        .exclude(pk=invoice.pk)
        .exclude(invoice_hash="")
        .order_by("-issue_date", "-created_at")
        .first()
    )
    return previous_invoice.invoice_hash if previous_invoice else ""


def sign_string(private_key_pem: str, data: str) -> str:
    if not private_key_pem:
        # Fallback for dev if no keys are generated
        return hashlib.sha1(data.encode("utf-8")).hexdigest()

    try:
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode('utf-8'),
            password=None,
        )
        signature = private_key.sign(
            data.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode('utf-8')
    except Exception as e:
        # Failsafe if key is malformed
        return hashlib.sha1(data.encode("utf-8")).hexdigest()


def fiscal_hash(*, empresa: Empresa, previous_hash: str, invoice_number: str, invoice_date, system_date, total: Decimal) -> str:
    # StringToHash AGT: DataFactura;DataSistema;NoFactura;TotalFatura;HashFacturaAnterior
    # Datas no formato YYYY-MM-DD e YYYY-MM-DDThh:mm:ss
    invoice_date_str = invoice_date.strftime("%Y-%m-%d")
    system_date_str = system_date.strftime("%Y-%m-%dT%H:%M:%S")
    total_str = f"{total:.2f}"
    
    source = f"{invoice_date_str};{system_date_str};{invoice_number};{total_str};{previous_hash}"
    return sign_string(empresa.software_private_key, source)


def qr_code_string(*, invoice: Invoice) -> str:
    # Formato padrão do QR Code fiscal da AGT (exemplo estruturado, pois a norma exige uma concatenação específica)
    # Exemplo: A:123456789*B:FT SEDE2024/1*C:2024-01-01*D:140.00*E:1140.00*F:HashedValue...
    return (
        f"A:{invoice.empresa.nif}*"
        f"B:{invoice.invoice_no}*"
        f"C:{invoice.issue_date.strftime('%Y-%m-%d')}*"
        f"D:{invoice.tax_total:.2f}*"
        f"E:{invoice.grand_total:.2f}*"
        f"F:{invoice.invoice_hash[:10]}*"
        f"G:{invoice.invoice_hash[-10:]}"
    )


@transaction.atomic
def allocate_fiscal_series_number(*, invoice: Invoice) -> tuple[str, int]:
    issue_date = timezone.localdate()
    fiscal_year = issue_date.year
    
    # Se não especificado, assume SEDE ou o primeiro disponível
    if not invoice.estabelecimento:
        from apps.empresas.models import Estabelecimento
        estabelecimento = Estabelecimento.objects.filter(empresa=invoice.empresa, code="SEDE").first() or \
                          Estabelecimento.objects.filter(empresa=invoice.empresa).first()
        
        if not estabelecimento:
            # Autocreation of default establishment to avoid crash and follow AGT rule (min 1 branch)
            estabelecimento = Estabelecimento.objects.create(
                empresa=invoice.empresa,
                code="SEDE",
                name="Sede Principal",
                address=invoice.empresa.address,
                city=invoice.empresa.city,
                is_active=True
            )
        
        invoice.estabelecimento = estabelecimento
        invoice.save(update_fields=["estabelecimento"])
    
    branch_code = invoice.estabelecimento.code
    
    series, created = FiscalSeries.objects.select_for_update().get_or_create(
        empresa=invoice.empresa,
        estabelecimento=invoice.estabelecimento,
        document_type=invoice.type,
        fiscal_year=fiscal_year,
        code=branch_code,
        defaults={"current_number": 0, "is_active": True},
    )
    validate_fiscal_series_active(series)

    # Se a série acabou de ser criada, solicitamos registo na AGT
    if created:
        from apps.facturacao.integrations.agt.client import AgtClient
        client = AgtClient()
        # Nota: Em produção isto pode ser assíncrono. Aqui fazemos síncrono para garantir o registo antes da primeira fatura.
        result = client.request_series(
            empresa=invoice.empresa,
            estabelecimento=invoice.estabelecimento,
            document_type=invoice.type,
            year=fiscal_year
        )
        if not result.success and not settings.AGT_MOCK_SYNC:
             raise ValidationError(f"Falha ao registar série fiscal na AGT: {result.error_message}")

    series.current_number += 1
    series.save(update_fields=["current_number", "updated_at"])

    invoice_number = fiscal_number(
        invoice_type=invoice.type,
        fiscal_year=fiscal_year,
        sequence=series.current_number,
        branch_code=branch_code,
    )
    return invoice_number, fiscal_year


def apply_fiscal_issuance(*, invoice: Invoice) -> Invoice:
    validate_can_issue_invoice(invoice)

    invoice_number, _ = allocate_fiscal_series_number(invoice=invoice)
    issue_date = timezone.localdate()
    previous_hash = previous_fiscal_hash(empresa=invoice.empresa, invoice=invoice)
    invoice_hash = fiscal_hash(
        empresa=invoice.empresa,
        previous_hash=previous_hash,
        invoice_number=invoice_number,
        invoice_date=issue_date,
        system_date=timezone.now(),
        total=invoice.grand_total,
    )

    invoice.invoice_no = invoice_number
    invoice.issue_date = issue_date
    invoice.previous_hash = previous_hash
    invoice.invoice_hash = invoice_hash
    invoice.qrcode_string = qr_code_string(invoice=invoice)
    invoice.status = Invoice.Status.ISSUED
    return invoice
