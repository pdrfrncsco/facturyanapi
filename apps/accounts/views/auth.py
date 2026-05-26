from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.serializers.auth import NDFaturaTokenObtainPairSerializer, UserProfileSerializer
from apps.empresas.serializers.empresas import EmpresaSerializer
from apps.empresas.selectors.memberships import empresas_for_user


class NDFaturaTokenObtainPairView(TokenObtainPairView):
    serializer_class = NDFaturaTokenObtainPairSerializer


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "user": UserProfileSerializer(request.user).data,
                "tenants": EmpresaSerializer(empresas_for_user(request.user), many=True).data,
            }
        )
