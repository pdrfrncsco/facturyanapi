from rest_framework import serializers

from apps.empresas.models import Empresa


class EmpresaSerializer(serializers.ModelSerializer):
    fiscalRegime = serializers.CharField(source="fiscal_regime")
    logoUrl = serializers.URLField(source="logo_url", allow_blank=True, required=False)
    agtCertificateNo = serializers.CharField(source="agt_certificate_no", allow_blank=True, required=False)

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
            "agtCertificateNo",
        ]
