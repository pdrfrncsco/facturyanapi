from django.contrib import admin

from apps.produtos.models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "price", "stock", "tax_rate", "unit", "empresa", "is_deleted")
    list_filter = ("empresa", "category", "unit", "tax_rate", "is_deleted")
    search_fields = ("code", "name", "category", "empresa__name", "empresa__nif")
    autocomplete_fields = ("empresa",)
    ordering = ("empresa", "code")
    readonly_fields = ("id", "created_at", "updated_at")
