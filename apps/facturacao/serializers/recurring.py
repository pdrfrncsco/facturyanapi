from rest_framework import serializers
from apps.facturacao.models import RecurringInvoice, RecurringInvoiceItem
from apps.produtos.models import Product

class RecurringInvoiceItemSerializer(serializers.ModelSerializer):
    productId = serializers.UUIDField(source="product_id")
    productName = serializers.CharField(source="product.name", read_only=True)
    
    class Meta:
        model = RecurringInvoiceItem
        fields = ["id", "productId", "productName", "quantity", "price", "discount"]

class RecurringInvoiceSerializer(serializers.ModelSerializer):
    clientName = serializers.CharField(source="client.name", read_only=True)
    items = RecurringInvoiceItemSerializer(many=True)
    
    class Meta:
        model = RecurringInvoice
        fields = [
            "id", "client", "clientName", "description", "frequency", 
            "start_date", "end_date", "last_run", "next_run", 
            "is_active", "invoice_type", "currency", 
            "withholding_tax_rate", "notes", "auto_issue", "items"
        ]

class RecurringInvoiceCreateSerializer(serializers.ModelSerializer):
    items = RecurringInvoiceItemSerializer(many=True)
    
    class Meta:
        model = RecurringInvoice
        fields = [
            "client", "description", "frequency", "start_date", "end_date",
            "invoice_type", "currency", "withholding_tax_rate", "notes", 
            "auto_issue", "items"
        ]

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        recurring = RecurringInvoice.objects.create(empresa=self.context['request'].empresa, **validated_data)
        for item_data in items_data:
            RecurringInvoiceItem.objects.create(empresa=self.context['request'].empresa, recurring_invoice=recurring, **item_data)
        return recurring
