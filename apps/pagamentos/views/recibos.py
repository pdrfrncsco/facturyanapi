from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.common.permissions import TenantRolePermission
from apps.pagamentos.models import Recibo
from apps.pagamentos.serializers.recibo import ReciboSerializer, SettlementCreateSerializer
from apps.pagamentos.services.settlement import create_settlement_receipt, finalize_settlement


class ReciboViewSet(viewsets.ModelViewSet):
    queryset = Recibo.objects.all()
    serializer_class = ReciboSerializer
    permission_classes = [TenantRolePermission]

    def get_queryset(self):
        return self.queryset.filter(empresa=self.request.empresa)

    def create(self, request, *args, **kwargs):
        serializer = SettlementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        receipt = create_settlement_receipt(
            empresa=request.empresa,
            client=request.empresa.clientes_client_set.get(pk=serializer.validated_data['client']),
            items_data=serializer.validated_data['items'],
            payment_method=serializer.validated_data['payment_method'],
            notes=serializer.validated_data.get('notes', '')
        )
        
        return Response(ReciboSerializer(receipt).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def emitir(self, request, pk=None):
        receipt = self.get_object()
        try:
            issued_receipt = finalize_settlement(receipt=receipt)
            return Response(ReciboSerializer(issued_receipt).data)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
