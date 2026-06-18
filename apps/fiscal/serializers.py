from rest_framework import serializers


class FiscalCertificateStatusSerializer(serializers.Serializer):
    exists = serializers.BooleanField()
    serialNumber = serializers.CharField(allow_blank=True)
    issuedAt = serializers.DateTimeField(allow_null=True)
    expiresAt = serializers.DateTimeField(allow_null=True)
    isActive = serializers.BooleanField()
    isExpired = serializers.BooleanField()
    isValid = serializers.BooleanField()


class FiscalSeriesStatusSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    documentType = serializers.CharField()
    code = serializers.CharField()
    fiscalYear = serializers.IntegerField()
    currentNumber = serializers.IntegerField()
    isActive = serializers.BooleanField()
    status = serializers.CharField()
    agtRegistrationId = serializers.CharField(allow_blank=True, required=False)
    estabelecimentoId = serializers.UUIDField(allow_null=True)
    estabelecimentoCode = serializers.CharField(allow_null=True)


class LastAgtSyncStatusSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    invoiceId = serializers.UUIDField()
    invoiceNo = serializers.CharField()
    status = serializers.CharField()
    responseCode = serializers.CharField(allow_blank=True)
    errorMessage = serializers.CharField(allow_blank=True)
    requestId = serializers.CharField(allow_blank=True)
    createdAt = serializers.DateTimeField()
    updatedAt = serializers.DateTimeField()


class ElectronicBillingStatusSerializer(serializers.Serializer):
    status = serializers.CharField()
    canStartActivation = serializers.BooleanField()
    canUploadCertificate = serializers.BooleanField()
    canIssueInvoices = serializers.BooleanField()
    certificate = FiscalCertificateStatusSerializer()
    series = FiscalSeriesStatusSerializer(many=True)
    lastAgtSync = LastAgtSyncStatusSerializer(allow_null=True)
    warnings = serializers.ListField(child=serializers.CharField())


class FiscalCertificateUploadSerializer(serializers.Serializer):
    certificate = serializers.FileField()
    password = serializers.CharField(write_only=True, trim_whitespace=False, allow_blank=True, required=False)

    def validate_certificate(self, value):
        name = value.name.lower()
        if not (name.endswith(".pfx") or name.endswith(".p12")):
            raise serializers.ValidationError("Carregue um ficheiro .pfx ou .p12.")
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("O certificado nao pode exceder 2MB.")
        return value


class FiscalSeriesRequestSerializer(serializers.Serializer):
    """Input para solicitar uma nova série fiscal."""
    estabelecimento_id = serializers.UUIDField(help_text="ID do estabelecimento")
    document_type = serializers.ChoiceField(
        choices=["FT", "FR", "NC", "ND", "GR", "PP"],
        help_text="Tipo de documento fiscal (FT, FR, NC, ND, GR, PP)",
    )
    series_code = serializers.CharField(
        max_length=24,
        help_text="Código da série (ex: SEDE, LOJA1). Deve corresponder ao código do estabelecimento.",
    )


class FiscalEventSerializer(serializers.Serializer):
    """Serializer para eventos fiscais de auditoria."""
    id = serializers.UUIDField()
    eventType = serializers.CharField(source="event_type")
    entityType = serializers.CharField(source="entity_type")
    entityId = serializers.UUIDField(source="entity_id")
    payload = serializers.DictField()
    agtRequestId = serializers.CharField(source="agt_request_id", allow_blank=True)
    createdAt = serializers.DateTimeField(source="created_at")
