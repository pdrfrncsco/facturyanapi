from rest_framework import serializers

from apps.produtos.models import Product, StockMovement
from apps.produtos.validators.products import validate_product_payload


class ProductSerializer(serializers.ModelSerializer):
    taxRate = serializers.DecimalField(source="tax_rate", max_digits=5, decimal_places=2)
    exemptionCode = serializers.CharField(source="exemption_code", allow_blank=True, required=False)
    tenantId = serializers.UUIDField(source="empresa_id", read_only=True)
    costPrice = serializers.DecimalField(source="cost_price", max_digits=18, decimal_places=2, required=False)
    minStock = serializers.DecimalField(source="min_stock", max_digits=18, decimal_places=3, required=False)
    isActive = serializers.BooleanField(source="is_active", default=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "code",
            "name",
            "category",
            "type",
            "price",
            "costPrice",
            "stock",
            "minStock",
            "taxRate",
            "exemptionCode",
            "tenantId",
            "unit",
            "isActive",
        ]

    def validate(self, attrs):
        request = self.context.get("request")
        empresa = getattr(request, "empresa", None) if request else None
        if empresa is not None:
            # Normalizar para o validador que espera os nomes dos campos do modelo
            payload = attrs.copy()
            if "tax_rate" in payload: payload["tax_rate"] = payload.pop("tax_rate")
            if "exemption_code" in payload: payload["exemption_code"] = payload.pop("exemption_code")
            
            try:
                validate_product_payload(empresa=empresa, data=payload, instance=self.instance)
            except Exception as exc:
                if hasattr(exc, "message_dict"):
                    raise serializers.ValidationError(exc.message_dict)
                raise
        return attrs


class StockMovementSerializer(serializers.ModelSerializer):
    operatorName = serializers.CharField(source="operator.get_full_name", read_only=True)
    productName = serializers.CharField(source="product.name", read_only=True)
    productCode = serializers.CharField(source="product.code", read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "product",
            "productName",
            "productCode",
            "type",
            "quantity",
            "reason",
            "operator",
            "operatorName",
            "timestamp",
        ]
        read_only_fields = ["operator", "timestamp"]
