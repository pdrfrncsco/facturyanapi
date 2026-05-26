from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.empresas.serializers.empresas import EmpresaSerializer
from apps.empresas.selectors.memberships import empresas_for_user


class EmpresaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EmpresaSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name", "nif"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        return empresas_for_user(self.request.user)
