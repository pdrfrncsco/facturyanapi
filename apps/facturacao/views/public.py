from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from apps.facturacao.models import Invoice
from apps.facturacao.serializers.invoices import InvoiceSerializer

class PublicInvoiceDetailView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request, token):
        try:
            invoice = Invoice.objects.select_related('empresa', 'client', 'estabelecimento').get(public_token=token)
            serializer = InvoiceSerializer(invoice)
            
            # Additional info for the portal
            data = serializer.data
            data['empresa_details'] = {
                'name': invoice.empresa.name,
                'nif': invoice.empresa.nif,
                'address': invoice.empresa.address,
                'city': invoice.empresa.city,
                'logo_url': invoice.empresa.logo.url if invoice.empresa.logo else None
            }
            
            return Response(data)
        except Invoice.DoesNotExist:
            return Response({"detail": "Factura não encontrada."}, status=status.HTTP_404_NOT_FOUND)
