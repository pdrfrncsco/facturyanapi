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
    estabelecimentoId = serializers.UUIDField(source="estabelecimento_id", read_only=True)
    estabelecimentoCode = serializers.CharField(source="estabelecimento.code", read_only=True)
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
    exchangeRate = serializers.DecimalField(source="exchange_rate", max_digits=18, decimal_places=4, read_only=True)
    publicToken = serializers.UUIDField(source="public_token", read_only=True)
    invoiceHash = serializers.CharField(source="invoice_hash", read_only=True)
    
    # Goods Movement
    vehiclePlate = serializers.CharField(source="vehicle_plate", required=False, allow_null=True)
    driverName = serializers.CharField(source="driver_name", required=False, allow_null=True)
    loadingPoint = serializers.CharField(source="loading_point", required=False, allow_null=True)
    deliveryPoint = serializers.CharField(source="delivery_point", required=False, allow_null=True)
    loadingDate = serializers.DateTimeField(source="loading_date", required=False, allow_null=True)
    deliveryDate = serializers.DateTimeField(source="delivery_date", required=False, allow_null=True)

    previousHash = serializers.CharField(source="previous_hash", read_only=True)
    agtSyncDate = serializers.DateTimeField(source="agt_sync_date", read_only=True)
    agtResponseCode = serializers.CharField(source="agt_response_code", read_only=True)
    qrcodeString = serializers.CharField(source="qrcode_string", read_only=True)
    cancelledAt = serializers.DateTimeField(source="cancelled_at", read_only=True)
    cancellationReason = serializers.CharField(source="cancellation_reason", read_only=True)
    cancelledBy = serializers.CharField(source="cancelled_by.get_full_name", read_only=True)
    originDocumentId = serializers.UUIDField(source="origin_document_id", read_only=True)
    rectificationReason = serializers.CharField(source="rectification_reason", read_only=True)
    tenantId = serializers.UUIDField(source="empresa_id", read_only=True)
    createdBy = serializers.CharField(source="created_by.get_full_name", read_only=True)
    items = InvoiceItemSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoiceNo",
            "estabelecimentoId",
            "estabelecimentoCode",
            "type",
            "status",
            "currency",
            "exchangeRate",
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
            "publicToken",
            "vehiclePlate",
            "driverName",
            "loadingPoint",
            "deliveryPoint",
            "loadingDate",
            "deliveryDate",
            "invoiceHash",
            "previousHash",
            "agtSyncDate",
            "agtResponseCode",
            "qrcodeString",
            "cancelledAt",
            "cancellationReason",
            "cancelledBy",
            "notes",
            "originDocumentId",
            "rectificationReason",
            "tenantId",
            "createdBy",
        ]


class DraftInvoiceItemInputSerializer(serializers.Serializer):
    productId = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    price = serializers.DecimalField(max_digits=18, decimal_places=2, required=False)
    discount = serializers.DecimalField(max_digits=5, decimal_places=2, default=0)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        value["product_id"] = value.pop("productId")
        return value


class CancelInvoiceInputSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=500, trim_whitespace=True)


class DraftInvoiceInputSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=Invoice.Type.choices)
    estabelecimentoId = serializers.UUIDField(required=False, allow_null=True)
    clientId = serializers.UUIDField()
    currency = serializers.CharField(max_length=3, default="AOA")
    exchangeRate = serializers.DecimalField(max_digits=18, decimal_places=4, required=False)
    dueDate = serializers.DateField(required=False, allow_null=True)
    withholdingTaxRate = serializers.DecimalField(max_digits=5, decimal_places=2, default=0)
    notes = serializers.CharField(required=False, allow_blank=True)
    originDocumentId = serializers.UUIDField(required=False, allow_null=True)
    rectificationReason = serializers.CharField(required=False, allow_blank=True)
    items = DraftInvoiceItemInputSerializer(many=True)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        value["client_id"] = value.pop("clientId")
        value["due_date"] = value.pop("dueDate", None)
        value["withholding_tax_rate"] = value.pop("withholdingTaxRate", 0)
        
        if "estabelecimentoId" in value:
            value["estabelecimento_id"] = value.pop("estabelecimentoId")
        if "exchangeRate" in value:
            value["exchange_rate"] = value.pop("exchangeRate")
            
        if "originDocumentId" in value:
            value["origin_document_id"] = value.pop("originDocumentId")
        if "rectificationReason" in value:
            value["rectification_reason"] = value.pop("rectificationReason")
        return value
