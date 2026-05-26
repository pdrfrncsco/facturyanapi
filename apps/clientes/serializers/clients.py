from rest_framework import serializers

from apps.clientes.models import Client
from apps.clientes.validators.clients import validate_client_payload


class ClientSerializer(serializers.ModelSerializer):
    tenantId = serializers.UUIDField(source="empresa_id", read_only=True)

    class Meta:
        model = Client
        fields = ["id", "name", "nif", "email", "phone", "address", "city", "country", "tenantId"]

    def validate(self, attrs):
        request = self.context.get("request")
        empresa = getattr(request, "empresa", None) if request else None
        if empresa is not None:
            try:
                validate_client_payload(empresa=empresa, data=attrs, instance=self.instance)
            except Exception as exc:
                if hasattr(exc, "message_dict"):
                    raise serializers.ValidationError(exc.message_dict)
                raise
        return attrs
