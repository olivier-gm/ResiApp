import logging
import uuid
import warnings
from io import BytesIO

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Max
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Listing, ListingImage, ListingTransition

logger = logging.getLogger(__name__)


def validate_for_review(listing):
    listing.full_clean()
    if not listing.owner.email_verified:
        raise ValidationError("Verifica tu correo antes de enviar una publicación.")
    if not listing.locality_id or not listing.amount or not listing.description.strip() or not listing.area:
        raise ValidationError("Completa ciudad, precio, superficie y descripción antes de enviar.")
    if not listing.images.exists():
        raise ValidationError("Añade al menos una foto antes de enviar a revisión.")


@transaction.atomic
def transition_listing(listing, actor, target, reason=""):
    locked = Listing.objects.select_for_update().get(pk=listing.pk)
    previous = locked.status
    is_moderator = actor.has_perm("listings.moderate_listing")
    owner_allowed = {
        "draft": {"pending"},
        "changes": {"pending"},
        "paused": {"pending", "closed"},
        "published": {"paused", "closed"},
        "closed": {"draft"},
        "pending": {"draft"},
    }
    moderator_allowed = (target in ("published", "changes") and previous == "pending") or (
        target == "removed" and previous != "removed"
    )
    owner_transition = actor.pk == locked.owner_id and target in owner_allowed.get(previous, set())
    if not actor.is_active or not ((is_moderator and moderator_allowed) or owner_transition):
        raise PermissionDenied("No puedes realizar este cambio de estado.")
    if target in ("published", "pending"):
        validate_for_review(locked)
    if target in ("changes", "removed") and not reason.strip():
        raise ValidationError("Indica el motivo de la decisión.")
    locked.status = target
    locked.moderation_reason = reason[:1000] if target in ("changes", "removed") else ""
    locked.save(update_fields=["status", "moderation_reason", "updated_at", "slug"])
    ListingTransition.objects.create(
        listing=locked,
        actor=actor,
        previous_status=previous,
        new_status=target,
        reason=reason[:1000],
    )
    if is_moderator and actor.pk != locked.owner_id:
        from apps.notifications.services import notify

        notify(
            locked.owner,
            f"Tu publicación: {locked.get_status_display()}",
            locked.get_absolute_url(),
        )
    listing.status = locked.status
    return locked


def mark_edited(listing, actor):
    if listing.status == Listing.Status.PUBLISHED:
        ListingTransition.objects.create(
            listing=listing,
            actor=actor,
            previous_status="published",
            new_status="pending",
            reason="Edición del anunciante; requiere nueva revisión.",
        )
        listing.status = Listing.Status.PENDING
        listing.save(update_fields=["status", "updated_at", "slug"])


def delete_objects(keys):
    for key in keys:
        try:
            default_storage.delete(key)
        except Exception:
            logger.exception("No se pudo limpiar una foto de publicación; ejecutar reconciliación.")


def process_photo(upload):
    if upload.size > 8 * 1024 * 1024:
        raise ValidationError("La foto no puede superar 8 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(upload) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValidationError("Usa una foto JPEG, PNG o WebP.")
                if source.width * source.height > 25_000_000:
                    raise ValidationError("La foto no puede superar 25 megapíxeles.")
                source.load()
                oriented = ImageOps.exif_transpose(source)
                image = oriented.convert("RGB")
                image.thumbnail((1800, 1800))
                full = BytesIO()
                image.save(full, "WEBP", quality=85, exif=b"")
                width, height = image.size
                image.thumbnail((640, 640))
                thumb = BytesIO()
                image.save(thumb, "WEBP", quality=78, exif=b"")
                return full.getvalue(), thumb.getvalue(), width, height
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValidationError("No se pudo leer la foto. Usa una imagen válida y más pequeña.") from exc


def add_photo(listing, actor, upload, alt=""):
    full, thumb, width, height = process_photo(upload)
    saved_keys = []
    try:
        with transaction.atomic():
            locked = Listing.objects.select_for_update().get(pk=listing.pk)
            if locked.owner_id != actor.pk or locked.status == Listing.Status.REMOVED:
                raise PermissionDenied
            if locked.images.count() >= 15:
                raise ValidationError("Puedes añadir hasta 15 fotos por publicación.")
            prefix = f"listings/{locked.pk}/{uuid.uuid4().hex}"
            full_key = default_storage.save(f"{prefix}/full.webp", ContentFile(full))
            saved_keys.append(full_key)
            thumb_key = default_storage.save(f"{prefix}/thumb.webp", ContentFile(thumb))
            saved_keys.append(thumb_key)
            position = (locked.images.aggregate(value=Max("position"))["value"] or 0) + 1
            photo = ListingImage.objects.create(
                listing=locked,
                object_key=full_key,
                thumbnail_key=thumb_key,
                width=width,
                height=height,
                position=position,
                alt=alt,
            )
            mark_edited(locked, actor)
            return photo
    except Exception:
        delete_objects(saved_keys)
        raise


@transaction.atomic
def remove_photo(photo, actor):
    listing = Listing.objects.select_for_update().get(pk=photo.listing_id)
    if listing.owner_id != actor.pk or listing.status == Listing.Status.REMOVED:
        raise PermissionDenied
    keys = [photo.object_key, photo.thumbnail_key]
    photo.delete()
    mark_edited(listing, actor)
    transaction.on_commit(lambda: delete_objects(keys))


@transaction.atomic
def move_photo(photo, actor, direction):
    listing = Listing.objects.select_for_update().get(pk=photo.listing_id)
    if listing.owner_id != actor.pk or listing.status == Listing.Status.REMOVED:
        raise PermissionDenied
    images = list(listing.images.all())
    index = next(i for i, item in enumerate(images) if item.pk == photo.pk)
    other = index - 1 if direction == "up" else index + 1
    if 0 <= other < len(images):
        images[index], images[other] = images[other], images[index]
        for position, item in enumerate(images):
            item.position = position
        ListingImage.objects.bulk_update(images, ["position"])
        mark_edited(listing, actor)
