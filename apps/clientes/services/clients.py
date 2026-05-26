from apps.auditoria.services.audit_logs import create_audit_log
from apps.clientes.models import Client
from apps.empresas.models import Empresa


def create_client(*, empresa: Empresa, user, data: dict, request=None) -> Client:
    client = Client.objects.create(empresa=empresa, **data)
    create_audit_log(
        empresa=empresa,
        user=user,
        action="ADD_CLIENT",
        details=f"Cliente registado: {client.name} (NIF: {client.nif})",
        request=request,
        entity_type="client",
        entity_id=str(client.id),
    )
    return client


def update_client(*, client: Client, user, data: dict, request=None) -> Client:
    for field, value in data.items():
        setattr(client, field, value)
    client.save()
    create_audit_log(
        empresa=client.empresa,
        user=user,
        action="UPDATE_CLIENT",
        details=f"Cliente actualizado: {client.name}",
        request=request,
        entity_type="client",
        entity_id=str(client.id),
    )
    return client


def delete_client(*, client: Client, user, request=None) -> None:
    client.delete()
    create_audit_log(
        empresa=client.empresa,
        user=user,
        action="DELETE_CLIENT",
        details=f"Cliente removido: {client.name}",
        request=request,
        entity_type="client",
        entity_id=str(client.id),
    )
