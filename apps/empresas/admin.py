from django.contrib import admin

from apps.empresas.models import Empresa, EmpresaMembership


class EmpresaMembershipInline(admin.TabularInline):
    model = EmpresaMembership
    extra = 0
    autocomplete_fields = ("user",)
    fields = ("user", "role", "is_default", "is_active", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("name", "nif", "city", "country", "fiscal_regime", "is_active", "is_deleted")
    list_filter = ("country", "city", "is_active", "is_deleted")
    search_fields = ("name", "nif", "address", "agt_certificate_no")
    ordering = ("name",)
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (EmpresaMembershipInline,)


@admin.register(EmpresaMembership)
class EmpresaMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "empresa", "role", "is_default", "is_active", "created_at")
    list_filter = ("role", "is_default", "is_active")
    search_fields = ("user__email", "user__username", "empresa__name", "empresa__nif")
    autocomplete_fields = ("user", "empresa")
    readonly_fields = ("id", "created_at", "updated_at")
