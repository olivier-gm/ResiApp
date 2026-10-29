import uuid

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetView
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.security import rate_limit

from .forms import ProfileForm, QueuedPasswordResetForm, RegistrationForm
from .services import VERIFY_SALT, send_verification

User = get_user_model()


def limited(request, scope, limit=10, seconds=3600):
    if not rate_limit(request, scope, limit=limit, seconds=seconds):
        return HttpResponse(
            "Demasiados intentos. Intenta de nuevo más tarde.",
            status=429,
            headers={"Retry-After": str(seconds)},
        )
    return None


class AccountLoginView(LoginView):
    template_name = "accounts/login.html"

    def post(self, request, *args, **kwargs):
        return limited(request, "login", limit=15, seconds=900) or super().post(request, *args, **kwargs)


class AccountPasswordResetView(PasswordResetView):
    form_class = QueuedPasswordResetForm
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.txt"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")

    def post(self, request, *args, **kwargs):
        return limited(request, "password-reset", limit=5) or super().post(request, *args, **kwargs)

    def form_valid(self, form):
        from urllib.parse import urlsplit

        from django.conf import settings

        public_url = urlsplit(settings.PUBLIC_BASE_URL)
        form.save(
            domain_override=public_url.netloc,
            use_https=public_url.scheme == "https",
            token_generator=self.token_generator,
            from_email=self.from_email,
            email_template_name=self.email_template_name,
            subject_template_name=self.subject_template_name,
            request=self.request,
        )
        return redirect(self.success_url)


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST":
        blocked = limited(request, "register", limit=5)
        if blocked:
            return blocked
        if form.is_valid():
            data = form.cleaned_data
            if not User.objects.filter(email__iexact=data["email"]).exists():
                try:
                    with transaction.atomic():
                        user = User.objects.create_user(
                            data["email"], data["password1"], display_name=data["display_name"]
                        )
                        send_verification(user)
                except IntegrityError:
                    pass
            return redirect("accounts:verification_sent")
    return render(request, "accounts/register.html", {"form": form})


def verification_sent(request):
    return render(request, "accounts/verification_sent.html")


@require_http_methods(["GET", "POST"])
def verify(request, token):
    valid = False
    try:
        payload = signing.loads(token, salt=VERIFY_SALT, max_age=48 * 3600)
        with transaction.atomic():
            user = User.objects.select_for_update().get(
                pk=payload["user"],
                email=payload["email"],
                verification_nonce=payload["nonce"],
                is_active=True,
                email_verified=False,
            )
            if request.method == "POST":
                user.email_verified = True
                user.verification_nonce = uuid.uuid4()
                user.save(update_fields=["email_verified", "verification_nonce"])
                messages.success(request, "Correo verificado. Ya puedes publicar y contactar.")
                return redirect("accounts:login")
            valid = True
    except signing.BadSignature, User.DoesNotExist, KeyError, ValueError, TypeError, ValidationError:
        pass
    return render(request, "accounts/verify.html", {"valid": valid}, status=200 if valid else 400)


@login_required
@require_POST
def resend_verification(request):
    blocked = limited(request, "resend-verification", limit=3)
    if blocked:
        return blocked
    if not request.user.email_verified:
        send_verification(request.user)
    messages.success(request, "Si tu correo está pendiente, recibirás un enlace de verificación.")
    return redirect("accounts:profile")


@login_required
def profile(request):
    previous_email = request.user.email
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save(commit=False)
                if user.email != previous_email:
                    user.email_verified = False
                    user.verification_nonce = uuid.uuid4()
                user.save()
                if user.email != previous_email:
                    send_verification(user)
        except IntegrityError:
            form.add_error("email", "No se puede utilizar este correo.")
        else:
            messages.success(
                request,
                "Perfil actualizado."
                if user.email == previous_email
                else "Perfil actualizado. Verifica el nuevo correo.",
            )
            return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})


@login_required
@require_POST
def request_deletion(request):
    blocked = limited(request, "request-deletion", limit=5)
    if blocked:
        return blocked
    if not request.user.check_password(request.POST.get("password", "")):
        messages.error(request, "Comprueba tu contraseña para solicitar la eliminación.")
    else:
        User.objects.filter(pk=request.user.pk, deletion_requested_at__isnull=True).update(
            deletion_requested_at=timezone.now()
        )
        messages.success(
            request,
            "Solicitud registrada. El equipo revisará la eliminación y la conservación necesaria de conversaciones y respaldos.",
        )
    return redirect("accounts:profile")
