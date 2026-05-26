from django.contrib import admin

from apps.clientes.models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "nif", "email", "phone", "city", "empresa", "is_deleted")
    list_filter = ("empresa", "city", "country", "is_deleted")
    search_fields = ("name", "nif", "email", "phone", "empresa__name", "empresa__nif")
    autocomplete_fields = ("empresa",)
    ordering = ("name",)
    readonly_fields = ("id", "created_at", "updated_at")
