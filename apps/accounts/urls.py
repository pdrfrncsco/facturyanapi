from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views.auth import MeView, NDFaturaTokenObtainPairView


urlpatterns = [
    path("login/", NDFaturaTokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", MeView.as_view(), name="me"),
]
