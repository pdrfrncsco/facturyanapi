from rest_framework import serializers

from apps.produtos.models import Product


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
        tax_rate = attrs.get("tax_rate", getattr(self.instance, "tax_rate", None))
        exemption_code = attrs.get("exemption_code", getattr(self.instance, "exemption_code", ""))
        if tax_rate == 0 and not exemption_code:
            raise serializers.ValidationError({"exemptionCode": "Obrigatório quando a taxa de IVA é 0."})
        return attrs
