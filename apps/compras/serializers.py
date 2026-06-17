from rest_framework import serializers
from .models import SupplierInvoice, SupplierInvoiceItem

class SupplierInvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierInvoiceItem
        fields = ["id", "description", "quantity", "unit_price", "tax_rate", "total"]

class SupplierInvoiceSerializer(serializers.ModelSerializer):
    items = SupplierInvoiceItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = SupplierInvoice
        fields = [
            "id", "supplier_name", "supplier_nif", "invoice_no", 
            "issue_date", "subtotal", "tax_total", "grand_total", 
            "currency", "status", "file", "notes", "items", "created_at"
        ]

class SupplierInvoiceUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
