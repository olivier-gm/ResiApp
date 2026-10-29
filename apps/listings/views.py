import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from storages.backends.s3 import S3Storage

from apps.core.security import rate_limit

from .forms import ImageUploadForm, ListingForm, SearchForm
from .models import Favorite, Listing, ListingImage
from .services import (
    add_photo,
    mark_edited,
    move_photo,
    remove_photo,
    transition_listing,
)

logger = logging.getLogger(__name__)


def search(request, operation="rent"):
    form = SearchForm(request.GET)
    listings = Listing.objects.public().with_card_data().filter(operation=operation)
    if form.is_valid():
        data = form.cleaned_data
        if data.get("q"):
            listings = listings.filter(
                Q(title__icontains=data["q"])
                | Q(description__icontains=data["q"])
                | Q(locality__name__icontains=data["q"])
                | Q(zone__name__icontains=data["q"])
            )
        for field in ("property_type", "currency", "locality", "zone"):
            if data.get(field):
                listings = listings.filter(**{field: data[field]})
        if data.get("state"):
            listings = listings.filter(locality__state=data["state"])
        for field, lookup in (
            ("minimum", "amount__gte"),
            ("maximum", "amount__lte"),
            ("bedrooms", "bedrooms__gte"),
            ("bathrooms", "bathrooms__gte"),
            ("parking", "parking__gte"),
        ):
            if data.get(field) is not None:
                listings = listings.filter(**{lookup: data[field]})
        for field in ("furnished", "pets_allowed"):
            if data.get(field):
                listings = listings.filter(**{field: data[field] == "yes"})
        for amenity in data.get("amenities", []):
            listings = listings.filter(amenities=amenity)
        ordering = {"price_up": ["amount", "id"], "price_down": ["-amount", "id"]}.get(
            data.get("order"), ["-created_at", "id"]
        )
        listings = listings.order_by(*ordering)
    else:
        listings = listings.none()
    page = Paginator(listings, 12).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(
        request,
        "listings/search.html",
        {
            "form": form,
            "page_obj": page,
            "operation": operation,
            "querystring": params.urlencode(),
        },
    )


def detail(request, pk, slug):
    listing = get_object_or_404(Listing.objects.with_card_data().prefetch_related("amenities"), pk=pk)
    can_manage = request.user.is_authenticated and (
        request.user.pk == listing.owner_id or request.user.has_perm("listings.moderate_listing")
    )
    if not listing.is_public and not can_manage:
        raise Http404
    if slug != listing.slug:
        return redirect(listing.get_absolute_url(), permanent=True)
    is_favorite = (
        request.user.is_authenticated and Favorite.objects.filter(user=request.user, listing=listing).exists()
    )
    return render(
        request,
        "listings/detail.html",
        {"listing": listing, "can_manage": can_manage, "is_favorite": is_favorite},
    )


@login_required
@never_cache
def dashboard(request):
    listings = Listing.objects.filter(owner=request.user).with_card_data()
    status = request.GET.get("status")
    if status in Listing.Status.values:
        listings = listings.filter(status=status)
    return render(
        request,
        "listings/dashboard.html",
        {
            "listings": listings,
            "statuses": Listing.Status.choices,
            "selected_status": status,
        },
    )


@login_required
@never_cache
def edit(request, pk=None):
    listing = get_object_or_404(Listing, pk=pk, owner=request.user) if pk else Listing(owner=request.user)
    if listing.status == Listing.Status.REMOVED:
        return HttpResponse("Esta publicación fue retirada. Contacta a soporte.", status=403)
    form = ListingForm(request.POST or None, instance=listing)
    if request.method == "POST" and form.is_valid():
        if not rate_limit(request, "listing-edit", limit=60, seconds=3600):
            return HttpResponse("Demasiados cambios. Inténtalo más tarde.", status=429)
        with transaction.atomic():
            if pk:
                locked = Listing.objects.select_for_update().get(pk=pk, owner=request.user)
                if locked.status == Listing.Status.REMOVED:
                    raise PermissionDenied
                form.instance.status = locked.status
            saved = form.save()
            mark_edited(saved, request.user)
        messages.success(
            request,
            "Borrador guardado. Añade fotos y envía a revisión cuando esté listo.",
        )
        return redirect("listings:edit", pk=saved.pk)
    return render(
        request,
        "listings/edit.html",
        {
            "form": form,
            "listing": listing,
            "upload_form": ImageUploadForm(),
            "listing_saved": pk is not None,
        },
    )


@login_required
@require_POST
def change_state(request, pk):
    listing = get_object_or_404(Listing, pk=pk, owner=request.user)
    try:
        transition_listing(listing, request.user, request.POST.get("target"))
        messages.success(request, "Estado de la publicación actualizado.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("listings:edit", pk=listing.pk)


@login_required
@require_POST
def upload(request, pk):
    listing = get_object_or_404(Listing, pk=pk, owner=request.user)
    form = ImageUploadForm(request.POST, request.FILES)
    if not rate_limit(request, "photo-upload", limit=60, seconds=3600):
        return HttpResponse("Demasiadas cargas. Inténtalo más tarde.", status=429)
    if form.is_valid():
        try:
            add_photo(
                listing,
                request.user,
                form.cleaned_data["image"],
                form.cleaned_data["alt"],
            )
            messages.success(request, "Foto añadida.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        except Exception:
            logger.exception("Fallo al almacenar una foto.")
            messages.error(request, "No se pudo guardar la foto. Puedes reintentar.")
    else:
        messages.error(
            request,
            " ".join(error for errors in form.errors.values() for error in errors),
        )
    return redirect("listings:edit", pk=listing.pk)


@login_required
@require_POST
def delete_image(request, pk):
    photo = get_object_or_404(
        ListingImage.objects.select_related("listing"),
        pk=pk,
        listing__owner=request.user,
    )
    listing_id = photo.listing_id
    remove_photo(photo, request.user)
    messages.success(request, "Foto eliminada.")
    return redirect("listings:edit", pk=listing_id)


@login_required
@require_POST
def reorder_image(request, pk):
    photo = get_object_or_404(ListingImage, pk=pk, listing__owner=request.user)
    if request.POST.get("direction") not in ("up", "down"):
        return HttpResponse("Dirección inválida.", status=400)
    move_photo(photo, request.user, request.POST["direction"])
    return redirect("listings:edit", pk=photo.listing_id)


@never_cache
def image(request, pk, variant):
    photo = get_object_or_404(ListingImage.objects.select_related("listing__owner"), pk=pk)
    listing = photo.listing
    allowed = listing.is_public or (
        request.user.is_authenticated
        and (request.user.pk == listing.owner_id or request.user.has_perm("listings.moderate_listing"))
    )
    if not allowed or variant not in ("full", "thumb"):
        raise Http404
    key = photo.object_key if variant == "full" else photo.thumbnail_key
    if isinstance(default_storage, S3Storage):
        response = HttpResponseRedirect(default_storage.url(key, expire=300))
    else:
        try:
            response = FileResponse(default_storage.open(key, "rb"), content_type="image/webp")
        except FileNotFoundError as exc:
            raise Http404 from exc
    response["Cache-Control"] = "private, no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response


@login_required
@require_POST
def favorite(request, pk):
    desired = request.POST.get("saved")
    if desired not in ("yes", "no"):
        return HttpResponse("Indica si deseas guardar la publicación.", status=400)
    listing = get_object_or_404(
        Listing.objects.public() if desired == "yes" else Listing.objects.all(), pk=pk
    )
    if desired == "yes":
        Favorite.objects.get_or_create(user=request.user, listing=listing)
    else:
        Favorite.objects.filter(user=request.user, listing=listing).delete()
    if request.headers.get("HX-Request"):
        return render(
            request,
            "listings/favorite_button.html",
            {"listing": listing, "is_favorite": desired == "yes"},
        )
    return redirect(listing.get_absolute_url() if listing.is_public else "listings:favorites")


@login_required
@never_cache
def favorites(request):
    items = (
        Favorite.objects.filter(user=request.user)
        .select_related("listing__owner", "listing__locality__state", "listing__zone")
        .prefetch_related("listing__images")
        .order_by("-created_at")
    )
    return render(request, "listings/favorites.html", {"items": items})
