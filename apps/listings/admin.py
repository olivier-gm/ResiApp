from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.core.exceptions import PermissionDenied, ValidationError
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from .models import Amenity, Listing, ListingImage, ListingTransition
from .services import transition_listing


class ModerationReasonForm(forms.Form):
    reason = forms.CharField(
        label="Motivo que verá el anunciante",
        min_length=10,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 5, "cols": 70}),
        help_text="Explica qué debe corregir o por qué se retira la publicación.",
    )


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "operation", "status", "locality", "updated_at"]
    list_filter = ["status", "operation", "currency"]
    search_fields = ["title", "owner__email"]
    actions = ["approve", "request_changes", "withdraw"]
    readonly_fields = [field.name for field in Listing._meta.fields] + ["amenities", "photos"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Fotografías")
    def photos(self, obj):
        return (
            format_html_join(
                " ",
                '<a href="{}" target="_blank" rel="noopener"><img src="{}" alt="{}" width="160" loading="lazy"></a>',
                (
                    (
                        reverse("listings:image", args=[photo.pk, "full"]),
                        reverse("listings:image", args=[photo.pk, "thumb"]),
                        photo.alt or "Fotografía del inmueble",
                    )
                    for photo in obj.images.all()
                ),
            )
            or "Sin fotografías"
        )

    def _transition(self, request, queryset, target, reason):
        if not request.user.has_perm("listings.moderate_listing"):
            raise PermissionDenied
        count = 0
        for listing in queryset:
            try:
                transition_listing(listing, request.user, target, reason)
            except (ValidationError, PermissionDenied) as exc:
                self.message_user(request, f"{listing}: {exc}", messages.ERROR)
            else:
                count += 1
                self.log_change(request, listing, f"Moderación: {target}. {reason}")
        if count:
            self.message_user(request, f"Se actualizaron {count} publicaciones.", messages.SUCCESS)

    def _reason_action(self, request, queryset, action, target, title):
        if not self.has_moderate_permission(request):
            raise PermissionDenied
        form = ModerationReasonForm(request.POST if request.POST.get("apply") else None)
        if request.POST.get("apply") and form.is_valid():
            self._transition(request, queryset, target, form.cleaned_data["reason"])
            return None
        request.current_app = self.admin_site.name
        return TemplateResponse(
            request,
            "admin/listings/moderate.html",
            {
                **self.admin_site.each_context(request),
                "title": title,
                "opts": self.model._meta,
                "form": form,
                "queryset": queryset,
                "action": action,
                "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            },
        )

    @admin.action(description="Aprobar publicaciones pendientes", permissions=["moderate"])
    def approve(self, request, queryset):
        self._transition(request, queryset, "published", "")

    @admin.action(description="Solicitar correcciones de información", permissions=["moderate"])
    def request_changes(self, request, queryset):
        return self._reason_action(
            request,
            queryset,
            "request_changes",
            "changes",
            "Solicitar correcciones",
        )

    @admin.action(
        description="Retirar publicaciones indicando el motivo",
        permissions=["moderate"],
    )
    def withdraw(self, request, queryset):
        return self._reason_action(
            request,
            queryset,
            "withdraw",
            "removed",
            "Retirar publicaciones",
        )

    def has_moderate_permission(self, request):
        return request.user.has_perm("listings.moderate_listing")


@admin.register(ListingTransition)
class ListingTransitionAdmin(admin.ModelAdmin):
    list_display = ["listing", "actor", "previous_status", "new_status", "created_at"]
    readonly_fields = [field.name for field in ListingTransition._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ListingImage)
class ListingImageAdmin(admin.ModelAdmin):
    list_display = ["listing", "position", "width", "height"]
    readonly_fields = ["preview"] + [field.name for field in ListingImage._meta.fields]

    @admin.display(description="Vista previa autorizada")
    def preview(self, obj):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener"><img src="{}" alt="{}" width="320" loading="lazy"><br>Ver fotografía completa</a>',
            reverse("listings:image", args=[obj.pk, "full"]),
            reverse("listings:image", args=[obj.pk, "thumb"]),
            obj.alt or "Fotografía del inmueble",
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(Amenity)
