from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.empresas.serializers.empresas import EmpresaSerializer
from apps.empresas.selectors.memberships import empresas_for_user


class UserProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(source="get_full_name")
    email = serializers.EmailField()
    role = serializers.CharField()


class RegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True)


class Setup2FASerializer(serializers.Serializer):
    pass


class Verify2FASerializer(serializers.Serializer):
    token = serializers.CharField(max_length=6)


class NDFaturaTokenObtainPairSerializer(TokenObtainPairSerializer):
    otp = serializers.CharField(max_length=6, required=False)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["role"] = user.role
        return token

    def validate(self, attrs):
        otp = attrs.get("otp")
        data = super().validate(attrs)
        user = self.user
        
        import pyotp
        from rest_framework.exceptions import ValidationError
        
        if user.is_2fa_enabled:
            if not otp:
                raise ValidationError({"otp": "Código 2FA obrigatório.", "2fa_required": True})
            totp = pyotp.TOTP(user.totp_secret)
            if not totp.verify(otp):
                raise ValidationError({"otp": "Código 2FA inválido."})

        data["user"] = UserProfileSerializer(user).data
        data["tenants"] = EmpresaSerializer(empresas_for_user(user), many=True).data
        return data
