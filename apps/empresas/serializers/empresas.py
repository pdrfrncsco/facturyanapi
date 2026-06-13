from rest_framework import serializers

from apps.empresas.models import Empresa


class EmpresaSerializer(serializers.ModelSerializer):
    fiscalRegime = serializers.CharField(source="fiscal_regime")
    logoUrl = serializers.URLField(source="logo_url", allow_blank=True, required=False)
    systemName = serializers.CharField(source="system_name", required=False)
    primaryColor = serializers.CharField(source="primary_color", required=False)
    agtCertificateNo = serializers.CharField(source="agt_certificate_no", allow_blank=True, required=False)
    softwarePublicKey = serializers.CharField(source="software_public_key", read_only=True)

    class Meta:
        model = Empresa
        fields = [
            "id",
            "name",
            "nif",
            "address",
            "city",
            "country",
            "fiscalRegime",
            "logoUrl",
            "systemName",
            "primaryColor",
            "agtCertificateNo",
            "softwarePublicKey",
        ]
