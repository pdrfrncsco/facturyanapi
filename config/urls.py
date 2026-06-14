from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.auditoria.views.audit_logs import AuditLogViewSet
from apps.clientes.views.clients import ClientViewSet
from apps.empresas.views.empresas import EmpresaViewSet
from apps.empresas.views.estabelecimentos import EstabelecimentoViewSet
from apps.facturacao.views.invoices import InvoiceViewSet
from apps.facturacao.views.public import PublicInvoiceDetailView
from apps.integracoes.views import MulticaixaWebhookView
from apps.facturacao.views.recurring import RecurringInvoiceViewSet
from apps.facturacao.views.currency import ExchangeRateViewSet
from apps.pagamentos.views.recibos import ReciboViewSet
from apps.produtos.views.products import ProductViewSet, StockMovementViewSet
from apps.relatorios.views.dashboard import DashboardStatsView
from apps.saft.views.export import SaftExportView
from apps.saft.views.jobs import SaftExportJobView


router = DefaultRouter()
router.register("empresas", EmpresaViewSet, basename="empresas")
router.register("estabelecimentos", EstabelecimentoViewSet, basename="estabelecimentos")
router.register("clientes", ClientViewSet, basename="clientes")
router.register("produtos", ProductViewSet, basename="produtos")
router.register("movimentos-stock", StockMovementViewSet, basename="movimentos-stock")
router.register("facturas", InvoiceViewSet, basename="facturas")
router.register("recorrentes", RecurringInvoiceViewSet, basename="recorrentes")
router.register("recibos", ReciboViewSet, basename="recibos")
router.register("taxas-cambio", ExchangeRateViewSet, basename="taxas-cambio")
router.register("auditoria", AuditLogViewSet, basename="auditoria")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/public/facturas/<uuid:token>/", PublicInvoiceDetailView.as_view(), name="public-invoice-detail"),
    path("api/v1/public/webhooks/multicaixa/", MulticaixaWebhookView.as_view(), name="public-multicaixa-webhook"),
    path("api/v1/dashboard/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("api/v1/relatorios/", include("apps.relatorios.urls")),
    path("api/v1/saft/export/", SaftExportView.as_view(), name="saft-export"),
    path("api/v1/saft/export/<uuid:job_id>/", SaftExportJobView.as_view(), name="saft-export-job"),
    path("api/v1/", include(router.urls)),
]
