from django.db.models import QuerySet

from apps.empresas.models import Empresa
from apps.produtos.models import Product


def products_for_empresa(empresa: Empresa) -> QuerySet[Product]:
    return Product.objects.filter(empresa=empresa)
