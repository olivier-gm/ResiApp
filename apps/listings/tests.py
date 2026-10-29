import os
import time
from decimal import Decimal
from io import BytesIO, StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse
from PIL import Image

from apps.locations.models import FederalEntity, Locality, Zone

from .forms import ListingForm, SearchForm
from .models import Favorite, Listing, ListingImage, ListingTransition
from .services import (
    add_photo,
    mark_edited,
    process_photo,
    remove_photo,
    transition_listing,
)


def photo_file():
    output = BytesIO()
    image = Image.new("RGB", (60, 40), color="green")
    exif = image.getexif()
    exif[270] = "Private address from camera"
    image.save(output, format="JPEG", exif=exif)
    return SimpleUploadedFile("foto.jpg", output.getvalue(), content_type="image/jpeg")


class ListingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(
            "owner@example.com",
            "safe-strong-password",
            display_name="Anunciante",
            email_verified=True,
        )
        cls.other = User.objects.create_user(
            "other@example.com",
            "safe-strong-password",
            display_name="Interesado",
            email_verified=True,
        )
        cls.staff = User.objects.create_superuser(
            "staff@example.com", "safe-strong-password", display_name="Moderador"
        )
        cls.state = FederalEntity.objects.create(code="VE-L", name="Mérida")
        cls.city = Locality.objects.create(code="merida", name="Mérida", state=cls.state)
        cls.other_city = Locality.objects.create(code="tovar", name="Tovar", state=cls.state)
        cls.zone = Zone.objects.create(code="centro", name="Centro", locality=cls.other_city)
        cls.listing = Listing.objects.create(
            owner=cls.owner,
            title="Apartamento tranquilo",
            description="Un apartamento con mucha luz.",
            amount=Decimal("220.00"),
            area=65,
            locality=cls.city,
        )

    def setUp(self):
        self.storage_dir = TemporaryDirectory()
        self.addCleanup(self.storage_dir.cleanup)
        self.storage_override = override_settings(
            STORAGES={
                "default": {
                    "BACKEND": "django.core.files.storage.FileSystemStorage",
                    "OPTIONS": {"location": self.storage_dir.name},
                },
                "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            }
        )
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)

    def complete(self):
        return add_photo(self.listing, self.owner, photo_file())

    def publish(self):
        self.complete()
        transition_listing(self.listing, self.owner, "pending")
        return transition_listing(self.listing, self.staff, "published")

    def test_review_requires_complete_listing_photo_and_verified_owner(self):
        with self.assertRaises(ValidationError):
            transition_listing(self.listing, self.owner, "pending")
        self.complete()
        self.owner.email_verified = False
        self.owner.save()
        with self.assertRaises(ValidationError):
            transition_listing(self.listing, self.owner, "pending")

    def test_owner_cannot_approve_and_approval_is_audited(self):
        self.complete()
        transition_listing(self.listing, self.owner, "pending")
        with self.assertRaises(PermissionDenied):
            transition_listing(self.listing, self.owner, "published")
        transition_listing(self.listing, self.staff, "published")
        self.assertEqual(ListingTransition.objects.filter(listing=self.listing).count(), 2)
        self.assertEqual(Listing.objects.public().count(), 1)

    def test_another_user_cannot_change_status_or_edit(self):
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.get(reverse("listings:edit", args=[self.listing.pk])).status_code,
            404,
        )
        with self.assertRaises(PermissionDenied):
            transition_listing(self.listing, self.other, "pending")

    def test_editing_published_listing_hides_it(self):
        self.publish()
        mark_edited(self.listing, self.owner)
        self.assertFalse(Listing.objects.public().exists())

    def test_inactive_owner_is_never_public(self):
        self.publish()
        self.owner.is_active = False
        self.owner.save()
        self.assertFalse(Listing.objects.public().exists())

    def test_cross_city_zone_rejected(self):
        self.listing.zone = self.zone
        with self.assertRaises(ValidationError):
            self.listing.full_clean()

    def test_price_order_requires_currency(self):
        form = SearchForm({"order": "price_up"})
        self.assertFalse(form.is_valid())
        self.assertIn("currency", form.errors)
        self.assertTrue(SearchForm({"order": "price_up", "currency": "USD"}).is_valid())

    def test_budget_and_unknown_filters_rejected(self):
        self.assertFalse(SearchForm({"minimum": "30", "maximum": "20", "currency": "USD"}).is_valid())
        self.assertFalse(SearchForm({"currency": "EUR"}).is_valid())
        self.assertFalse(SearchForm({"bedrooms": "abc"}).is_valid())

    def test_form_does_not_accept_owner_or_status(self):
        self.assertNotIn("owner", ListingForm().fields)
        self.assertNotIn("status", ListingForm().fields)

    def test_private_listing_does_not_leak_description_or_address(self):
        self.listing.exact_address = "PRIVATE EXACT ADDRESS"
        self.listing.save()
        response = self.client.get(self.listing.get_absolute_url())
        self.assertEqual(response.status_code, 404)
        self.publish()
        response = self.client.get(self.listing.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "PRIVATE EXACT ADDRESS")

    def test_signed_endpoint_denies_private_photo_to_other_user(self):
        photo = self.complete()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(photo.url).status_code, 404)
        self.client.force_login(self.owner)
        response = self.client.get(photo.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        response.close()

    def test_upload_strips_metadata_and_generates_webp(self):
        full, thumb, width, height = process_photo(photo_file())
        self.assertEqual((width, height), (60, 40))
        for content in (full, thumb):
            with Image.open(BytesIO(content)) as image:
                self.assertEqual(image.format, "WEBP")
                self.assertEqual(dict(image.getexif()), {})

    def test_fake_image_rejected(self):
        with self.assertRaises(ValidationError):
            process_photo(SimpleUploadedFile("foto.jpg", b"not-an-image", content_type="image/jpeg"))

    def test_oversize_upload_rejected(self):
        upload = photo_file()
        upload.size = 8 * 1024 * 1024 + 1
        with self.assertRaises(ValidationError):
            process_photo(upload)

    def test_photo_quota_is_enforced_on_server(self):
        for index in range(15):
            ListingImage.objects.create(
                listing=self.listing,
                object_key=f"full-{index}",
                thumbnail_key=f"thumb-{index}",
                width=1,
                height=1,
            )
        with self.assertRaises(ValidationError):
            self.complete()
        self.assertEqual(ListingImage.objects.count(), 15)

    def test_photo_sql_failure_cleans_already_uploaded_objects(self):
        with patch(
            "apps.listings.services.ListingImage.objects.create",
            side_effect=RuntimeError("SQL unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                self.complete()
        import os

        self.assertEqual(sum(len(files) for _, _, files in os.walk(self.storage_dir.name)), 0)

    def test_photo_deletion_runs_after_commit(self):
        photo = self.complete()
        key = photo.object_key
        with self.captureOnCommitCallbacks(execute=True):
            remove_photo(photo, self.owner)
        self.assertFalse(default_storage.exists(key))

    def test_favorite_writes_are_idempotent(self):
        self.publish()
        self.client.force_login(self.other)
        url = reverse("listings:favorite", args=[self.listing.pk])
        for _ in range(2):
            self.assertEqual(self.client.post(url, {"saved": "yes"}).status_code, 302)
        self.assertEqual(Favorite.objects.count(), 1)
        self.client.post(url, {"saved": "no"})
        self.assertFalse(Favorite.objects.exists())

    def test_favorite_get_never_writes(self):
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.get(reverse("listings:favorite", args=[self.listing.pk])).status_code,
            405,
        )

    def test_action_routes_are_not_captured_by_detail_slug(self):
        favorite = resolve(reverse("listings:favorite", args=[self.listing.pk]))
        inquiry = resolve(reverse("inquiries:create", args=[self.listing.pk]))
        self.assertEqual(favorite.view_name, "listings:favorite")
        self.assertIn(inquiry.view_name, ("inquiries:create", "inquiries:start"))

    def test_search_only_shows_matching_public_operation_and_currency(self):
        self.publish()
        Listing.objects.create(
            owner=self.owner,
            title="Venta fuera de rango",
            status="published",
            operation="sale",
            amount=999,
            area=50,
            locality=self.city,
        )
        response = self.client.get(reverse("listings:rentals"), {"currency": "USD", "maximum": "300"})
        self.assertContains(response, self.listing.title)
        self.assertNotContains(response, "Venta fuera de rango")

    def test_new_invalid_form_renders_without_photo_controls(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("listings:new"),
            {"title": "Title only invalid values", "amount": "invalid"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Añadir foto")

    def test_reconciliation_is_dry_by_default_and_protects_referenced_photos(self):
        photo = self.complete()
        orphan = default_storage.save("listings/orphan.webp", ContentFile(b"orphan"))
        fresh = default_storage.save("listings/fresh.webp", ContentFile(b"fresh"))
        old_time = time.time() - 72 * 3600
        for key in (photo.object_key, photo.thumbnail_key, orphan):
            os.utime(default_storage.path(key), (old_time, old_time))
        call_command("reconcile_photos", stdout=StringIO())
        self.assertTrue(default_storage.exists(orphan))
        call_command("reconcile_photos", delete=True, stdout=StringIO())
        self.assertFalse(default_storage.exists(orphan))
        self.assertTrue(default_storage.exists(photo.object_key))
        self.assertTrue(default_storage.exists(photo.thumbnail_key))
        self.assertTrue(default_storage.exists(fresh))


class LocationChoicePerformanceTests(TestCase):
    def test_location_labels_do_not_query_one_state_per_city(self):
        state = FederalEntity.objects.create(code="perf", name="Estado de prueba")
        Locality.objects.bulk_create(
            [Locality(code=f"perf-{i}", name=f"Ciudad {i}", state=state) for i in range(75)]
        )
        self.assertNotIn("Ciudad 74", str(SearchForm()["locality"]))
        for form in [SearchForm({"state": state.pk}), ListingForm({"state": state.pk})]:
            with self.subTest(form=type(form).__name__), CaptureQueriesContext(connection) as queries:
                html = str(form["locality"])
            self.assertIn("Ciudad 74, Estado de prueba", html)
            self.assertLessEqual(len(queries), 6)
