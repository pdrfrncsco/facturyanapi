from django.db import transaction
from apps.fiscal.models import DocumentSeries
import random
import string

class SeriesService:
    @staticmethod
    def get_next_number(empresa, estabelecimento, document_type) -> tuple[str, int, str]:
        """
        Gera o próximo número sequencial para uma série activa.
        Retorna (series_code, number, previous_hash).
        """
        with transaction.atomic():
            series = DocumentSeries.objects.select_for_update().get(
                empresa=empresa,
                estabelecimento=estabelecimento,
                document_type=document_type,
                is_active=True
            )
            
            number = series.current_number
            series.current_number += 1
            series.save(update_fields=['current_number'])
            
            # Obter o hash do documento anterior da mesma série
            from apps.facturacao.models import Invoice
            last_doc = Invoice.objects.filter(
                empresa=empresa,
                estabelecimento=estabelecimento,
                type=document_type,
                invoice_no__contains=series.series_code
            ).exclude(invoice_hash="").order_by("-issue_date", "-created_at").first()
            
            previous_hash = last_doc.invoice_hash if last_doc else ""
            
        return series.series_code, number, previous_hash

    @staticmethod
    def format_invoice_no(doc_type, series_code, number) -> str:
        """Ex: FT SEDE/00001"""
        return f"{doc_type} {series_code}/{number:05d}"
