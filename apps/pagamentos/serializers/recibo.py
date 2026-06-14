from rest_framework import serializers
from apps.pagamentos.models import Recibo, ReciboItem


class ReciboItemSerializer(serializers.ModelSerializer):
    invoiceNo = serializers.CharField(source="invoice.invoice_no", read_only=True)
    amountPaid = serializers.DecimalField(source="amount_paid", max_digits=18, decimal_places=2, read_only=True)
    
    class Meta:
        model = ReciboItem
        fields = ["id", "invoice", "invoiceNo", "amountPaid"]


class ReciboSerializer(serializers.ModelSerializer):
    items = ReciboItemSerializer(many=True, read_only=True)
    clientName = serializers.CharField(source="client.name", read_only=True)
    receiptNo = serializers.CharField(source="receipt_no", read_only=True)
    issueDate = serializers.DateField(source="issue_date", read_only=True)
    totalAmount = serializers.DecimalField(source="total_amount", max_digits=18, decimal_places=2, read_only=True)
    paymentMethod = serializers.CharField(source="payment_method", read_only=True)
    receiptHash = serializers.CharField(source="receipt_hash", read_only=True)
    qrcodeString = serializers.CharField(source="qrcode_string", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    
    class Meta:
        model = Recibo
        fields = [
            "id", "receiptNo", "client", "clientName", "issueDate",
            "totalAmount", "paymentMethod", "status",
            "receiptHash", "qrcodeString", "notes", "items",
            "createdAt", "updatedAt"
        ]
        read_only_fields = ["receiptNo", "status", "receiptHash", "qrcodeString", "issueDate"]


class SettlementCreateSerializer(serializers.Serializer):
    client = serializers.UUIDField()
    payment_method = serializers.ChoiceField(choices=Recibo.PaymentMethod.choices)
    notes = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(child=serializers.DictField(), min_length=1)

    def validate_items(self, value):
        normalized_items = []
        for index, item in enumerate(value, start=1):
            invoice_id = item.get("invoice_id")
            amount = item.get("amount")

            if not invoice_id:
                raise serializers.ValidationError(f"Item {index}: invoice_id é obrigatório.")
            if amount in (None, ""):
                raise serializers.ValidationError(f"Item {index}: amount é obrigatório.")

            try:
                amount_decimal = serializers.DecimalField(max_digits=18, decimal_places=2).to_internal_value(amount)
            except serializers.ValidationError:
                raise serializers.ValidationError(f"Item {index}: amount inválido.")

            if amount_decimal <= 0:
                raise serializers.ValidationError(f"Item {index}: amount deve ser maior que zero.")

            normalized_items.append({"invoice_id": invoice_id, "amount": amount_decimal})

        return normalized_items
