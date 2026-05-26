from rest_framework import serializers

from apps.clientes.models import Client


class ClientSerializer(serializers.ModelSerializer):
    tenantId = serializers.UUIDField(source="empresa_id", read_only=True)

    class Meta:
        model = Client
        fields = ["id", "name", "nif", "email", "phone", "address", "city", "country", "tenantId"]
