from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views.auth import (
    MeView, 
    NDFaturaTokenObtainPairView, 
    RegisterView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    Setup2FAView,
    Verify2FAView
)


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("password-reset/<str:uidb64>/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("2fa/setup/", Setup2FAView.as_view(), name="2fa-setup"),
    path("2fa/verify/", Verify2FAView.as_view(), name="2fa-verify"),
    path("login/", NDFaturaTokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", MeView.as_view(), name="me"),
]
