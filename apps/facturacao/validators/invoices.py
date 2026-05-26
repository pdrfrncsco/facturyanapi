from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from apps.clientes.models import Client
from apps.empresas.models import Empresa
from apps.facturacao.models import Invoice
from apps.produtos.models import Product


def decimal_value(value, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({field: "Valor numerico invalido."})


def validate_invoice_is_draft(invoice: Invoice) -> None:
    if invoice.status != Invoice.Status.DRAFT:
        raise ValidationError({"status": "Apenas rascunhos podem ser alterados nesta fase."})


def validate_invoice_header(*, empresa: Empresa, client_id: str, invoice_type: str) -> Client:
    if invoice_type not in Invoice.Type.values:
        raise ValidationError({"type": "Tipo de documento invalido."})

    client = Client.objects.filter(id=client_id, empresa=empresa).first()
    if client is None:
        raise ValidationError({"clientId": "Cliente invalido ou sem acesso para esta empresa."})
    return client


def validate_invoice_items(*, empresa: Empresa, items: list[dict]) -> list[tuple[Product, dict]]:
    if not items:
        raise ValidationError({"items": "Adicione pelo menos uma linha ao rascunho."})

    validated_items = []
    errors = {}
    for index, item in enumerate(items):
        prefix = f"items.{index}"
        product_id = item.get("productId") or item.get("product_id")
        product = Product.objects.filter(id=product_id, empresa=empresa).first()
        if product is None:
            errors[f"{prefix}.productId"] = "Produto invalido ou sem acesso para esta empresa."
            continue

        quantity = decimal_value(item.get("quantity", 0), f"{prefix}.quantity")
        discount = decimal_value(item.get("discount", 0), f"{prefix}.discount")
        price = decimal_value(item.get("price", product.price), f"{prefix}.price")

        if quantity <= 0:
            errors[f"{prefix}.quantity"] = "A quantidade deve ser superior a zero."
        if price < 0:
            errors[f"{prefix}.price"] = "O preco nao pode ser negativo."
        if discount < 0 or discount > 100:
            errors[f"{prefix}.discount"] = "O desconto deve estar entre 0 e 100."
        if product.unit != "SERV" and product.stock < quantity:
            errors[f"{prefix}.quantity"] = "Quantidade indisponivel em stock."

        validated_items.append((product, {**item, "quantity": quantity, "discount": discount, "price": price}))

    if errors:
        raise ValidationError(errors)
    return validated_items
