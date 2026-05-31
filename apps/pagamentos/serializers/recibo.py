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
    items = serializers.ListField(
        child=serializers.DictField()
    )
