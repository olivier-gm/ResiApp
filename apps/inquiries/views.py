from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.core.security import rate_limit
from apps.listings.models import Listing

from .forms import MessageForm, VisitForm, VisitResponseForm
from .models import Inquiry, UserBlock, VisitRequest
from .services import (
    create_inquiry,
    is_blocked,
    propose_visit,
    respond_visit,
    send_message,
)


def own_inquiries(user):
    return Inquiry.objects.filter(Q(interested=user) | Q(listing__owner=user)).select_related(
        "listing__owner", "interested"
    )


def thread_context(inquiry, user, **extra):
    other = inquiry.other_user(user)
    return {
        "inquiry": inquiry,
        "other": other,
        "thread_messages": inquiry.messages.select_related("sender"),
        "visits": inquiry.visits.select_related("proposed_by"),
        "message_form": MessageForm(),
        "visit_form": VisitForm(),
        "blocked": is_blocked(user, other),
        "blocked_by_me": UserBlock.objects.filter(blocker=user, blocked=other).exists(),
        **extra,
    }


@login_required
@never_cache
def inbox(request):
    return render(request, "inquiries/inbox.html", {"inquiries": own_inquiries(request.user)})


@login_required
@never_cache
def create(request, listing_id):
    listing = get_object_or_404(Listing.objects.select_related("owner"), pk=listing_id)
    form = MessageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not rate_limit(request, "inquiry_create", limit=15, seconds=3600):
            return HttpResponse("Has enviado muchas consultas. Inténtalo más tarde.", status=429)
        inquiry = create_inquiry(listing, request.user, **form.cleaned_data)
        return redirect(inquiry)
    if request.method not in ["GET", "POST"]:
        return HttpResponse(status=405)
    if not listing.is_public or listing.owner_id == request.user.pk:
        return HttpResponse("Este inmueble no admite una nueva consulta.", status=403)
    return render(request, "inquiries/create.html", {"listing": listing, "form": form})


@login_required
@never_cache
def thread(request, pk):
    inquiry = get_object_or_404(own_inquiries(request.user), pk=pk)
    form = MessageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not rate_limit(request, "inquiry_message", limit=60, seconds=3600):
            return HttpResponse("Has enviado muchos mensajes. Inténtalo más tarde.", status=429)
        send_message(inquiry, request.user, **form.cleaned_data)
        return redirect(inquiry)
    if request.method not in ["GET", "POST"]:
        return HttpResponse(status=405)
    return render(
        request,
        "inquiries/thread.html",
        thread_context(inquiry, request.user, message_form=form),
    )


@login_required
@require_POST
@never_cache
def visit_create(request, pk):
    inquiry = get_object_or_404(own_inquiries(request.user), pk=pk)
    form = VisitForm(request.POST)
    if form.is_valid():
        if not rate_limit(request, "visit_create", limit=20, seconds=3600):
            return HttpResponse("Has enviado muchas propuestas. Inténtalo más tarde.", status=429)
        try:
            propose_visit(inquiry, request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Propuesta enviada. La otra persona debe confirmarla.")
            return redirect(inquiry)
    return render(
        request,
        "inquiries/thread.html",
        thread_context(inquiry, request.user, visit_form=form),
    )


@login_required
@require_POST
@never_cache
def visit_respond(request, pk):
    visit = get_object_or_404(
        VisitRequest.objects.filter(inquiry__in=own_inquiries(request.user)).select_related(
            "inquiry__listing__owner", "inquiry__interested"
        ),
        pk=pk,
    )
    form = VisitResponseForm(request.POST)
    if form.is_valid():
        try:
            respond_visit(visit.pk, request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Solicitud de visita actualizada.")
            return redirect(visit.inquiry)
    return render(
        request,
        "inquiries/thread.html",
        thread_context(visit.inquiry, request.user, response_form=form, response_visit=visit),
    )


@login_required
@require_POST
@never_cache
def block(request, pk):
    inquiry = get_object_or_404(own_inquiries(request.user), pk=pk)
    UserBlock.objects.get_or_create(blocker=request.user, blocked=inquiry.other_user(request.user))
    messages.success(request, "Contacto bloqueado. Puedes seguir leyendo el historial.")
    return redirect(inquiry)


@login_required
@require_POST
@never_cache
def unblock(request, pk):
    inquiry = get_object_or_404(own_inquiries(request.user), pk=pk)
    UserBlock.objects.filter(blocker=request.user, blocked=inquiry.other_user(request.user)).delete()
    messages.success(request, "Has retirado tu bloqueo.")
    return redirect(inquiry)


@login_required
@require_POST
@never_cache
def mark_read(request, pk):
    inquiry = get_object_or_404(own_inquiries(request.user), pk=pk)
    inquiry.messages.exclude(sender=request.user).filter(read_at__isnull=True).update(read_at=timezone.now())
    return redirect(inquiry)
