from django.db import models
from apps.common.models import TimeStampedModel, UUIDModel
from apps.empresas.models.empresa import Empresa
from apps.empresas.models.estabelecimento import Estabelecimento

class FiscalCertificate(UUIDModel, TimeStampedModel):
    """
    Certificado da AGT e chaves RSA.
    Pode ser um certificado global do produtor ou específico por tenant.
    """
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name="fiscal_certificate")
    certificate_file = models.FileField(upload_to="certificates/", null=True, blank=True)
    certificate_password = models.CharField(max_length=512, blank=True) # Em produção usar encriptação Fernet
    serial_number = models.CharField(max_length=100, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    
    # Chaves JWS
    software_private_key = models.TextField(blank=True)
    software_public_key = models.TextField(blank=True)
    agt_private_key = models.TextField(blank=True, help_text="Chave privada do contribuinte fornecida pela AGT")

    def __str__(self):
        return f"Certificate for {self.empresa.name}"

class DocumentSeries(UUIDModel, TimeStampedModel):
    """
    Séries de documentos comunicadas e autorizadas pela AGT.
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="document_series")
    estabelecimento = models.ForeignKey(Estabelecimento, on_delete=models.CASCADE, related_name="document_series")
    document_type = models.CharField(max_length=5) # FT, FR, NC, RC, ND, GR, PP
    series_code = models.CharField(max_length=50) # Ex: SEDE
    agt_registration_id = models.CharField(max_length=100, blank=True)
    current_number = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['empresa', 'estabelecimento', 'document_type', 'series_code']

    def __str__(self):
        return f"{self.document_type} - {self.series_code}"

class FiscalEvent(UUIDModel, TimeStampedModel):
    """
    Audit log específico para eventos fiscais.
    """
    EVENTS = [
        ('DOCUMENT_CREATED', 'Documento criado'),
        ('DOCUMENT_SIGNED', 'Assinado JWS'),
        ('DOCUMENT_SENT', 'Enviado AGT'),
        ('DOCUMENT_ACCEPTED', 'Aceite AGT'),
        ('DOCUMENT_REJECTED', 'Rejeitado AGT'),
        ('DOCUMENT_CANCELLED', 'Cancelado'),
        ('CERTIFICATE_UPDATED', 'Certificado actualizado'),
    ]
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="fiscal_events")
    entity_type = models.CharField(max_length=50) # invoice, recibo
    entity_id = models.UUIDField()
    event_type = models.CharField(max_length=30, choices=EVENTS)
    payload = models.JSONField(default=dict)
    agt_request_id = models.CharField(max_length=100, blank=True)
    agt_response = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.event_type} - {self.created_at}"
