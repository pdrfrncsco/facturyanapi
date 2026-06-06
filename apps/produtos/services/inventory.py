from django.db import transaction
from apps.auditoria.services.audit_logs import create_audit_log
from apps.produtos.models import Product, StockMovement


@transaction.atomic
def adjust_stock(*, product: Product, user, quantity, type, reason, request=None) -> StockMovement:
    """
    Ajusta o stock de um produto e regista o movimento e auditoria.
    """
    if type == StockMovement.Type.IN:
        product.stock += quantity
    else:
        product.stock -= quantity
    
    product.save(update_fields=["stock", "updated_at"])
    
    movement = StockMovement.objects.create(
        empresa=product.empresa,
        product=product,
        type=type,
        quantity=quantity,
        reason=reason,
        operator=user
    )
    
    create_audit_log(
        empresa=product.empresa,
        user=user,
        action="STOCK_ADJUSTMENT",
        details=f"Ajuste de stock ({type}): {quantity} {product.unit} para {product.name}. Razão: {reason}",
        request=request,
        entity_type="product",
        entity_id=str(product.id),
    )
    
    return movement
