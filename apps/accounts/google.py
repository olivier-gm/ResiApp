import secrets
from urllib.parse import parse_qs, urlsplit

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.django_client import OAuth
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from joserfc.errors import JoseError
from requests.exceptions import RequestException

from apps.core.security import rate_limit

from .models import GoogleIdentity, User


def google_client():
    oauth = OAuth()
    return oauth.register(
        "google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid email profile",
            "code_challenge_method": "S256",
            "default_timeout": 15,
        },
    )


def failure(request, text, status=400):
    return render(request, "accounts/google_error.html", {"error": text}, status=status)


@require_POST
@never_cache
def start(request):
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return failure(request, "El acceso con Google todavía no está configurado.", 503)
    if not rate_limit(request, "google-login", limit=10, seconds=900):
        return failure(request, "Demasiados intentos. Intenta de nuevo más tarde.", 429)
    connect = request.POST.get("process") == "connect"
    if connect and not request.user.is_authenticated:
        return redirect("accounts:login")
    if request.user.is_authenticated and not connect:
        return redirect("accounts:profile")
    destination = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        destination, {request.get_host()}, require_https=request.is_secure()
    ):
        destination = reverse("listings:dashboard")
    try:
        response = google_client().authorize_redirect(
            request,
            settings.PUBLIC_BASE_URL + reverse("accounts:google_callback"),
            nonce=secrets.token_urlsafe(32),
            prompt="select_account",
        )
    except OAuthError, RequestException, ValueError:
        return failure(request, "No pudimos conectar con Google. Inténtalo de nuevo.", 502)
    state = parse_qs(urlsplit(response.url).query)["state"][0]
    request.session["google_flow"] = {
        "state": state,
        "user": request.user.pk if connect else None,
        "next": destination,
    }
    return response


@require_GET
@never_cache
def callback(request):
    flow = request.session.pop("google_flow", None)
    if not flow or not secrets.compare_digest(str(flow["state"]), request.GET.get("state", "")):
        return failure(request, "La solicitud venció o no coincide. Vuelve a iniciar el acceso con Google.")
    try:
        # Authlib validates state, signature, issuer, audience, expiry and the stored nonce.
        token = google_client().authorize_access_token(request)
        claims = token["userinfo"]
        email_claim = claims.get("email")
        if not isinstance(email_claim, str):
            raise ValueError("Invalid email claim")
        email = email_claim.strip().lower()
        subject = claims.get("sub")
        validate_email(email)
        if (
            claims.get("email_verified") is not True
            or not isinstance(subject, str)
            or not 1 <= len(subject) <= 255
        ):
            raise ValueError("Invalid verified identity")
    except OAuthError, JoseError, RequestException, KeyError, ValueError, ValidationError:
        return failure(request, "Google no confirmó una identidad válida. Vuelve a intentarlo.")
    try:
        with transaction.atomic():
            identity = GoogleIdentity.objects.select_related("user").filter(subject=subject).first()
            if flow["user"] is not None:
                if (
                    not request.user.is_authenticated
                    or request.user.pk != flow["user"]
                    or not request.user.is_active
                ):
                    return failure(request, "Tu sesión cambió. Entra de nuevo antes de vincular Google.")
                if identity and identity.user_id != request.user.pk:
                    return failure(request, "Esta cuenta de Google ya está vinculada a otra cuenta.")
                current = GoogleIdentity.objects.filter(user=request.user).first()
                if current and current.subject != subject:
                    return failure(request, "Ya tienes otra cuenta de Google vinculada.")
                GoogleIdentity.objects.get_or_create(subject=subject, defaults={"user": request.user})
                messages.success(request, "Cuenta de Google vinculada. Ya puedes usarla para entrar.")
                return redirect("accounts:profile")
            if request.user.is_authenticated:
                return failure(request, "Tu sesión cambió. Sal de tu cuenta antes de iniciar otro acceso.")
            if identity:
                user = identity.user
            else:
                if User.objects.filter(email__iexact=email).exists():
                    return failure(
                        request,
                        "Entra primero con tu contraseña y vincula Google desde Mi cuenta. Si la olvidaste, puedes recuperarla.",
                    )
                user = User.objects.create_user(
                    email,
                    display_name=str(claims.get("name") or email.split("@")[0])[:100],
                    email_verified=True,
                )
                GoogleIdentity.objects.create(user=user, subject=subject)
            if not user.is_active:
                return failure(request, "No se puede acceder a esta cuenta.", 403)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    except IntegrityError:
        return failure(request, "La cuenta cambió durante el acceso. Entra de nuevo para continuar.")
    return redirect(flow["next"])
