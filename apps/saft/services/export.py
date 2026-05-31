import xml.etree.ElementTree as ET
from io import BytesIO
from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.auditoria.services.audit_logs import create_audit_log
from apps.clientes.models import Client
from apps.common.task_dispatch import dispatch_task
from apps.empresas.models import Empresa
from apps.facturacao.models import Invoice
from apps.facturacao.services.decimal_utils import money
from apps.produtos.models import Product
from apps.saft.models import SaftExportJob


def _build_saft_xml(*, empresa: Empresa, year: int, month: int) -> bytes:
    root = ET.Element(
        "AuditFile",
        {
            "xmlns": "urn:OECD:StandardAuditFile-Tax:AO_1.01_01",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        },
    )

    # 1. Header
    header = ET.SubElement(root, "Header")
    ET.SubElement(header, "AuditFileVersion").text = "1.01_01"
    ET.SubElement(header, "CompanyID").text = empresa.nif
    ET.SubElement(header, "TaxRegistrationNumber").text = empresa.nif
    ET.SubElement(header, "TaxAccountingBasis").text = "F"
    ET.SubElement(header, "CompanyName").text = empresa.name
    ET.SubElement(header, "FiscalYear").text = str(year)
    ET.SubElement(header, "StartDate").text = f"{year}-{month:02d}-01"
    # End date calculation (simplified)
    ET.SubElement(header, "EndDate").text = f"{year}-{month:02d}-28"
    ET.SubElement(header, "CurrencyCode").text = "AOA"
    ET.SubElement(header, "DateCreated").text = timezone.localdate().isoformat()
    ET.SubElement(header, "ProductVersion").text = "ndfatura-1.0"
    ET.SubElement(header, "SoftwareCertificateNumber").text = empresa.agt_certificate_no or "0"

    # 2. MasterFiles
    master_files = ET.SubElement(root, "MasterFiles")

    # 2.1 Customers
    clients = Client.objects.filter(empresa=empresa)
    for client in clients:
        customer = ET.SubElement(master_files, "Customer")
        ET.SubElement(customer, "CustomerID").text = str(client.id)
        ET.SubElement(customer, "AccountID").text = "Desconhecido"
        ET.SubElement(customer, "CustomerTaxID").text = client.nif
        ET.SubElement(customer, "CompanyName").text = client.name
        billing_address = ET.SubElement(customer, "BillingAddress")
        ET.SubElement(billing_address, "AddressDetail").text = client.address
        ET.SubElement(billing_address, "City").text = client.city
        ET.SubElement(billing_address, "Country").text = "AO"
        ET.SubElement(customer, "SelfBillingIndicator").text = "0"

    # 2.2 Products
    products = Product.objects.filter(empresa=empresa)
    for product in products:
        prod_el = ET.SubElement(master_files, "Product")
        # Heuristic for product type if field missing
        is_service = product.unit.upper() in ["HR", "SERV", "UN"] # This is just a guess
        ET.SubElement(prod_el, "ProductType").text = "P" # Defaulting to Product for now
        ET.SubElement(prod_el, "ProductCode").text = product.code
        ET.SubElement(prod_el, "ProductDescription").text = product.name
        ET.SubElement(prod_el, "ProductNumberCode").text = product.code

    # 3. SourceDocuments
    source_docs = ET.SubElement(root, "SourceDocuments")
    sales_invoices = ET.SubElement(source_docs, "SalesInvoices")

    invoices = Invoice.objects.filter(
        empresa=empresa,
        issue_date__year=year,
        issue_date__month=month,
    ).exclude(status=Invoice.Status.DRAFT)

    total_debit = Decimal("0")
    total_credit = Decimal("0")
    invoice_count = invoices.count()

    for invoice in invoices:
        inv_el = ET.SubElement(sales_invoices, "Invoice")
        ET.SubElement(inv_el, "InvoiceNo").text = invoice.invoice_no
        ET.SubElement(inv_el, "DocumentStatus").text = "N" if invoice.status != Invoice.Status.CANCELLED else "A"
        ET.SubElement(inv_el, "Hash").text = invoice.invoice_hash
        ET.SubElement(inv_el, "InvoiceDate").text = invoice.issue_date.isoformat()
        ET.SubElement(inv_el, "InvoiceType").text = invoice.type
        ET.SubElement(inv_el, "CustomerID").text = str(invoice.client_id)

        # Lines
        for idx, item in enumerate(invoice.items.all(), 1):
            line = ET.SubElement(inv_el, "Line")
            ET.SubElement(line, "LineNumber").text = str(idx)
            ET.SubElement(line, "ProductCode").text = item.product.code
            ET.SubElement(line, "Quantity").text = str(item.quantity)
            ET.SubElement(line, "UnitPrice").text = str(item.price)
            ET.SubElement(line, "Description").text = item.product_name

        # Document Totals
        doc_totals = ET.SubElement(inv_el, "DocumentTotals")
        ET.SubElement(doc_totals, "TaxPayable").text = str(invoice.tax_total)
        ET.SubElement(doc_totals, "NetTotal").text = str(invoice.subtotal - invoice.discount_total)
        ET.SubElement(doc_totals, "GrossTotal").text = str(invoice.grand_total)

        if invoice.type == Invoice.Type.NC:
            total_debit += invoice.grand_total
        else:
            total_credit += invoice.grand_total

    ET.SubElement(sales_invoices, "NumberOfEntries").text = str(invoice_count)
    ET.SubElement(sales_invoices, "TotalDebit").text = str(total_debit)
    ET.SubElement(sales_invoices, "TotalCredit").text = str(total_credit)

    buffer = BytesIO()
    ET.ElementTree(root).write(buffer, encoding="utf-8", xml_declaration=True)
    return buffer.getvalue()


def request_saft_export(*, empresa: Empresa, user, year: int, month: int, request=None) -> dict:
    filename = f"SAFT_AO_{empresa.nif}_{year}_{month:02d}.xml"
    job = SaftExportJob.objects.create(
        empresa=empresa,
        year=year,
        month=month,
        filename=filename,
        requested_by=user,
        status=SaftExportJob.Status.PENDING,
    )
    create_audit_log(
        empresa=empresa,
        user=user,
        action="EXPORT_SAFT",
        details=f"Pedido de exportação SAF-T (AO) para {year}-{month:02d}.",
        request=request,
        entity_type="saft_export",
        entity_id=str(job.id),
    )
    from apps.saft.tasks.export import generate_saft_export

    dispatch_task(generate_saft_export, str(job.id))
    return {
        "jobId": str(job.id),
        "filename": filename,
        "status": "queued",
    }


@transaction.atomic
def process_saft_export_job(*, job_id: str) -> SaftExportJob:
    job = SaftExportJob.objects.select_for_update().select_related("empresa", "requested_by").get(pk=job_id)
    xml_bytes = _build_saft_xml(empresa=job.empresa, year=job.year, month=job.month)
    job.file.save(job.filename, ContentFile(xml_bytes), save=False)
    job.status = SaftExportJob.Status.READY
    job.error_message = ""
    job.save(update_fields=["file", "status", "error_message", "updated_at"])
    return job


def mark_saft_export_error(*, job_id: str, error_message: str) -> None:
    job = SaftExportJob.objects.filter(pk=job_id).first()
    if not job:
        return
    job.status = SaftExportJob.Status.ERROR
    job.error_message = error_message[:2000]
    job.save(update_fields=["status", "error_message", "updated_at"])
