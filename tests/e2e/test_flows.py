import os
import re
import uuid
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from playwright.sync_api import expect, sync_playwright

from apps.inquiries.models import Inquiry, Message, VisitRequest
from apps.listings.models import Favorite, Listing
from apps.listings.services import add_photo, transition_listing
from apps.locations.models import FederalEntity, Locality

CHROME_PATH = Path(os.getenv("CHROME_EXECUTABLE", "C:/Program Files/Google/Chrome/Application/chrome.exe"))


@skipUnless(CHROME_PATH.is_file(), "E2E necesita Chrome: configura CHROME_EXECUTABLE.")
@override_settings(
    ALLOWED_HOSTS=["localhost", "127.0.0.1", "testserver"],
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class ResiVeBrowserTests(StaticLiveServerTestCase):
    """Real Chrome + isolated Django live server; no production resources."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Playwright sync keeps a loop active; ORM access in this test thread stays serial.
        cls.async_environment = patch.dict(os.environ, {"DJANGO_ALLOW_ASYNC_UNSAFE": "true"})
        cls.async_environment.start()
        cls.addClassCleanup(cls.async_environment.stop)
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(executable_path=str(CHROME_PATH), headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def setUp(self):
        User = get_user_model()
        self.password = "UnHogarSeguro-2026!"
        self.owner = User.objects.create_user(
            "owner-browser@example.com", self.password, display_name="Andrea", email_verified=True
        )
        self.interested = User.objects.create_user(
            "client-browser@example.com", self.password, display_name="Carlos", email_verified=True
        )
        self.moderator = User.objects.create_superuser(
            "staff-browser@example.com", self.password, display_name="Equipo"
        )
        self.state = FederalEntity.objects.create(code="browser-state", name="Mérida")
        self.city = Locality.objects.create(code="browser-city", name="Mérida", state=self.state)
        self.context = self.browser.new_context(viewport={"width": 1440, "height": 1000})
        self.page = self.context.new_page()
        self.page.set_default_timeout(15000)
        self.browser_errors = []
        self.page.on("pageerror", lambda error: self.browser_errors.append(str(error)))
        self.artifacts = Path(settings.BASE_DIR) / "test-results" / "e2e"
        self.artifacts.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if hasattr(self, "page") and not self.page.is_closed():
            self.page.screenshot(path=str(self.artifacts / f"{self._testMethodName}.png"), full_page=True)
        self.context.close()
        super().tearDown()

    def url(self, name, *args):
        return self.live_server_url + reverse(name, args=args)

    def mark_document(self):
        marker = str(uuid.uuid4())
        self.page.evaluate("value => window.__resiveDocument = value", marker)
        return marker

    def same_document(self, marker):
        self.assertEqual(self.page.evaluate("window.__resiveDocument"), marker)

    def login(self, user):
        self.page.goto(self.url("accounts:login"))
        self.page.wait_for_function("window.htmx !== undefined")
        marker = self.mark_document()
        self.page.locator("input[name=username]").fill(user.email)
        self.page.locator("input[name=password]").fill(self.password)
        self.page.get_by_role("button", name="Entrar", exact=True).click()
        try:
            expect(self.page.locator("header .account-nav .avatar")).to_be_visible()
        except AssertionError as exc:
            raise AssertionError(
                f"Login UI: {self.page.locator('body').inner_text()[:2400]} | JS errors: {self.browser_errors}"
            ) from exc
        expect(self.page.locator("header .account-nav")).to_contain_text("Consultas")
        expect(self.page.get_by_role("heading", name="Mis publicaciones", exact=True)).to_be_visible()
        self.same_document(marker)
        return marker

    def logout(self):
        self.page.locator("header .avatar").click()
        expect(self.page.get_by_role("heading", name="Mi cuenta", exact=True)).to_be_visible()
        marker = self.mark_document()
        self.page.get_by_role("button", name="Cerrar sesión", exact=True).click()
        expect(
            self.page.locator("header .account-nav").get_by_role("link", name="Ingresar", exact=True)
        ).to_be_visible()
        expect(self.page.locator("header .account-nav .avatar")).to_have_count(0)
        self.same_document(marker)

    @staticmethod
    def photo_bytes():
        output = BytesIO()
        Image.new("RGB", (600, 400), "#3c7161").save(output, "JPEG")
        return output.getvalue()

    def published_listing(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        listing = Listing.objects.create(
            owner=self.owner,
            title="Apartamento luminoso en Mérida",
            description="Apartamento cómodo cerca de servicios.",
            locality=self.city,
            area=65,
            amount="250.00",
        )
        add_photo(
            listing,
            self.owner,
            SimpleUploadedFile("apartamento.jpg", self.photo_bytes(), content_type="image/jpeg"),
        )
        transition_listing(listing, self.owner, "pending")
        return transition_listing(listing, self.moderator, "published")

    def assert_no_horizontal_overflow(self):
        self.assertLessEqual(
            self.page.evaluate("document.documentElement.scrollWidth"),
            self.page.evaluate("window.innerWidth") + 1,
        )

    def open_filters(self):
        details = self.page.locator(".filter-panel details")
        if details.get_attribute("open") is None:
            details.locator("summary").click()

    def test_publish_query_and_visit_without_full_document_reload(self):
        marker = self.login(self.owner)
        self.page.get_by_role("link", name="+ Publicar un inmueble", exact=True).click()
        expect(self.page.get_by_role("heading", name="Cuéntanos sobre tu espacio")).to_be_visible()
        self.page.locator("#id_title").fill("Hogar de prueba en Mérida")
        self.page.locator("#id_description").fill("Apartamento luminoso con servicios y buena ubicación.")
        self.page.locator("#id_state").select_option(str(self.state.pk))
        expect(self.page.locator("#id_locality option", has_text="Mérida")).to_have_count(1)
        self.page.locator("#id_locality").select_option(str(self.city.pk))
        self.page.locator("#id_amount").fill("275.00")
        self.page.locator("#id_area").fill("70.00")
        self.page.get_by_role("button", name="Guardar borrador", exact=True).click()
        expect(self.page.get_by_role("heading", name="Fotografías", exact=True)).to_be_visible()
        self.same_document(marker)
        self.page.locator("input[type=file]").set_input_files(
            {"name": "hogar.jpg", "mimeType": "image/jpeg", "buffer": self.photo_bytes()}
        )
        self.page.get_by_role("button", name="Añadir foto", exact=True).click()
        expect(self.page.get_by_text("Foto añadida.", exact=True)).to_be_visible()
        self.page.get_by_role("button", name="Enviar a revisión", exact=True).click()
        expect(self.page.get_by_text("En revisión", exact=True)).to_be_visible()
        self.same_document(marker)
        listing = Listing.objects.get(title="Hogar de prueba en Mérida")
        self.assertEqual(listing.status, "pending")
        self.assertEqual(listing.images.count(), 1)
        transition_listing(listing, self.moderator, "published")
        self.logout()

        marker = self.login(self.interested)
        self.page.locator("header nav").get_by_role("link", name="Alquilar", exact=True).click()
        expect(self.page.get_by_role("heading", name="1 inmueble", exact=True)).to_be_visible()
        self.open_filters()
        self.page.locator("#id_q").fill("Hogar de prueba")
        self.page.get_by_role("button", name="Buscar inmuebles", exact=True).click()
        expect(self.page.locator(".property-card")).to_have_count(1)
        self.same_document(marker)
        self.page.get_by_role("heading", name=listing.title, exact=True).get_by_role("link").click()
        expect(self.page.get_by_role("heading", name=listing.title, exact=True)).to_be_visible()
        self.page.get_by_role("button", name="♡ Guardar inmueble", exact=True).click()
        expect(self.page.get_by_role("button", name="♥ Guardado · quitar", exact=True)).to_have_attribute(
            "aria-pressed", "true"
        )
        self.assertTrue(Favorite.objects.filter(user=self.interested, listing=listing).exists())
        self.same_document(marker)

        self.page.get_by_role("link", name="Consultar y coordinar visita", exact=True).click()
        self.page.locator("textarea[name=body]").fill(
            "Hola, quisiera conocer este apartamento y coordinar una visita."
        )
        self.page.get_by_role("button", name="Enviar consulta", exact=True).click()
        expect(
            self.page.get_by_text(
                "Hola, quisiera conocer este apartamento y coordinar una visita.", exact=True
            )
        ).to_be_visible()
        self.page.locator("input[name=scheduled_at]").last.fill(
            (timezone.localtime() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        )
        self.page.get_by_role("button", name="Enviar propuesta", exact=True).click()
        expect(self.page.get_by_text("Pendiente de confirmación", exact=True)).to_be_visible()
        self.same_document(marker)
        inquiry = Inquiry.objects.get(listing=listing, interested=self.interested)
        self.assertEqual(Message.objects.filter(inquiry=inquiry).count(), 1)
        self.assertEqual(VisitRequest.objects.filter(inquiry=inquiry, status="pending").count(), 1)
        self.assert_no_horizontal_overflow()
        self.page.screenshot(path=str(self.artifacts / "desktop-consultation.png"), full_page=True)
        self.assertEqual(self.browser_errors, [])

    def test_mobile_navigation_filters_history_and_favorite(self):
        listing = self.published_listing()
        self.page.set_viewport_size({"width": 390, "height": 844})
        marker = self.login(self.interested)
        self.assert_no_horizontal_overflow()
        self.page.locator("header nav").get_by_role("link", name="Alquilar", exact=True).click()
        expect(self.page.locator(".property-card")).to_have_count(1)
        self.open_filters()
        self.page.locator("#id_currency").select_option("USD")
        self.page.locator("#id_maximum").fill("100")
        self.page.get_by_role("button", name="Buscar inmuebles", exact=True).click()
        expect(
            self.page.get_by_role("heading", name="No encontramos coincidencias", exact=True)
        ).to_be_visible()
        expect(self.page).to_have_url(re.compile(r"maximum=100"))
        self.same_document(marker)
        self.page.go_back()
        expect(self.page.locator(".property-card")).to_have_count(1)
        self.same_document(marker)
        self.assert_no_horizontal_overflow()
        self.page.screenshot(path=str(self.artifacts / "mobile-search.png"), full_page=True)
        self.page.get_by_role("heading", name=listing.title, exact=True).get_by_role("link").click()
        expect(self.page.get_by_role("heading", name=listing.title, exact=True)).to_be_visible()
        self.page.get_by_role("button", name="♡ Guardar inmueble", exact=True).click()
        expect(self.page.get_by_role("button", name="♥ Guardado · quitar", exact=True)).to_be_visible()
        self.same_document(marker)
        self.assert_no_horizontal_overflow()
        self.page.screenshot(path=str(self.artifacts / "mobile-detail.png"), full_page=True)
        self.logout()
        self.assertEqual(self.browser_errors, [])

    def test_search_login_and_favorite_work_without_javascript(self):
        listing = self.published_listing()
        self.context.close()
        self.context = self.browser.new_context(
            java_script_enabled=False, viewport={"width": 390, "height": 844}
        )
        self.page = self.context.new_page()
        self.page.goto(self.url("listings:rentals"))
        self.open_filters()
        self.page.locator("#id_state").select_option(str(self.state.pk))
        self.page.get_by_role("button", name="Buscar inmuebles", exact=True).click()
        self.page.locator("#id_locality").select_option(str(self.city.pk))
        self.page.locator("#id_currency").select_option("USD")
        self.page.locator("#id_maximum").fill("300")
        self.page.get_by_role("button", name="Buscar inmuebles", exact=True).click()
        expect(self.page.locator(".property-card")).to_have_count(1)
        self.page.goto(self.url("accounts:login"))
        self.page.locator("input[name=username]").fill(self.interested.email)
        self.page.locator("input[name=password]").fill(self.password)
        self.page.get_by_role("button", name="Entrar", exact=True).click()
        expect(self.page.locator("header .account-nav .avatar")).to_be_visible()
        self.page.goto(self.live_server_url + listing.get_absolute_url())
        self.page.get_by_role("button", name="♡ Guardar inmueble", exact=True).click()
        expect(self.page.get_by_role("button", name="♥ Guardado · quitar", exact=True)).to_be_visible()
        self.assertTrue(Favorite.objects.filter(user=self.interested, listing=listing).exists())

    def test_public_buy_and_header_navigation(self):
        self.page.goto(self.live_server_url + "/")
        self.page.wait_for_function("window.htmx !== undefined")
        marker = self.mark_document()
        self.page.get_by_role("link", name="Quiero comprar").click()
        expect(self.page).to_have_url(self.url("listings:sales"))
        expect(self.page.locator("h1")).to_have_text("Tu próximo hogar, a tu medida.")
        self.same_document(marker)
        for name, route in [
            ("Alquilar", "listings:rentals"),
            ("Comprar", "listings:sales"),
            ("Ingresar", "accounts:login"),
            ("Crear cuenta", "accounts:register"),
        ]:
            self.page.locator("header").get_by_role("link", name=name, exact=True).click()
            expect(self.page).to_have_url(self.url(route))
            self.same_document(marker)
        self.assertEqual(self.browser_errors, [])
