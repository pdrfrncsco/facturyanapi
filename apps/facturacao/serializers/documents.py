from rest_framework import serializers

from apps.facturacao.models import AgtSyncLog, InvoiceDocument


class AgtSyncLogSerializer(serializers.ModelSerializer):
    invoiceId = serializers.UUIDField(source="invoice_id", read_only=True)
    responseCode = serializers.CharField(source="response_code", read_only=True)
    errorMessage = serializers.CharField(source="error_message", read_only=True)
    attemptCount = serializers.IntegerField(source="attempt_count", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = AgtSyncLog
        fields = ["id", "invoiceId", "status", "responseCode", "errorMessage", "attemptCount", "createdAt"]


class InvoiceDocumentSerializer(serializers.ModelSerializer):
    invoiceId = serializers.UUIDField(source="invoice_id", read_only=True)
    generatedAt = serializers.DateTimeField(source="generated_at", read_only=True)
    errorMessage = serializers.CharField(source="error_message", read_only=True)
    downloadUrl = serializers.SerializerMethodField()

    class Meta:
        model = InvoiceDocument
        fields = ["id", "invoiceId", "status", "generatedAt", "downloadUrl", "errorMessage"]

    def get_downloadUrl(self, obj) -> str | None:
        if obj.status != InvoiceDocument.Status.READY or not obj.file:
            return None
        request = self.context.get("request")
        if request is None:
            return None
        return request.build_absolute_uri(f"/api/v1/facturas/{obj.invoice_id}/pdf/")
