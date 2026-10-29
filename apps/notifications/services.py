from urllib.parse import urlsplit

from django.conf import settings
from django.db import transaction

from .models import EmailDelivery, Notification


def queue_email(to, subject, body):
    return EmailDelivery.objects.create(to=to, subject=subject, body=body)


@transaction.atomic
def notify(user, title, url=""):
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or (url and not url.startswith("/")):
        raise ValueError("Las notificaciones deben apuntar a una ruta interna.")
    notification = Notification.objects.create(user=user, title=title, url=url)
    if user.email_verified and user.is_active and user.email_notifications:
        link = settings.PUBLIC_BASE_URL.rstrip("/") + url
        queue_email(user.email, title[:200], f"{title}\n\nConsulta tu cuenta en ResiVe:\n{link}")
    return notification
