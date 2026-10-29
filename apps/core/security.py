import hashlib
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import RateWindow


def rate_limit(request, scope, limit=20, seconds=60):
    remote = request.META.get("REMOTE_ADDR", "")
    if getattr(settings, "TRUST_PROXY_SSL", False):
        remote = request.META.get("HTTP_X_REAL_IP", remote)
    identity = str(request.user.pk) if request.user.is_authenticated else remote
    key = hashlib.sha256(f"{scope}:{identity}".encode()).hexdigest()
    now = timezone.now()
    with transaction.atomic():
        window, _ = RateWindow.objects.get_or_create(
            key=key, defaults={"expires_at": now + timedelta(seconds=seconds)}
        )
        window = RateWindow.objects.select_for_update().get(pk=window.pk)
        if window.expires_at <= now:
            window.count, window.expires_at = 0, now + timedelta(seconds=seconds)
        window.count += 1
        window.save(update_fields=["count", "expires_at"])
        return window.count <= limit
