from django.db.models import QuerySet

from apps.clientes.models import Client
from apps.empresas.models import Empresa


def clients_for_empresa(empresa: Empresa) -> QuerySet[Client]:
    return Client.objects.filter(empresa=empresa)
