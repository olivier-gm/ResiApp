from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.notifications.services import notify

from .models import Inquiry, Message, UserBlock, VisitRequest


def is_blocked(first, second):
    return UserBlock.objects.filter(
        Q(blocker=first, blocked=second) | Q(blocker=second, blocked=first)
    ).exists()


def can_write(inquiry, user):
    if user.pk not in (inquiry.interested_id, inquiry.listing.owner_id):
        raise PermissionDenied("No perteneces a esta consulta.")
    other = inquiry.other_user(user)
    if not user.is_active or not user.email_verified or not other.is_active:
        raise PermissionDenied("Verifica tu correo y comprueba que ambas cuentas estén activas.")
    if is_blocked(user, other):
        raise PermissionDenied("El contacto entre estas cuentas está bloqueado.")
    return other


@transaction.atomic
def create_inquiry(listing, user, body, client_token):
    if not user.is_active or not user.email_verified:
        raise PermissionDenied("Verifica tu correo antes de consultar.")
    if listing.owner_id == user.pk or not listing.is_public:
        raise PermissionDenied("Este inmueble no admite una nueva consulta.")
    if is_blocked(user, listing.owner):
        raise PermissionDenied("El contacto entre estas cuentas está bloqueado.")
    inquiry, _ = Inquiry.objects.get_or_create(listing=listing, interested=user)
    send_message(inquiry, user, body, client_token)
    return inquiry


@transaction.atomic
def send_message(inquiry, user, body, client_token):
    other = can_write(inquiry, user)
    body = body.strip()
    if not 5 <= len(body) <= 3000:
        raise ValidationError("El mensaje debe tener entre 5 y 3000 caracteres.")
    message, created = Message.objects.get_or_create(
        inquiry=inquiry,
        sender=user,
        client_token=client_token,
        defaults={"body": body},
    )
    if created:
        Inquiry.objects.filter(pk=inquiry.pk).update(updated_at=timezone.now())
        notify(other, "Tienes un nuevo mensaje en ResiVe", inquiry.get_absolute_url())
    return message


@transaction.atomic
def propose_visit(inquiry, user, scheduled_at):
    other = can_write(inquiry, user)
    if not inquiry.listing.is_public:
        raise ValidationError("El inmueble ya no está disponible para nuevas visitas.")
    if scheduled_at <= timezone.now():
        raise ValidationError("Elige una fecha futura.")
    visit = VisitRequest.objects.create(inquiry=inquiry, proposed_by=user, scheduled_at=scheduled_at)
    notify(other, "Tienes una propuesta de visita", inquiry.get_absolute_url())
    return visit


@transaction.atomic
def respond_visit(visit_id, user, version, action, scheduled_at=None):
    visit = (
        VisitRequest.objects.select_for_update()
        .select_related("inquiry__listing__owner", "inquiry__interested")
        .get(pk=visit_id)
    )
    other = can_write(visit.inquiry, user)
    if visit.version != version:
        raise ValidationError("Esta visita cambió. Actualiza la consulta antes de responder.")
    if visit.status in [VisitRequest.Status.CANCELLED, VisitRequest.Status.REJECTED]:
        raise ValidationError("Esta solicitud ya está cerrada. Propón una nueva visita.")
    updates = {"version": version + 1, "updated_at": timezone.now()}
    if action == "cancel":
        updates["status"] = VisitRequest.Status.CANCELLED
    elif action in ["accept", "reject"]:
        if visit.proposed_by_id == user.pk:
            raise PermissionDenied("La otra persona debe responder a tu propuesta.")
        if visit.status != VisitRequest.Status.PENDING or visit.scheduled_at <= timezone.now():
            raise ValidationError("Solo se puede responder a una propuesta pendiente y futura.")
        if action == "accept" and not visit.inquiry.listing.is_public:
            raise ValidationError("El inmueble ya no está disponible para confirmar visitas.")
        updates["status"] = (
            VisitRequest.Status.ACCEPTED if action == "accept" else VisitRequest.Status.REJECTED
        )
    elif action == "reschedule":
        if not scheduled_at or scheduled_at <= timezone.now():
            raise ValidationError("Elige una fecha futura.")
        if not visit.inquiry.listing.is_public:
            raise ValidationError("El inmueble ya no está disponible para reprogramar visitas.")
        updates.update(
            status=VisitRequest.Status.PENDING,
            scheduled_at=scheduled_at,
            proposed_by=user,
        )
    else:
        raise ValidationError("Respuesta desconocida.")
    if not VisitRequest.objects.filter(pk=visit.pk, version=version).update(**updates):
        raise ValidationError("Otra persona acaba de responder. Actualiza la consulta.")
    notify(other, "Se actualizó una solicitud de visita", visit.inquiry.get_absolute_url())
    return visit
