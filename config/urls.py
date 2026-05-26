from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.auditoria.views.audit_logs import AuditLogViewSet
from apps.clientes.views.clients import ClientViewSet
from apps.empresas.views.empresas import EmpresaViewSet
from apps.facturacao.views.invoices import InvoiceViewSet
from apps.produtos.views.products import ProductViewSet
from apps.relatorios.views.dashboard import DashboardStatsView
from apps.saft.views.export import SaftExportView


router = DefaultRouter()
router.register("empresas", EmpresaViewSet, basename="empresas")
router.register("clientes", ClientViewSet, basename="clientes")
router.register("produtos", ProductViewSet, basename="produtos")
router.register("facturas", InvoiceViewSet, basename="facturas")
router.register("auditoria", AuditLogViewSet, basename="auditoria")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/dashboard/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("api/v1/saft/export/", SaftExportView.as_view(), name="saft-export"),
    path("api/v1/", include(router.urls)),
]
