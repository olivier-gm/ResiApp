import re

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import (
    PasswordResetForm,
    UserChangeForm,
    UserCreationForm,
)
from django.template.loader import render_to_string

from .models import User


class RegistrationForm(forms.Form):
    display_name = forms.CharField(label="Nombre público", max_length=100)
    email = forms.EmailField(label="Correo electrónico")
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Repite la contraseña", widget=forms.PasswordInput)

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean(self):
        data = super().clean()
        if data.get("password1") != data.get("password2"):
            self.add_error("password2", "Las contraseñas no coinciden.")
        if data.get("password1"):
            candidate = User(email=data.get("email", ""), display_name=data.get("display_name", ""))
            try:
                password_validation.validate_password(data["password1"], candidate)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return data


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "display_name",
            "email",
            "phone",
            "advertiser_type",
            "whatsapp_enabled",
            "email_notifications",
        )
        help_texts = {
            "phone": "Incluye + y código de país, con 8 a 15 dígitos. Ejemplo: +58 412 123 4567. Los espacios, paréntesis y guiones se eliminan al guardar.",
            "whatsapp_enabled": "Si lo habilitas, tu número se compartirá en el enlace público de tus anuncios. No enviamos mensajes automáticamente.",
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("No se puede utilizar este correo.")
        return email

    def clean_phone(self):
        phone = re.sub(r"[ ()-]", "", self.cleaned_data["phone"].strip())
        if phone and not re.fullmatch(r"\+[1-9][0-9]{7,14}", phone):
            raise forms.ValidationError(
                "Usa + y el código de país, con 8 a 15 dígitos; por ejemplo, +584121234567."
            )
        return phone

    def clean(self):
        data = super().clean()
        if data.get("whatsapp_enabled") and not data.get("phone"):
            self.add_error("phone", "Indica un teléfono para habilitar WhatsApp.")
        return data


class QueuedPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        for user in User.objects.filter(email__iexact=email, is_active=True):
            if user.has_usable_password() or (user.email_verified and hasattr(user, "google_identity")):
                yield user

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        from apps.notifications.services import queue_email

        subject = "".join(render_to_string(subject_template_name, context).splitlines())
        queue_email(to_email, subject, render_to_string(email_template_name, context))


class AdminUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "display_name")


class AdminUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"
