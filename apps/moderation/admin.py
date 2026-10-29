from django.contrib import admin
from django.utils import timezone

from apps.notifications.services import notify

from .forms import ReportAdminForm
from .models import Report, ReportAccess


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    form = ReportAdminForm
    list_display = ("listing_title_snapshot", "reason", "status", "created_at")
    list_filter = ("status", "reason")
    search_fields = ("listing_title_snapshot",)
    readonly_fields = (
        "reporter",
        "listing",
        "message",
        "reason",
        "details",
        "listing_title_snapshot",
        "message_snapshot",
        "created_at",
        "resolved_at",
        "resolved_by",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_object(self, request, object_id, from_field=None):
        obj = super().get_object(request, object_id, from_field)
        if obj and self.has_view_or_change_permission(request, obj):
            ReportAccess.objects.create(report=obj, user=request.user)
        return obj

    def save_model(self, request, obj, form, change):
        previous = Report.objects.get(pk=obj.pk)
        if obj.status == Report.Status.PENDING:
            obj.resolved_by, obj.resolved_at = None, None
        elif previous.status != obj.status:
            obj.resolved_by, obj.resolved_at = request.user, timezone.now()
            notify(
                obj.reporter,
                "El equipo revisó tu denuncia en ResiVe",
                "/panel/notificaciones/",
            )
        super().save_model(request, obj, form, change)


@admin.register(ReportAccess)
class ReportAccessAdmin(admin.ModelAdmin):
    list_display = ("report", "user", "accessed_at")
    readonly_fields = ("report", "user", "accessed_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
