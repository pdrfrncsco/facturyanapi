from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import status
from django.core.exceptions import ValidationError
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
import pyotp

from apps.accounts.serializers.auth import (
    NDFaturaTokenObtainPairSerializer, 
    UserProfileSerializer,
    RegisterSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    Verify2FASerializer
)
from apps.accounts.serializers.members import TenantMemberSerializer, TenantMemberUpdateSerializer
from apps.accounts.services.auth import register_user
from apps.common.permissions import TenantRolePermission
from apps.empresas.models import EmpresaMembership
from apps.empresas.serializers.empresas import EmpresaSerializer
from apps.empresas.selectors.memberships import empresas_for_user

User = get_user_model()


class Setup2FAView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.is_2fa_enabled:
            return Response({"error": "2FA já está activado."}, status=status.HTTP_400_BAD_REQUEST)
        
        if not user.totp_secret:
            user.totp_secret = pyotp.random_base32()
            user.save()
            
        totp = pyotp.TOTP(user.totp_secret)
        provisioning_uri = totp.provisioning_uri(name=user.email, issuer_name="FACTURYAN")
        
        return Response({
            "secret": user.totp_secret,
            "qr_code_url": provisioning_uri
        })


class Verify2FAView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        serializer = Verify2FASerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(serializer.validated_data["token"]):
            return Response({"error": "Código 2FA inválido."}, status=status.HTTP_400_BAD_REQUEST)
            
        user.is_2fa_enabled = True
        user.save()
        
        return Response({"message": "2FA activado com sucesso."})


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email=email).first()
        if user:
            token = PasswordResetTokenGenerator().make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = f"{settings.CORS_ALLOWED_ORIGINS[0]}/reset-password/{uid}/{token}"
            
            # Simulated email send
            send_mail(
                subject="Recuperação de Palavra-passe - FACTURYAN",
                message=f"Para recuperar a sua palavra-passe clique no link: {reset_url}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
            
        return Response({"message": "Se o email existir, enviámos um link de recuperação."}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, uidb64):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"error": "Link inválido."}, status=status.HTTP_400_BAD_REQUEST)

        if not PasswordResetTokenGenerator().check_token(user, serializer.validated_data["token"]):
            return Response({"error": "Token expirado ou inválido."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data["password"])
        user.save()
        return Response({"message": "Palavra-passe alterada com sucesso."}, status=status.HTTP_200_OK)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = register_user(**serializer.validated_data)
        except ValidationError as exc:
            return Response({"error": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(
            UserProfileSerializer(user).data, 
            status=status.HTTP_201_CREATED
        )


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


class TenantMembersView(APIView):
    permission_classes = [TenantRolePermission]
    role_permissions = {
        "get": TenantRolePermission.ALL_ROLES,
    }

    def get(self, request):
        empresa = getattr(request, "empresa", None)
        if empresa is None:
            return Response([], status=status.HTTP_200_OK)

        memberships = (
            EmpresaMembership.objects.filter(empresa=empresa)
            .select_related("user")
            .order_by("user__first_name", "user__last_name", "user__email")
        )
        serializer = TenantMemberSerializer(memberships, many=True, context={"request": request})
        return Response(serializer.data)


class TenantMemberDetailView(APIView):
    permission_classes = [TenantRolePermission]
    role_permissions = {
        "patch": TenantRolePermission.FISCAL_MANAGER_ROLES,
    }

    def patch(self, request, membership_id):
        empresa = getattr(request, "empresa", None)
        if empresa is None:
            return Response({"detail": "Empresa inválida."}, status=status.HTTP_400_BAD_REQUEST)

        membership = (
            EmpresaMembership.objects.select_related("user", "empresa")
            .filter(id=membership_id, empresa=empresa)
            .first()
        )
        if membership is None:
            return Response({"detail": "Utilizador não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        serializer = TenantMemberUpdateSerializer(
            membership,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(TenantMemberSerializer(membership, context={"request": request}).data, status=status.HTTP_200_OK)
