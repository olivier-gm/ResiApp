from django.contrib import admin

from .models import EmailDelivery


@admin.register(EmailDelivery)
class EmailDeliveryAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "attempts", "sent_at", "last_error")
    list_filter = ("sent_at",)
    exclude = ("to", "subject", "body")
    readonly_fields = ("id", "created_at", "attempts", "next_attempt_at", "sent_at", "last_error")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
