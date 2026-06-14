from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from apps.pagamentos.services.multicaixa import process_payment_notification
from decimal import Decimal

class MulticaixaWebhookView(APIView):
    """
    Webhook público para receber notificações de pagamento Multicaixa.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        # Nota: Em produção, validar assinatura HMAC/IP do provedor.
        data = request.data
        entity_code = data.get("entity_code")
        reference = data.get("reference")
        amount_str = data.get("amount")
        transaction_id = data.get("transaction_id")
        
        if not all([entity_code, reference, amount_str]):
            return Response({"detail": "Campos obrigatórios (entity_code, reference, amount) em falta."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            amount = Decimal(str(amount_str))
            ref = process_payment_notification(
                entity_code=entity_code,
                reference_number=reference,
                amount=amount,
                transaction_id=transaction_id
            )
            
            if ref:
                return Response({"status": "ok", "message": f"Pagamento da fatura {ref.invoice.invoice_no} processado."})
            
            return Response({"status": "not_found", "message": "Referência pendente não encontrada."}, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
