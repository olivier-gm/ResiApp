import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from authlib.integrations.django_client import OAuth
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from joserfc import jwt
from joserfc.jwk import RSAKey

from .forms import QueuedPasswordResetForm
from .models import GoogleIdentity, User


@override_settings(
    GOOGLE_CLIENT_ID="test-client", GOOGLE_CLIENT_SECRET="test-secret", PUBLIC_BASE_URL="http://testserver"
)
class GoogleTests(TestCase):
    def setUp(self):
        self.claims = {
            "sub": "google-subject",
            "email": "new@example.com",
            "email_verified": True,
            "name": "Nombre Google",
        }

    def callback(self, claims=None, connect_user=None, next_url="/panel/publicaciones/"):
        session = self.client.session
        session["google_flow"] = {"state": "valid-state", "user": connect_user, "next": next_url}
        session.save()
        with patch("apps.accounts.google.google_client") as factory:
            factory.return_value.authorize_access_token.return_value = {
                "userinfo": self.claims if claims is None else claims
            }
            return self.client.get(
                reverse("accounts:google_callback"), {"state": "valid-state", "code": "test-code"}
            )

    def test_new_google_account_verified_without_password(self):
        self.assertEqual(self.callback().status_code, 302)
        user = User.objects.get(email="new@example.com")
        self.assertTrue(user.email_verified)
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff)
        self.assertEqual(str(user.pk), self.client.session["_auth_user_id"])
        self.assertEqual(GoogleIdentity.objects.get().subject, "google-subject")

    def test_existing_email_never_automatically_links(self):
        User.objects.create_user("new@example.com", "password")
        self.assertEqual(self.callback().status_code, 400)
        self.assertFalse(GoogleIdentity.objects.exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_explicit_link_then_login_and_suspension(self):
        user = User.objects.create_user("local@example.com", "password")
        self.client.force_login(user)
        self.assertEqual(self.callback(connect_user=user.pk).status_code, 302)
        self.client.logout()
        self.assertEqual(self.callback().status_code, 302)
        self.assertEqual(str(user.pk), self.client.session["_auth_user_id"])
        self.client.logout()
        user.is_active = False
        user.save()
        self.assertEqual(self.callback().status_code, 403)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_link_cannot_move_an_identity_or_survive_changed_session(self):
        user = User.objects.create_user("first@example.com", "password")
        other = User.objects.create_user("second@example.com", "password")
        GoogleIdentity.objects.create(user=user, subject="google-subject")
        self.client.force_login(other)
        self.assertEqual(self.callback(connect_user=other.pk).status_code, 400)
        self.assertEqual(self.callback(connect_user=user.pk).status_code, 400)
        self.assertEqual(GoogleIdentity.objects.get().user_id, user.pk)

    def test_unverified_or_missing_claims_rejected(self):
        for claims in [
            {},
            {**self.claims, "email_verified": False},
            {**self.claims, "email_verified": "true"},
            {**self.claims, "email": "bad"},
        ]:
            with self.subTest(claims=claims):
                self.assertEqual(self.callback(claims).status_code, 400)
        self.assertFalse(User.objects.exists())

    def test_missing_state_and_replay_rejected(self):
        self.assertEqual(self.client.get(reverse("accounts:google_callback")).status_code, 400)
        self.callback()
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("accounts:google_callback"), {"state": "valid-state"}).status_code, 400
        )

    def test_start_requires_post_and_csrf_and_missing_config_handled(self):
        self.assertEqual(self.client.get(reverse("accounts:google_start")).status_code, 405)
        self.assertEqual(
            Client(enforce_csrf_checks=True).post(reverse("accounts:google_start")).status_code, 403
        )
        with override_settings(GOOGLE_CLIENT_ID=""):
            self.assertEqual(self.client.post(reverse("accounts:google_start")).status_code, 503)
            self.assertNotContains(self.client.get(reverse("accounts:login")), "Continuar con Google")

    def test_button_escapes_htmx_and_credentials_not_rendered(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, "Continuar con Google")
        self.assertContains(response, 'hx-boost="false"')
        self.assertNotContains(response, "test-secret")

    def real_client(self):
        self.key = RSAKey.generate_key(2048)
        return OAuth().register(
            "google",
            client_id="test-client",
            client_secret="test-secret",
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            access_token_url="https://oauth2.googleapis.com/token",
            issuer="https://accounts.google.com",
            jwks={"keys": [self.key.as_dict(private=False)]},
            client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"},
        )

    def test_sdk_checks_signed_token_nonce_audience_and_expiry(self):
        for invalid in [None, "nonce", "aud", "exp", "iss", "signature"]:
            self.client.logout()
            client = self.real_client()
            with patch("apps.accounts.google.google_client", return_value=client):
                response = self.client.post(
                    reverse("accounts:google_start"), {"next": "https://evil.invalid"}
                )
                self.assertEqual(response.status_code, 302)
                query = parse_qs(urlsplit(response.url).query)
                self.assertEqual(query["code_challenge_method"], ["S256"])
                self.assertEqual(self.client.session["google_flow"]["next"], "/panel/publicaciones/")
                claims = {
                    **self.claims,
                    "iss": "https://accounts.google.com",
                    "aud": "test-client",
                    "iat": int(time.time()),
                    "exp": int(time.time()) + 300,
                    "nonce": query["nonce"][0],
                }
                if invalid:
                    if invalid == "signature":
                        key = RSAKey.generate_key(2048)
                    else:
                        claims[invalid] = int(time.time()) - 600 if invalid == "exp" else "invalid"
                        key = self.key
                else:
                    key = self.key
                token = jwt.encode({"alg": "RS256"}, claims, key)
                with patch.object(client, "fetch_access_token", return_value={"id_token": token}):
                    callback = self.client.get(
                        reverse("accounts:google_callback"), {"state": query["state"][0], "code": "test-code"}
                    )
                self.assertEqual(callback.status_code, 302 if invalid is None else 400, invalid)
                if invalid is None:
                    User.objects.all().delete()

    def test_google_only_account_can_create_password_but_unverified_cannot(self):
        self.callback()
        user = User.objects.get()
        self.assertEqual(list(QueuedPasswordResetForm().get_users(user.email)), [user])
        user.email_verified = False
        user.save()
        self.assertEqual(list(QueuedPasswordResetForm().get_users(user.email)), [])

    def test_linked_login_does_not_verify_changed_local_email(self):
        user = User.objects.create_user("changed@example.com", None, email_verified=False)
        GoogleIdentity.objects.create(user=user, subject="google-subject")
        self.assertEqual(self.callback().status_code, 302)
        user.refresh_from_db()
        self.assertFalse(user.email_verified)

    def test_sdk_rejects_missing_state_and_cancelled_consent(self):
        client = self.real_client()
        with patch("apps.accounts.google.google_client", return_value=client):
            session = self.client.session
            session["google_flow"] = {"state": "no-sdk-state", "user": None, "next": "/"}
            session.save()
            with patch.object(client, "fetch_access_token") as exchange:
                self.assertEqual(
                    self.client.get(
                        reverse("accounts:google_callback"), {"state": "no-sdk-state", "code": "bad"}
                    ).status_code,
                    400,
                )
                exchange.assert_not_called()
            response = self.client.post(reverse("accounts:google_start"))
            state = parse_qs(urlsplit(response.url).query)["state"][0]
            self.assertEqual(
                self.client.get(
                    reverse("accounts:google_callback"), {"state": state, "error": "access_denied"}
                ).status_code,
                400,
            )
        self.assertFalse(User.objects.exists())
