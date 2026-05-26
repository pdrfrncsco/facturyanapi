from rest_framework import serializers

from apps.produtos.models import Product
from apps.produtos.validators.products import validate_product_payload


class ProductSerializer(serializers.ModelSerializer):
    taxRate = serializers.DecimalField(source="tax_rate", max_digits=5, decimal_places=2)
    exemptionCode = serializers.CharField(source="exemption_code", allow_blank=True, required=False)
    tenantId = serializers.UUIDField(source="empresa_id", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "code",
            "name",
            "category",
            "price",
            "stock",
            "taxRate",
            "exemptionCode",
            "tenantId",
            "unit",
        ]

    def validate(self, attrs):
        request = self.context.get("request")
        empresa = getattr(request, "empresa", None) if request else None
        if empresa is not None:
            try:
                validate_product_payload(empresa=empresa, data=attrs, instance=self.instance)
            except Exception as exc:
                if hasattr(exc, "message_dict"):
                    raise serializers.ValidationError(exc.message_dict)
                raise
        return attrs
