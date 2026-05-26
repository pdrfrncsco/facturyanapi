from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.empresas.serializers.empresas import EmpresaSerializer
from apps.empresas.selectors.memberships import empresas_for_user


class UserProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(source="get_full_name")
    email = serializers.EmailField()
    role = serializers.CharField()


class NDFaturaTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["role"] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        data["user"] = UserProfileSerializer(user).data
        data["tenants"] = EmpresaSerializer(empresas_for_user(user), many=True).data
        return data
