from django.conf import settings
from django.core import signing
from django.urls import reverse

from apps.notifications.services import queue_email

VERIFY_SALT = "resive.email.verify"


def verification_token(user):
    return signing.dumps(
        {"user": user.pk, "email": user.email, "nonce": str(user.verification_nonce)}, salt=VERIFY_SALT
    )


def send_verification(user):
    url = settings.PUBLIC_BASE_URL.rstrip("/") + reverse("accounts:verify", args=[verification_token(user)])
    queue_email(
        user.email,
        "Verifica tu correo en ResiVe",
        f"Confirma tu correo para publicar y contactar:\n\n{url}\n\nEl enlace vence en 48 horas. Si no creaste esta cuenta, ignora este mensaje.",
    )
