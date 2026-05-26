from django.contrib import admin

from apps.auditoria.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "empresa", "user_name", "entity_type", "entity_id", "ip_address")
    list_filter = ("empresa", "action", "entity_type", "created_at")
    search_fields = ("action", "details", "user_name", "entity_type", "entity_id", "empresa__name", "empresa__nif")
    autocomplete_fields = ("empresa", "user")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    readonly_fields = (
        "id",
        "empresa",
        "user",
        "user_name",
        "action",
        "details",
        "entity_type",
        "entity_id",
        "ip_address",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        return False
