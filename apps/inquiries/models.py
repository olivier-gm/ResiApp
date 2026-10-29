import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse


class Inquiry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey("listings.Listing", on_delete=models.PROTECT, related_name="inquiries")
    interested = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="inquiries"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["listing", "interested"], name="unique_listing_inquiry")
        ]

    def get_absolute_url(self):
        return reverse("inquiries:thread", args=[self.pk])

    def other_user(self, user):
        if user.pk == self.interested_id:
            return self.listing.owner
        if user.pk == self.listing.owner_id:
            return self.interested
        raise ValidationError("No perteneces a esta consulta.")

    def __str__(self):
        return f"Consulta de {self.interested}"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inquiry = models.ForeignKey(Inquiry, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inquiry_messages",
    )
    body = models.TextField(max_length=3000)
    client_token = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["inquiry", "sender", "client_token"],
                name="unique_message_retry",
            )
        ]


class VisitRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente de confirmación"
        ACCEPTED = "accepted", "Confirmada"
        REJECTED = "rejected", "Rechazada"
        CANCELLED = "cancelled", "Cancelada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inquiry = models.ForeignKey(Inquiry, on_delete=models.CASCADE, related_name="visits")
    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="visit_proposals",
    )
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class UserBlock(models.Model):
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocks_created",
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocks_received",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="unique_user_block"),
            models.CheckConstraint(condition=~models.Q(blocker=models.F("blocked")), name="no_self_block"),
        ]
