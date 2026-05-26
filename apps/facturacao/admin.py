from django.contrib import admin

from apps.facturacao.models import FiscalSeries, Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    autocomplete_fields = ("empresa", "product")
    fields = (
        "product",
        "product_name",
        "quantity",
        "price",
        "tax_rate",
        "discount",
        "subtotal",
        "total_tax",
        "total",
    )
    readonly_fields = ("product_name", "subtotal", "total_tax", "total")

    def has_delete_permission(self, request, obj=None):
        return obj is None or obj.status == Invoice.Status.DRAFT

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status != Invoice.Status.DRAFT:
            return tuple(field.name for field in self.model._meta.fields)
        return self.readonly_fields


@admin.register(FiscalSeries)
class FiscalSeriesAdmin(admin.ModelAdmin):
    list_display = ("code", "document_type", "fiscal_year", "current_number", "empresa", "is_active", "is_deleted")
    list_filter = ("empresa", "document_type", "fiscal_year", "is_active", "is_deleted")
    search_fields = ("code", "document_type", "empresa__name", "empresa__nif")
    autocomplete_fields = ("empresa",)
    ordering = ("empresa", "-fiscal_year", "document_type", "code")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_no", "type", "status", "client_name", "client_nif", "grand_total", "issue_date", "empresa")
    list_filter = ("empresa", "type", "status", "issue_date", "is_deleted")
    search_fields = ("invoice_no", "client_name", "client_nif", "invoice_hash", "empresa__name", "empresa__nif")
    autocomplete_fields = ("empresa", "client", "created_by")
    date_hierarchy = "issue_date"
    ordering = ("-created_at",)
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "invoice_hash",
        "previous_hash",
        "qrcode_string",
        "agt_sync_date",
        "agt_response_code",
    )
    inlines = (InvoiceItemInline,)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status != Invoice.Status.DRAFT:
            return tuple(field.name for field in self.model._meta.fields)
        return self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status != Invoice.Status.DRAFT:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ("invoice", "product_name", "quantity", "price", "tax_rate", "subtotal", "total_tax", "total", "empresa")
    list_filter = ("empresa", "tax_rate", "is_deleted")
    search_fields = ("invoice__invoice_no", "product_name", "product__code", "empresa__name", "empresa__nif")
    autocomplete_fields = ("empresa", "invoice", "product")
    readonly_fields = ("id", "created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.invoice.status != Invoice.Status.DRAFT:
            return tuple(field.name for field in self.model._meta.fields)
        return self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        if obj and obj.invoice.status != Invoice.Status.DRAFT:
            return False
        return super().has_delete_permission(request, obj)
