from django.db import models
from apps.common.models import TenantOwnedModel

class FiscalCertificate(TenantOwnedModel):
    """
    Certificado da AGT e chaves RSA.
    """
    # Use OneToOneField but ensure it's compatible with TenantOwnedModel (which has empresa FK)
    # Actually TenantOwnedModel already has empresa. For a OneToOne relationship:
    certificate_file = models.FileField(upload_to="certificates/", null=True, blank=True)
    certificate_password = models.CharField(max_length=512, blank=True) # Encriptado com Fernet
    serial_number = models.CharField(max_length=100, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    
    # Chaves JWS e AGT
    software_private_key = models.TextField(blank=True)
    software_public_key = models.TextField(blank=True)
    agt_private_key = models.TextField(blank=True, help_text="Chave privada do contribuinte fornecida pela AGT")

    class Meta:
        verbose_name = "Certificado Fiscal"
        unique_together = [("empresa",)]

    def __str__(self):
        return f"Certificate for {self.empresa.name}"

class DocumentSeries(TenantOwnedModel):
    """
    Séries de documentos comunicadas e autorizadas pela AGT.
    Consolida FiscalSeries e DocumentSeries.
    """
    class Status(models.TextChoices):
        DRAFT = "Draft", "Rascunho"
        REQUESTED = "Requested", "Solicitada"
        APPROVED = "Approved", "Aprovada"
        REJECTED = "Rejected", "Rejeitada"
        INACTIVE = "Inactive", "Inativa"

    estabelecimento = models.ForeignKey(
        "empresas.Estabelecimento", 
        on_delete=models.CASCADE, 
        related_name="document_series"
    )
    document_type = models.CharField(max_length=8) # FT, FR, NC, ND, GR, PP
    series_code = models.CharField(max_length=24) # Ex: SEDE
    fiscal_year = models.PositiveIntegerField()
    agt_registration_id = models.CharField(max_length=100, blank=True)
    current_number = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("empresa", "estabelecimento", "series_code", "document_type", "fiscal_year")]
        indexes = [models.Index(fields=["empresa", "estabelecimento", "document_type", "is_active"])]

    def __str__(self):
        return f"{self.document_type} {self.fiscal_year}/{self.series_code}"

class FiscalEvent(TenantOwnedModel):
    """
    Audit log específico para eventos fiscais.
    """
    class EventType(models.TextChoices):
        DOCUMENT_CREATED = 'DOCUMENT_CREATED', 'Documento criado'
        DOCUMENT_SIGNED = 'DOCUMENT_SIGNED', 'Assinado JWS'
        DOCUMENT_SENT = 'DOCUMENT_SENT', 'Enviado AGT'
        DOCUMENT_ACCEPTED = 'DOCUMENT_ACCEPTED', 'Aceite AGT'
        DOCUMENT_REJECTED = 'DOCUMENT_REJECTED', 'Rejeitado AGT'
        DOCUMENT_CANCELLED = 'DOCUMENT_CANCELLED', 'Cancelado'
        CERTIFICATE_UPDATED = 'CERTIFICATE_UPDATED', 'Certificado actualizado'
        ACTIVATION_STARTED = 'ACTIVATION_STARTED', 'Ativação iniciada'

    entity_type = models.CharField(max_length=50) # invoice, recibo, empresa
    entity_id = models.UUIDField()
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    payload = models.JSONField(default=dict)
    agt_request_id = models.CharField(max_length=100, blank=True)
    agt_response = models.JSONField(default=dict)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type} - {self.created_at}"
