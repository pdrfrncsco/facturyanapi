from rest_framework import serializers

from apps.facturacao.models import Invoice, InvoiceItem


class InvoiceItemSerializer(serializers.ModelSerializer):
    productId = serializers.UUIDField(source="product_id", read_only=True)
    productName = serializers.CharField(source="product_name", read_only=True)
    taxRate = serializers.DecimalField(source="tax_rate", max_digits=5, decimal_places=2, read_only=True)
    totalTax = serializers.DecimalField(source="total_tax", max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = InvoiceItem
        fields = ["id", "productId", "productName", "quantity", "price", "taxRate", "discount", "totalTax", "subtotal", "total"]


class InvoiceSerializer(serializers.ModelSerializer):
    invoiceNo = serializers.CharField(source="invoice_no", read_only=True)
    issueDate = serializers.DateField(source="issue_date", read_only=True)
    dueDate = serializers.DateField(source="due_date", read_only=True)
    clientId = serializers.UUIDField(source="client_id", read_only=True)
    clientName = serializers.CharField(source="client_name", read_only=True)
    clientNif = serializers.CharField(source="client_nif", read_only=True)
    clientAddress = serializers.CharField(source="client_address", read_only=True)
    discountTotal = serializers.DecimalField(source="discount_total", max_digits=18, decimal_places=2, read_only=True)
    taxTotal = serializers.DecimalField(source="tax_total", max_digits=18, decimal_places=2, read_only=True)
    withholdingTaxRate = serializers.DecimalField(source="withholding_tax_rate", max_digits=5, decimal_places=2, read_only=True)
    withholdingTaxAmount = serializers.DecimalField(source="withholding_tax_amount", max_digits=18, decimal_places=2, read_only=True)
    grandTotal = serializers.DecimalField(source="grand_total", max_digits=18, decimal_places=2, read_only=True)
    invoiceHash = serializers.CharField(source="invoice_hash", read_only=True)
    agtSyncDate = serializers.DateTimeField(source="agt_sync_date", read_only=True)
    agtResponseCode = serializers.CharField(source="agt_response_code", read_only=True)
    qrcodeString = serializers.CharField(source="qrcode_string", read_only=True)
    tenantId = serializers.UUIDField(source="empresa_id", read_only=True)
    createdBy = serializers.CharField(source="created_by.get_full_name", read_only=True)
    items = InvoiceItemSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoiceNo",
            "type",
            "status",
            "issueDate",
            "dueDate",
            "clientId",
            "clientName",
            "clientNif",
            "clientAddress",
            "items",
            "subtotal",
            "discountTotal",
            "taxTotal",
            "withholdingTaxRate",
            "withholdingTaxAmount",
            "grandTotal",
            "invoiceHash",
            "agtSyncDate",
            "agtResponseCode",
            "qrcodeString",
            "notes",
            "tenantId",
            "createdBy",
        ]
