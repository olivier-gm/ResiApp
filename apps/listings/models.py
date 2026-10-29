import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Amenity(models.Model):
    name = models.CharField("nombre", max_length=80, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "servicio"

    def __str__(self):
        return self.name


class ListingQuerySet(models.QuerySet):
    def public(self):
        return self.filter(status="published", owner__is_active=True)

    def with_card_data(self):
        return self.select_related("owner", "locality__state", "zone").prefetch_related("images")


class Listing(models.Model):
    class Operation(models.TextChoices):
        RENT = "rent", "Alquiler"
        SALE = "sale", "Venta"

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        PENDING = "pending", "En revisión"
        PUBLISHED = "published", "Publicada"
        CHANGES = "changes", "Requiere cambios"
        PAUSED = "paused", "Pausada"
        CLOSED = "closed", "Cerrada"
        REMOVED = "removed", "Retirada por moderación"

    class PropertyType(models.TextChoices):
        APARTMENT = "apartment", "Apartamento"
        HOUSE = "house", "Casa"
        ANNEX = "annex", "Anexo"
        ROOM = "room", "Habitación"
        TOWNHOUSE = "townhouse", "Townhouse"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="listings")
    title = models.CharField("título", max_length=150)
    slug = models.SlugField(max_length=180, editable=False)
    description = models.TextField("descripción", blank=True, max_length=6000)
    operation = models.CharField("operación", max_length=4, choices=Operation, default=Operation.RENT)
    property_type = models.CharField(
        "tipo", max_length=12, choices=PropertyType, default=PropertyType.APARTMENT
    )
    status = models.CharField(max_length=10, choices=Status, default=Status.DRAFT, db_index=True)
    locality = models.ForeignKey(
        "locations.Locality",
        verbose_name="ciudad/localidad",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="listings",
    )
    zone = models.ForeignKey(
        "locations.Zone",
        verbose_name="zona/urbanización",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="listings",
    )
    exact_address = models.CharField("dirección exacta (privada)", max_length=300, blank=True)
    amount = models.DecimalField(
        "precio",
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(
        "moneda", max_length=3, choices=[("USD", "USD"), ("VES", "VES")], default="USD"
    )
    area = models.DecimalField(
        "superficie (m²)",
        max_digits=9,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    bedrooms = models.PositiveSmallIntegerField("dormitorios", default=1, validators=[MaxValueValidator(100)])
    bathrooms = models.PositiveSmallIntegerField("baños", default=1, validators=[MaxValueValidator(100)])
    parking = models.PositiveSmallIntegerField(
        "puestos de estacionamiento", default=0, validators=[MaxValueValidator(100)]
    )
    furnished = models.BooleanField("amueblado", null=True, blank=True)
    pets_allowed = models.BooleanField("acepta mascotas", null=True, blank=True)
    amenities = models.ManyToManyField(Amenity, verbose_name="servicios", blank=True)
    deposit = models.DecimalField(
        "depósito declarado",
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    advance = models.DecimalField(
        "anticipo declarado",
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    minimum_months = models.PositiveSmallIntegerField(
        "estancia mínima (meses)",
        null=True,
        blank=True,
        validators=[MaxValueValidator(120)],
    )
    available_from = models.DateField("disponible desde", null=True, blank=True)
    included_expenses = models.CharField("servicios y gastos incluidos", max_length=500, blank=True)
    additional_costs = models.CharField("gastos adicionales", max_length=500, blank=True)
    house_rules = models.CharField("reglas de convivencia", max_length=1000, blank=True)
    negotiable = models.BooleanField("precio negociable", default=False)
    documentation = models.CharField("situación documental declarada", max_length=500, blank=True)
    moderation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = ListingQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "id"]
        permissions = [("moderate_listing", "Puede revisar y retirar anuncios")]
        indexes = [
            models.Index(fields=["status", "operation", "-created_at"]),
            models.Index(fields=["currency", "amount"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__isnull=True) | models.Q(amount__gt=0),
                name="listing_positive_amount",
            )
        ]
        verbose_name = "publicación"

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.zone_id and self.zone.locality_id != self.locality_id:
            raise ValidationError({"zone": "La zona no pertenece a la ciudad elegida."})

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title)[:180] or "inmueble"
        super().save(*args, **kwargs)

    @property
    def is_public(self):
        return self.status == self.Status.PUBLISHED and self.owner.is_active

    @property
    def cover(self):
        return next(iter(self.images.all()), None)

    def get_absolute_url(self):
        return reverse("listings:detail", kwargs={"pk": self.pk, "slug": self.slug})


class ListingImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="images")
    object_key = models.CharField(max_length=400)
    thumbnail_key = models.CharField(max_length=400)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    position = models.PositiveIntegerField(default=0)
    alt = models.CharField("descripción de la foto", max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "created_at", "id"]

    @property
    def url(self):
        return reverse("listings:image", kwargs={"pk": self.pk, "variant": "full"})

    @property
    def thumbnail_url(self):
        return reverse("listings:image", kwargs={"pk": self.pk, "variant": "thumb"})


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "listing"], name="favorite_unique")]


class ListingTransition(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.PROTECT, related_name="transitions")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    previous_status = models.CharField(max_length=10)
    new_status = models.CharField(max_length=10)
    reason = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
