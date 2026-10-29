from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import AdminUserChangeForm, AdminUserCreationForm
from .models import User


@admin.register(User)
class AccountAdmin(UserAdmin):
    form = AdminUserChangeForm
    add_form = AdminUserCreationForm
    list_display = ("email", "display_name", "email_verified", "is_active", "deletion_requested_at")
    list_filter = ("email_verified", "is_active", "is_staff")
    search_fields = ("email", "display_name")
    ordering = ("email",)
    actions = ("suspend_accounts",)
    readonly_fields = ("last_login", "date_joined", "deletion_requested_at", "verification_nonce")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Perfil",
            {
                "fields": (
                    "display_name",
                    "phone",
                    "advertiser_type",
                    "whatsapp_enabled",
                    "email_notifications",
                    "email_verified",
                )
            },
        ),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (
            "Registro",
            {"fields": ("last_login", "date_joined", "deletion_requested_at", "verification_nonce")},
        ),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "display_name", "password1", "password2")}),
    )

    @admin.action(description="Suspender cuentas seleccionadas", permissions=["change"])
    def suspend_accounts(self, request, queryset):
        allowed = queryset.exclude(pk=request.user.pk)
        if not request.user.is_superuser:
            allowed = allowed.filter(is_staff=False, is_superuser=False)
        count = allowed.update(is_active=False)
        self.message_user(
            request, f"Cuentas suspendidas: {count}. Sus anuncios dejan de estar disponibles públicamente."
        )
