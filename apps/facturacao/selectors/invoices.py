from django.db.models import QuerySet

from apps.empresas.models import Empresa
from apps.facturacao.models import Invoice


def invoices_for_empresa(empresa: Empresa) -> QuerySet[Invoice]:
    return Invoice.objects.filter(empresa=empresa).select_related("client", "created_by").prefetch_related("items")
