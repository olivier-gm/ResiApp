import re
import uuid

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class UserManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, username):
        return self.get(email__iexact=username.strip())

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("El correo es obligatorio.")
        user = self.model(email=self.normalize_email(email).strip().lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("email_verified", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("El administrador necesita permisos de personal y superusuario.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField("Correo electrónico", unique=True)
    display_name = models.CharField("Nombre público", max_length=100)
    email_verified = models.BooleanField("Correo verificado", default=False)
    verification_nonce = models.UUIDField(default=uuid.uuid4, editable=False)
    phone = models.CharField("Teléfono privado", max_length=25, blank=True)
    advertiser_type = models.CharField(
        "Publico como",
        max_length=10,
        default="owner",
        choices=[("owner", "Propietario"), ("agent", "Asesor inmobiliario")],
    )
    whatsapp_enabled = models.BooleanField("Permitir contacto público por WhatsApp", default=False)
    email_notifications = models.BooleanField(
        "Recibir avisos de consultas y visitas por correo", default=True
    )
    deletion_requested_at = models.DateTimeField(null=True, blank=True, editable=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ("display_name",)
    objects = UserManager()

    class Meta:
        constraints = (models.UniqueConstraint(Lower("email"), name="user_email_case_unique"),)
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name or self.email

    def get_full_name(self):
        return self.display_name

    @property
    def whatsapp_url(self):
        if (
            self.whatsapp_enabled
            and self.is_active
            and self.email_verified
            and re.fullmatch(r"\+[1-9][0-9]{7,14}", self.phone)
        ):
            return f"https://wa.me/{self.phone[1:]}"
        return ""


class GoogleIdentity(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="google_identity"
    )
    subject = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
