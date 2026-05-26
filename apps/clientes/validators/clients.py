import re

from django.core.exceptions import ValidationError

from apps.clientes.models import Client
from apps.empresas.models import Empresa


ANGOLA_NIF_PATTERN = re.compile(r"^[123579][0-9]{8}$")


def validate_angola_nif(nif: str) -> None:
    if not nif:
        raise ValidationError({"nif": "O NIF e obrigatorio."})
    if not ANGOLA_NIF_PATTERN.match(nif):
        raise ValidationError({"nif": "O NIF em Angola deve ter 9 digitos e iniciar por 1, 2, 3, 5, 7 ou 9."})


def validate_client_payload(*, empresa: Empresa, data: dict, instance: Client | None = None) -> None:
    nif = data.get("nif", getattr(instance, "nif", ""))
    name = data.get("name", getattr(instance, "name", ""))
    address = data.get("address", getattr(instance, "address", ""))

    errors = {}
    try:
        validate_angola_nif(nif)
    except ValidationError as exc:
        errors.update(exc.message_dict)

    if len(name.strip()) < 5:
        errors["name"] = "O nome do cliente deve ter pelo menos 5 caracteres."
    if len(address.strip()) < 6:
        errors["address"] = "O endereco do cliente deve ter pelo menos 6 caracteres."

    duplicate_query = Client.objects.filter(empresa=empresa, nif=nif)
    if instance is not None:
        duplicate_query = duplicate_query.exclude(pk=instance.pk)
    if duplicate_query.exists():
        errors["nif"] = "Ja existe um cliente com este NIF nesta empresa."

    if errors:
        raise ValidationError(errors)
