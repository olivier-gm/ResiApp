from uuid import UUID

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.core.security import rate_limit
from apps.inquiries.models import Message
from apps.inquiries.views import own_inquiries
from apps.listings.models import Listing

from .forms import ReportForm
from .models import Report


def report_target(user, listing_id, message_id):
    if bool(listing_id) == bool(message_id):
        raise Http404("Elige un único contenido para denunciar.")
    try:
        target_id = UUID(listing_id or message_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise Http404("Contenido no encontrado.") from exc
    if listing_id:
        listing = get_object_or_404(Listing.objects.select_related("owner"), pk=target_id)
        if not listing.is_public and listing.owner_id != user.pk:
            raise Http404("Contenido no encontrado.")
        return {"listing": listing, "message": None}, listing.title, ""
    message = get_object_or_404(
        Message.objects.select_related("inquiry__listing"),
        pk=target_id,
        inquiry__in=own_inquiries(user),
    )
    return (
        {"listing": None, "message": message},
        message.inquiry.listing.title,
        message.body,
    )


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def report(request):
    if not request.user.email_verified:
        raise PermissionDenied("Verifica tu correo antes de enviar una denuncia.")
    source = request.POST if request.method == "POST" else request.GET
    listing_id, message_id = source.get("listing", ""), source.get("message", "")
    target, title, snapshot = report_target(request.user, listing_id, message_id)
    form = ReportForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not rate_limit(request, "report", limit=10, seconds=3600):
            return HttpResponse("Has enviado muchas denuncias. Inténtalo más tarde.", status=429)
        with transaction.atomic():
            Report.objects.get_or_create(
                reporter=request.user,
                status=Report.Status.PENDING,
                **target,
                defaults={
                    **form.cleaned_data,
                    "listing_title_snapshot": title,
                    "message_snapshot": snapshot,
                },
            )
        messages.success(
            request,
            "Recibimos tu denuncia. El equipo revisará el contenido y los datos que compartiste.",
        )
        if target["message"]:
            return redirect(target["message"].inquiry)
        return redirect("listings:rentals")
    return render(
        request,
        "moderation/report.html",
        {
            "form": form,
            "target_title": title,
            "listing_id": listing_id,
            "message_id": message_id,
        },
    )
