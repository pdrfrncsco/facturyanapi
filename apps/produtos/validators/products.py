from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from apps.empresas.models import Empresa
from apps.produtos.models import Product


ALLOWED_TAX_RATES = {Decimal("0"), Decimal("5"), Decimal("7"), Decimal("14")}


def _decimal(value, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({field: "Valor numerico invalido."})


def validate_product_payload(*, empresa: Empresa, data: dict, instance: Product | None = None) -> None:
    code = data.get("code", getattr(instance, "code", ""))
    name = data.get("name", getattr(instance, "name", ""))
    category = data.get("category", getattr(instance, "category", ""))
    type = data.get("type", getattr(instance, "type", Product.Type.PRODUCT))
    unit = data.get("unit", getattr(instance, "unit", ""))
    price = _decimal(data.get("price", getattr(instance, "price", 0)), "price")
    cost_price = _decimal(data.get("cost_price", getattr(instance, "cost_price", 0)), "costPrice")
    stock = _decimal(data.get("stock", getattr(instance, "stock", 0)), "stock")
    min_stock = _decimal(data.get("min_stock", getattr(instance, "min_stock", 0)), "minStock")
    tax_rate = _decimal(data.get("tax_rate", getattr(instance, "tax_rate", 14)), "taxRate")
    exemption_code = data.get("exemption_code", getattr(instance, "exemption_code", ""))

    errors = {}
    if len(code.strip()) < 2:
        errors["code"] = "O codigo do produto deve ter pelo menos 2 caracteres."
    if len(name.strip()) < 3:
        errors["name"] = "O nome do produto deve ter pelo menos 3 caracteres."
    if len(category.strip()) < 2:
        errors["category"] = "A categoria deve ter pelo menos 2 caracteres."
    if type not in Product.Type.values:
        errors["type"] = "Tipo de produto invalido."
    if len(unit.strip()) < 1:
        errors["unit"] = "A unidade e obrigatoria."
    if price < 0:
        errors["price"] = "O preco unitario nao pode ser negativo."
    if cost_price < 0:
        errors["costPrice"] = "O preco de custo nao pode ser negativo."
    if stock < 0:
        errors["stock"] = "O stock nao pode ser negativo."
    if min_stock < 0:
        errors["minStock"] = "O stock minimo nao pode ser negativo."
    if tax_rate not in ALLOWED_TAX_RATES:
        errors["taxRate"] = "Taxa de IVA invalida. Use 0, 5, 7 ou 14."
    if tax_rate == 0 and not str(exemption_code).strip():
        errors["exemptionCode"] = "Obrigatorio quando a taxa de IVA e 0."


    duplicate_query = Product.objects.filter(empresa=empresa, code=code)
    if instance is not None:
        duplicate_query = duplicate_query.exclude(pk=instance.pk)
    if duplicate_query.exists():
        errors["code"] = "Ja existe um produto com este codigo nesta empresa."

    if errors:
        raise ValidationError(errors)
