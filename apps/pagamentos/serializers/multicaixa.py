from rest_framework import serializers
from apps.pagamentos.models import MulticaixaReference

class MulticaixaReferenceSerializer(serializers.ModelSerializer):
    entityCode = serializers.CharField(source="entity_code", read_only=True)
    referenceNumber = serializers.CharField(source="reference_number", read_only=True)
    expiresAt = serializers.DateTimeField(source="expires_at", read_only=True)
    paidAt = serializers.DateTimeField(source="paid_at", read_only=True)
    
    class Meta:
        model = MulticaixaReference
        fields = [
            "id", "entityCode", "referenceNumber", "amount", 
            "status", "expiresAt", "paidAt"
        ]
        read_only_fields = fields
