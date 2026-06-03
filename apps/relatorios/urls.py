from django.urls import path
from apps.relatorios.views.reports import IvaMapView, AccountStatementView

urlpatterns = [
    path("iva-map/", IvaMapView.as_view(), name="iva-map"),
    path("account-statement/<uuid:client_id>/", AccountStatementView.as_view(), name="account-statement"),
]
