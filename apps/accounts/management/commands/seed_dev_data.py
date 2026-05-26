from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.clientes.models import Client
from apps.empresas.models import Empresa, EmpresaMembership
from apps.produtos.models import Product


class Command(BaseCommand):
    help = "Seed local development data aligned with ndfatura-web mocks."

    def handle(self, *args, **options):
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            email="ndeasdigital@gmail.com",
            defaults={
                "username": "ndeasdigital",
                "first_name": "Manuel",
                "last_name": "Bento",
                "role": "Admin",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            user.set_password("admin12345")
            user.save(update_fields=["password"])

        empresas = [
            {
                "name": "Sodiam Exportações Lda",
                "nif": "540398271",
                "address": "Av. Lenine, Edifício Torres Atlântico, Piso 7",
                "city": "Luanda",
                "country": "Angola",
                "fiscal_regime": "Regime Geral (Transmissões de Bens e Serviços)",
                "agt_certificate_no": "241/AGT/2026",
            },
            {
                "name": "Sonangol Distribuição S.A.",
                "nif": "540101928",
                "address": "Rua Rainha Ginga, n.º 29-31",
                "city": "Luanda",
                "country": "Angola",
                "fiscal_regime": "Regime Geral",
                "agt_certificate_no": "242/AGT/2026",
            },
        ]

        seeded_empresas = []
        for index, payload in enumerate(empresas):
            empresa, _ = Empresa.objects.update_or_create(nif=payload["nif"], defaults=payload)
            seeded_empresas.append(empresa)
            EmpresaMembership.objects.update_or_create(
                user=user,
                empresa=empresa,
                defaults={"role": "owner", "is_default": index == 0, "is_active": True},
            )

        primary = seeded_empresas[0]
        clients = [
            {
                "name": "TAAG Linhas Aéreas de Angola S.A.",
                "nif": "540110294",
                "email": "financeiro@taag.co.ao",
                "phone": "+244 923 440 221",
                "address": "Rua da Missão, N.º 123-141",
                "city": "Luanda",
                "country": "Angola",
            },
            {
                "name": "Kero Supermercados Group Lda",
                "nif": "540889271",
                "email": "contabilidade@kero.co.ao",
                "phone": "+244 912 300 450",
                "address": "Av. Pedro de Castro Van-Dúnem Loy, Talatona",
                "city": "Luanda",
                "country": "Angola",
            },
        ]
        for payload in clients:
            Client.objects.update_or_create(empresa=primary, nif=payload["nif"], defaults=payload)

        products = [
            {
                "code": "SERV-01",
                "name": "Consultoria e Auditoria Tecnológica Especializada",
                "category": "Serviços",
                "price": Decimal("1850000.00"),
                "stock": Decimal("999.000"),
                "tax_rate": Decimal("14.00"),
                "unit": "SERV",
            },
            {
                "code": "LIC-ERP-02",
                "name": "Subscrição Anual NDFATURA Cloud Enterprise SaaS",
                "category": "Software",
                "price": Decimal("450000.00"),
                "stock": Decimal("80.000"),
                "tax_rate": Decimal("14.00"),
                "unit": "UN",
            },
            {
                "code": "FUEL-03",
                "name": "Gasóleo Industrial Isento de IVA",
                "category": "Combustível",
                "price": Decimal("350.00"),
                "stock": Decimal("50000.000"),
                "tax_rate": Decimal("0.00"),
                "exemption_code": "M10",
                "unit": "L",
            },
        ]
        for payload in products:
            Product.objects.update_or_create(empresa=primary, code=payload["code"], defaults=payload)

        self.stdout.write(self.style.SUCCESS("Development data seeded. Login: ndeasdigital@gmail.com / admin12345"))
