from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase, override_settings

from .security import rate_limit


class CoreTests(TestCase):
    def test_home_and_routes(self):
        for url in [
            "/",
            "/alquileres/",
            "/ventas/",
            "/informacion/privacidad/",
            "/informacion/terminos/",
            "/informacion/ayuda/",
            "/healthz/",
            "/robots.txt",
            "/sitemap.xml",
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_rate_limit_shared_per_identity(self):
        request = RequestFactory().get("/")
        request.user = get_user_model().objects.create_user("rate@example.com", "secret")
        self.assertTrue(rate_limit(request, "test", limit=1))
        self.assertFalse(rate_limit(request, "test", limit=1))

    def test_private_cache(self):
        user = get_user_model().objects.create_user("private@example.com", "secret")
        self.client.force_login(user)
        response = self.client.get("/cuenta/perfil/")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("noindex", response["X-Robots-Tag"])

    @override_settings(TRUST_PROXY_SSL=True)
    def test_trusted_proxy_limits_separate_clients(self):
        request = RequestFactory().get("/", HTTP_X_REAL_IP="192.0.2.1")
        request.user = AnonymousUser()
        self.assertTrue(rate_limit(request, "proxy", limit=1))
        self.assertFalse(rate_limit(request, "proxy", limit=1))
        request.META["HTTP_X_REAL_IP"] = "192.0.2.2"
        self.assertTrue(rate_limit(request, "proxy", limit=1))

    @override_settings(LOCAL_DEMO=True, DEBUG=True)
    def test_demo_command_idempotent_and_guarded(self):
        from apps.listings.models import Listing
        from apps.locations.models import FederalEntity, Locality

        state = FederalEntity.objects.create(code="VE.14", name="Mérida")
        Locality.objects.create(code="demo-city", state=state, name="Mérida")
        call_command("seed_demo", password="LocalTestPassword2026")
        call_command("seed_demo", password="LocalTestPassword2026")
        self.assertEqual(Listing.objects.count(), 1)
        self.assertEqual(Listing.objects.get().images.count(), 1)
        with override_settings(LOCAL_DEMO=False), self.assertRaises(CommandError):
            call_command("seed_demo", password="LocalTestPassword2026")
