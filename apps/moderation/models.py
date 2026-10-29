import uuid

from django.conf import settings
from django.db import models


class Report(models.Model):
    class Reason(models.TextChoices):
        FRAUD = "fraud", "Posible fraude"
        FALSE_INFO = "false_info", "Información incorrecta"
        INAPPROPRIATE = "inappropriate", "Contenido o trato inapropiado"
        UNAVAILABLE = "unavailable", "Inmueble no disponible"
        OTHER = "other", "Otro motivo"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        RESOLVED = "resolved", "Resuelta"
        DISMISSED = "dismissed", "Desestimada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reports")
    listing = models.ForeignKey(
        "listings.Listing",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reports",
    )
    message = models.ForeignKey(
        "inquiries.Message",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reports",
    )
    reason = models.CharField("motivo", max_length=20, choices=Reason.choices)
    details = models.TextField("explica lo ocurrido", max_length=2000)
    listing_title_snapshot = models.CharField(
        "título del anuncio al denunciar", max_length=150, editable=False
    )
    message_snapshot = models.TextField("mensaje denunciado", blank=True, editable=False)
    status = models.CharField("estado", max_length=12, choices=Status.choices, default=Status.PENDING)
    resolution = models.TextField("motivo de la resolución", blank=True, max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="report_resolutions",
        editable=False,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "denuncia"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(listing__isnull=False, message__isnull=True)
                    | models.Q(listing__isnull=True, message__isnull=False)
                ),
                name="report_exactly_one_target",
            ),
            models.UniqueConstraint(
                fields=["reporter", "listing"],
                condition=models.Q(status="pending"),
                name="unique_pending_listing_report",
            ),
            models.UniqueConstraint(
                fields=["reporter", "message"],
                condition=models.Q(status="pending"),
                name="unique_pending_message_report",
            ),
        ]

    def __str__(self):
        return f"{self.get_reason_display()} · {self.listing_title_snapshot}"


class ReportAccess(models.Model):
    report = models.ForeignKey(Report, on_delete=models.PROTECT, related_name="accesses")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="report_accesses",
    )
    accessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-accessed_at"]
        verbose_name = "acceso a denuncia"
