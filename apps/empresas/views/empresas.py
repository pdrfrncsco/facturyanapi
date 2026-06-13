from rest_framework import viewsets, mixins, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.empresas.serializers.empresas import EmpresaSerializer
from apps.empresas.selectors.memberships import empresas_for_user
from apps.empresas.services.keys import rotate_empresa_keys


class EmpresaViewSet(mixins.RetrieveModelMixin, 
                     mixins.UpdateModelMixin, 
                     mixins.ListModelMixin, 
                     viewsets.GenericViewSet):
    """
    ViewSet para Empresas. 
    Permite listagem, detalhe e actualização de perfil.
    Criação e remoção são restritas a fluxos de onboarding não expostos aqui.
    """
    serializer_class = EmpresaSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name", "nif"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        return empresas_for_user(self.request.user)

    @action(detail=True, methods=["post"], url_path="rotate-keys")
    def rotate_keys(self, request, pk=None):
        empresa = self.get_object()
        # Idealmente apenas admins do tenant deveriam fazer isto
        rotate_empresa_keys(empresa)
        return Response({"message": "Chaves RSA geradas com sucesso."}, status=status.HTTP_200_OK)
