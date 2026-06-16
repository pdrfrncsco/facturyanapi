from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.clientes.models import Client
from apps.common.permissions import TenantRolePermission
from apps.pagamentos.models import Recibo
from apps.pagamentos.serializers.recibo import ReciboSerializer, SettlementCreateSerializer
from apps.pagamentos.services.settlement import create_settlement_receipt, finalize_settlement, cancel_receipt


class ReciboViewSet(viewsets.ModelViewSet):
    queryset = Recibo.objects.all()
    serializer_class = ReciboSerializer
    permission_classes = [TenantRolePermission]
    role_permissions = {
        "list": TenantRolePermission.ALL_ROLES,
        "retrieve": TenantRolePermission.ALL_ROLES,
        "create": TenantRolePermission.WRITE_ROLES,
        "emitir": TenantRolePermission.FISCAL_MANAGER_ROLES,
        "cancelar": TenantRolePermission.FISCAL_MANAGER_ROLES,
        "enviar_email": TenantRolePermission.ALL_ROLES,
        "pdf": TenantRolePermission.ALL_ROLES,
    }

    def get_queryset(self):
        return self.queryset.filter(empresa=self.request.empresa)

    def create(self, request, *args, **kwargs):
        serializer = SettlementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        client = Client.objects.filter(pk=serializer.validated_data["client"], empresa=request.empresa).first()
        if client is None:
            return Response({"client": "Cliente inválido para a empresa activa."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            receipt = create_settlement_receipt(
                empresa=request.empresa,
                client=client,
                items_data=serializer.validated_data["items"],
                payment_method=serializer.validated_data["payment_method"],
                notes=serializer.validated_data.get("notes", ""),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(ReciboSerializer(receipt).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def emitir(self, request, pk=None):
        receipt = self.get_object()
        try:
            issued_receipt = finalize_settlement(
                receipt=receipt,
                user=request.user,
                request=request
            )
            return Response(ReciboSerializer(issued_receipt).data)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='cancelar')
    def cancelar(self, request, pk=None):
        receipt = self.get_object()
        try:
            cancelled_receipt = cancel_receipt(
                receipt=receipt,
                user=request.user,
                request=request
            )
            return Response(ReciboSerializer(cancelled_receipt).data)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='enviar-email')
    def enviar_email(self, request, pk=None):
        from apps.notificacoes.services.email import send_receipt_email
        receipt = self.get_object()
        success = send_receipt_email(receipt=receipt)
        if success:
            return Response({"status": "sent"})
        return Response({"detail": "Falha ao enviar e-mail."}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        from django.http import FileResponse
        from apps.pagamentos.services.pdf_generation import generate_receipt_pdf_file
        
        receipt = self.get_object()
        pdf_file = generate_receipt_pdf_file(receipt=receipt)
        return FileResponse(pdf_file.open('rb'), as_attachment=True, filename=pdf_file.name)
