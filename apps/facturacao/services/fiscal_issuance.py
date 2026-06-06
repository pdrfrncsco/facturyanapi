import hashlib
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

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


def fiscal_hash(*, previous_hash: str, invoice_number: str, invoice_date, total: Decimal, company_nif: str) -> str:
    source = f"{previous_hash}{invoice_number}{invoice_date.isoformat()}{money(total)}{company_nif}"
    return hashlib.sha1(source.encode("utf-8")).hexdigest()


def qr_code_string(*, invoice: Invoice) -> str:
    return (
        "https://portaldocontribuinte.minfin.gov.ao/verify"
        f"?doc={invoice.invoice_no}"
        f"&nif={invoice.empresa.nif}"
        f"&total={money(invoice.grand_total)}"
        f"&hash={invoice.invoice_hash}"
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
        previous_hash=previous_hash,
        invoice_number=invoice_number,
        invoice_date=issue_date,
        total=invoice.grand_total,
        company_nif=invoice.empresa.nif,
    )

    invoice.invoice_no = invoice_number
    invoice.issue_date = issue_date
    invoice.previous_hash = previous_hash
    invoice.invoice_hash = invoice_hash
    invoice.qrcode_string = qr_code_string(invoice=invoice)
    invoice.status = Invoice.Status.ISSUED
    return invoice
