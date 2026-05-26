from apps.auditoria.services.audit_logs import create_audit_log
from apps.empresas.models import Empresa
from apps.produtos.models import Product


def create_product(*, empresa: Empresa, user, data: dict, request=None) -> Product:
    product = Product.objects.create(empresa=empresa, **data)
    create_audit_log(
        empresa=empresa,
        user=user,
        action="ADD_PRODUCT",
        details=f"Produto adicionado: {product.name} ({product.code})",
        request=request,
        entity_type="product",
        entity_id=str(product.id),
    )
    return product


def update_product(*, product: Product, user, data: dict, request=None) -> Product:
    for field, value in data.items():
        setattr(product, field, value)
    product.save()
    create_audit_log(
        empresa=product.empresa,
        user=user,
        action="UPDATE_PRODUCT",
        details=f"Produto actualizado: {product.name}",
        request=request,
        entity_type="product",
        entity_id=str(product.id),
    )
    return product


def delete_product(*, product: Product, user, request=None) -> None:
    product.delete()
    create_audit_log(
        empresa=product.empresa,
        user=user,
        action="DELETE_PRODUCT",
        details=f"Produto removido: {product.name}",
        request=request,
        entity_type="product",
        entity_id=str(product.id),
    )
