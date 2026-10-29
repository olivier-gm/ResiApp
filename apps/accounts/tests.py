from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.notifications.models import EmailDelivery

from .services import VERIFY_SALT, verification_token

User = get_user_model()
PASSWORD = "R3siVe-larga-segura-2026!"


@override_settings(PUBLIC_BASE_URL="https://resive.test")
class AccountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("vecina@example.com", PASSWORD, display_name="Vecina")

    def test_email_is_normalized_and_login_is_case_insensitive(self):
        user = User.objects.create_user("  OTRO@EXAMPLE.COM ", PASSWORD, display_name="Otro")
        self.assertEqual(user.email, "otro@example.com")
        self.assertTrue(self.client.login(username="OTRO@EXAMPLE.COM", password=PASSWORD))

    def test_database_rejects_case_duplicate(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=self.user.pk).update(email="DUPLICADO@example.com")
            other = User.objects.create_user("other@example.com", PASSWORD, display_name="Otro")
            User.objects.filter(pk=other.pk).update(email="duplicado@EXAMPLE.com")

    def test_registration_queues_mail_and_does_not_enumerate_duplicates(self):
        data = {
            "display_name": "Casa",
            "email": "nuevo@example.com",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
        first = self.client.post(reverse("accounts:register"), data)
        second = self.client.post(reverse("accounts:register"), {**data, "email": "NUEVO@EXAMPLE.COM"})
        self.assertEqual(first.status_code, 302)
        self.assertEqual(first.url, second.url)
        self.assertEqual(User.objects.filter(email="nuevo@example.com").count(), 1)
        self.assertEqual(EmailDelivery.objects.filter(to="nuevo@example.com").count(), 1)
        self.assertIn("https://resive.test/", EmailDelivery.objects.get().body)

    def test_verification_requires_post_and_is_single_use(self):
        url = reverse("accounts:verify", args=[verification_token(self.user)])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)
        self.assertEqual(self.client.post(url).status_code, 400)

    def test_verification_expired_or_malformed_is_rejected(self):
        with patch(
            "django.core.signing.time.time", return_value=(timezone.now() - timedelta(days=3)).timestamp()
        ):
            token = verification_token(self.user)
        self.assertEqual(self.client.post(reverse("accounts:verify", args=[token])).status_code, 400)
        malformed = signing.dumps(
            {"user": self.user.pk, "email": self.user.email, "nonce": "bad"}, salt=VERIFY_SALT
        )
        self.assertEqual(self.client.post(reverse("accounts:verify", args=[malformed])).status_code, 400)

    def test_profile_email_change_revokes_old_token_and_verification(self):
        self.user.email_verified = True
        self.user.save()
        old_token = verification_token(self.user)
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:profile"),
            {"display_name": "Vecina", "email": "nuevo@example.com", "phone": "", "advertiser_type": "owner"},
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "nuevo@example.com")
        self.assertFalse(self.user.email_verified)
        self.assertEqual(self.client.post(reverse("accounts:verify", args=[old_token])).status_code, 400)
        self.assertEqual(EmailDelivery.objects.get().to, "nuevo@example.com")

    def test_profile_cannot_promote_user_or_verify_own_email(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse("accounts:profile"),
            {
                "display_name": "Vecina",
                "email": self.user.email,
                "advertiser_type": "agent",
                "is_staff": "true",
                "email_verified": "true",
            },
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.email_verified)
        self.assertEqual(self.user.advertiser_type, "agent")

    def test_logout_requires_post_and_csrf(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse("accounts:logout")).status_code, 403)

    def test_login_and_verification_reject_missing_csrf(self):
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        self.assertEqual(
            client.post(
                reverse("accounts:login"), {"username": self.user.email, "password": PASSWORD}
            ).status_code,
            403,
        )
        url = reverse("accounts:verify", args=[verification_token(self.user)])
        self.assertEqual(client.post(url).status_code, 403)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)
        self.assertEqual(client.get(url).status_code, 200)
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post(url, {"csrfmiddlewaretoken": token}).status_code, 302)

    def test_suspended_account_cannot_use_existing_session(self):
        self.client.force_login(self.user)
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 302)

    def test_deletion_request_checks_password_and_preserves_account(self):
        self.client.force_login(self.user)
        self.client.post(reverse("accounts:request_deletion"), {"password": "wrong"})
        self.user.refresh_from_db()
        self.assertIsNone(self.user.deletion_requested_at)
        self.client.post(reverse("accounts:request_deletion"), {"password": PASSWORD})
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.deletion_requested_at)
        self.assertTrue(self.user.is_active)

    def test_password_reset_is_queued_and_does_not_expose_account(self):
        known = self.client.post(reverse("accounts:password_reset"), {"email": self.user.email})
        unknown = self.client.post(reverse("accounts:password_reset"), {"email": "absent@example.com"})
        self.assertEqual(known.url, unknown.url)
        mail = EmailDelivery.objects.get()
        self.assertEqual(mail.to, self.user.email)
        self.assertIn("https://resive.test/", mail.body)
        self.assertIn("/restablecer/", mail.body)

    def test_password_reset_link_completes_and_cannot_be_reused(self):
        from urllib.parse import urlsplit

        self.client.post(reverse("accounts:password_reset"), {"email": self.user.email})
        mail = EmailDelivery.objects.get()
        link = next(line for line in mail.body.splitlines() if line.startswith("https://"))
        path = urlsplit(link).path
        response = self.client.get(path, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Elige una nueva contraseña")
        new_password = PASSWORD + "renovada"
        target = response.redirect_chain[-1][0]
        result = self.client.post(
            target, {"new_password1": new_password, "new_password2": new_password}, follow=True
        )
        self.assertContains(result, "Tu contraseña está lista")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertFalse(self.user.check_password(PASSWORD))
        self.assertContains(self.client.get(path, follow=True), "Enlace no disponible")

    def test_htmx_profile_update_returns_complete_main_with_confirmation(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:profile"),
            {"display_name": "Nuevo nombre", "email": self.user.email, "advertiser_type": "owner"},
            HTTP_HX_REQUEST="true",
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="main"')
        self.assertContains(response, "Perfil actualizado")
        self.user.refresh_from_db()
        self.assertEqual(self.user.display_name, "Nuevo nombre")
        self.assertIn("no-store", response["Cache-Control"])

    def test_login_refreshes_account_navigation_without_document_navigation(self):
        page = self.client.get(reverse("accounts:login"))
        self.assertContains(page, 'hx-target="body"')
        self.assertContains(page, 'hx-select="unset"')
        result = self.client.post(
            reverse("accounts:login"),
            {"username": self.user.email, "password": PASSWORD},
            HTTP_HX_REQUEST="true",
            follow=True,
        )
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, "Mi cuenta")

    def test_login_rate_limited(self):
        with patch("apps.accounts.views.rate_limit", return_value=False):
            response = self.client.post(
                reverse("accounts:login"), {"username": self.user.email, "password": PASSWORD}
            )
        self.assertEqual(response.status_code, 429)

    def test_private_account_requires_authentication(self):
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 302)


class WhatsAppTests(TestCase):
    def setUp(self):
        from apps.listings.models import Listing

        self.user = User.objects.create_user(
            "contacto@example.com", display_name="Anunciante", phone="+584121234567", email_verified=True
        )
        self.listing = Listing.objects.create(
            owner=self.user,
            title="Apartamento de prueba",
            description="Información del inmueble.",
            status="published",
            amount="300.00",
        )

    def profile_data(self, phone, enabled=False):
        return {
            "display_name": self.user.display_name,
            "email": self.user.email,
            "phone": phone,
            "advertiser_type": "owner",
            "whatsapp_enabled": enabled,
        }

    def test_profile_normalizes_international_phone(self):
        from .forms import ProfileForm

        form = ProfileForm(self.profile_data("+58 (412) 123-4567", enabled=True), instance=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, "+584121234567")
        self.assertEqual(self.user.whatsapp_url, "https://wa.me/584121234567")

    def test_profile_rejects_non_international_and_non_ascii_numbers(self):
        from .forms import ProfileForm

        for phone in [
            "04121234567",
            "+1234567",
            "+1234567890123456",
            "+０１２３４５６７８９",
            "+012345678",
            "https://evil.invalid",
        ]:
            with self.subTest(phone=phone):
                form = ProfileForm(self.profile_data(phone), instance=self.user)
                self.assertFalse(form.is_valid())
                self.assertIn("phone", form.errors)

    def test_whatsapp_requires_opt_in_verified_active_account_and_valid_phone(self):
        self.assertEqual(self.user.whatsapp_url, "")
        self.user.whatsapp_enabled = True
        self.assertEqual(self.user.whatsapp_url, "https://wa.me/584121234567")
        for field, value in [
            ("email_verified", False),
            ("is_active", False),
            ("phone", "+１２３４５６７８９"),
        ]:
            with self.subTest(field=field):
                previous = getattr(self.user, field)
                setattr(self.user, field, value)
                self.assertEqual(self.user.whatsapp_url, "")
                setattr(self.user, field, previous)

    def test_public_detail_hides_phone_without_opt_in_and_shows_consented_link(self):
        response = self.client.get(self.listing.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Contactar por WhatsApp")
        self.assertNotContains(response, "584121234567")
        self.user.whatsapp_enabled = True
        self.user.save(update_fields=["whatsapp_enabled"])
        response = self.client.get(self.listing.get_absolute_url())
        self.assertContains(response, 'href="https://wa.me/584121234567"')
        self.assertContains(response, "Contactar por WhatsApp")
        self.assertContains(response, 'rel="noopener noreferrer" hx-boost="false"')

    def test_enabled_without_number_does_not_expose_contact_link(self):
        self.user.phone = ""
        self.user.whatsapp_enabled = True
        self.user.save(update_fields=["phone", "whatsapp_enabled"])
        response = self.client.get(self.listing.get_absolute_url())
        self.assertNotContains(response, "Contactar por WhatsApp")
