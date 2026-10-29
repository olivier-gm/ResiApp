from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.inquiries.models import Inquiry, Message
from apps.listings.models import Listing, ListingImage, ListingTransition
from apps.locations.models import FederalEntity, Locality

from .models import Report, ReportAccess


class ReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(
            "reportowner@example.com",
            "StrongPassword84!",
            display_name="Propietario",
            email_verified=True,
        )
        cls.seeker = User.objects.create_user(
            "reportseeker@example.com",
            "StrongPassword84!",
            display_name="Interesado",
            email_verified=True,
        )
        cls.outsider = User.objects.create_user(
            "reportoutsider@example.com",
            "StrongPassword84!",
            display_name="Otro",
            email_verified=True,
        )
        cls.listing = Listing.objects.create(
            owner=cls.owner,
            title="Anuncio público",
            status="published",
            amount="300.00",
        )
        cls.draft = Listing.objects.create(owner=cls.owner, title="Anuncio privado", status="draft")
        cls.inquiry = Inquiry.objects.create(listing=cls.listing, interested=cls.seeker)
        cls.message = Message.objects.create(
            inquiry=cls.inquiry,
            sender=cls.owner,
            body="Contenido denunciable en conversación privada",
        )

    def report(self, **target):
        return self.client.post(
            reverse("moderation:report"),
            {
                **target,
                "reason": "fraud",
                "details": "Esta información requiere una revisión del equipo.",
            },
        )

    def test_verified_user_can_report_public_listing_and_duplicates_are_idempotent(
        self,
    ):
        self.client.force_login(self.seeker)
        self.assertEqual(self.report(listing=self.listing.pk).status_code, 302)
        self.assertEqual(self.report(listing=self.listing.pk).status_code, 302)
        self.assertEqual(Report.objects.count(), 1)
        report = Report.objects.get()
        self.assertEqual(report.reporter, self.seeker)
        self.assertEqual(report.listing_title_snapshot, "Anuncio público")
        self.assertEqual(report.message_snapshot, "")

    def test_private_message_report_restricted_to_participants_and_minimal_snapshot(
        self,
    ):
        self.client.force_login(self.outsider)
        self.assertEqual(self.report(message=self.message.pk).status_code, 404)
        self.client.force_login(self.seeker)
        self.assertEqual(self.report(message=self.message.pk).status_code, 302)
        self.assertEqual(Report.objects.get().message_snapshot, self.message.body)
        self.assertIsNone(Report.objects.get().listing)

    def test_private_listing_and_invalid_targets_are_hidden(self):
        self.client.force_login(self.seeker)
        self.assertEqual(self.report(listing=self.draft.pk).status_code, 404)
        self.assertEqual(self.report(listing="invalid").status_code, 404)
        self.assertEqual(
            self.report(listing=self.listing.pk, message=self.message.pk).status_code,
            404,
        )
        self.assertEqual(self.report().status_code, 404)
        self.assertFalse(Report.objects.exists())

    def test_unverified_user_cannot_report(self):
        self.outsider.email_verified = False
        self.outsider.save()
        self.client.force_login(self.outsider)
        self.assertEqual(self.report(listing=self.listing.pk).status_code, 403)

    def test_validation_preserves_input_and_does_not_save(self):
        self.client.force_login(self.seeker)
        response = self.client.post(
            reverse("moderation:report"),
            {"listing": self.listing.pk, "reason": "fraud", "details": "Corto"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Corto")
        self.assertFalse(Report.objects.exists())

    def test_report_admin_requires_permission_and_records_evidence_access(self):
        report = Report.objects.create(
            reporter=self.seeker,
            message=self.message,
            reason="fraud",
            details="Motivo suficientemente descriptivo",
            listing_title_snapshot=self.listing.title,
            message_snapshot=self.message.body,
        )
        staff = get_user_model().objects.create_user(
            "moderator@example.com",
            "StrongPassword84!",
            display_name="Moderador",
            is_staff=True,
            email_verified=True,
        )
        self.client.force_login(staff)
        url = reverse("admin:moderation_report_change", args=[report.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertFalse(ReportAccess.objects.exists())
        staff.user_permissions.add(
            Permission.objects.get(codename="view_report", content_type__app_label="moderation")
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ReportAccess.objects.filter(report=report, user=staff).count(), 1)
        self.assertContains(response, self.message.body)
        self.assertNotIn(Message, admin.site._registry)


class ListingModerationAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from io import StringIO

        from django.contrib.auth.models import Group

        call_command("setup_roles", stdout=StringIO())
        User = get_user_model()
        cls.owner = User.objects.create_user(
            "mod-owner@example.com", "StrongPassword84!", display_name="Anunciante", email_verified=True
        )
        cls.moderator = User.objects.create_user(
            "mod-reviewer@example.com",
            "StrongPassword84!",
            display_name="Revisor",
            email_verified=True,
            is_staff=True,
        )
        cls.moderator.groups.add(Group.objects.get(name="Moderadores"))
        state = FederalEntity.objects.create(code="admin-test-state", name="Mérida")
        city = Locality.objects.create(code="admin-test-city", name="Mérida", state=state)
        cls.listing = Listing.objects.create(
            owner=cls.owner,
            title="Publicación a revisar",
            description="Vivienda con condiciones completas.",
            status="pending",
            amount="250.00",
            area="70",
            locality=city,
        )
        cls.photo = ListingImage.objects.create(
            listing=cls.listing,
            object_key="test/full.webp",
            thumbnail_key="test/thumb.webp",
            width=320,
            height=240,
        )
        cls.changelist = reverse("admin:listings_listing_changelist")

    def action(self, action, **extra):
        return self.client.post(
            self.changelist,
            {"action": action, "_selected_action": [str(self.listing.pk)], "select_across": "0", **extra},
        )

    def test_moderator_group_can_approve_but_cannot_edit_fields(self):
        self.client.force_login(self.moderator)
        self.assertFalse(self.moderator.has_perm("listings.change_listing"))
        response = self.client.get(self.changelist)
        self.assertContains(response, "Aprobar publicaciones pendientes")
        self.assertEqual(self.action("approve", index="0").status_code, 302)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "published")
        result = self.client.post(
            reverse("admin:listings_listing_change", args=[self.listing.pk]),
            {"title": "Título manipulado", "status": "draft"},
        )
        self.assertEqual(result.status_code, 403)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.title, "Publicación a revisar")
        self.assertEqual(self.listing.status, "published")

    def test_corrections_require_specific_reason_and_confirmed_submission(self):
        self.client.force_login(self.moderator)
        response = self.action("request_changes", index="0")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Motivo que verá el anunciante")
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "pending")
        response = self.action("request_changes", apply="1", reason="")
        self.assertEqual(response.status_code, 200)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "pending")
        reason = "La descripción debe aclarar los gastos que se pagan por separado."
        self.assertEqual(self.action("request_changes", apply="1", reason=reason).status_code, 302)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "changes")
        self.assertEqual(self.listing.moderation_reason, reason)
        self.assertEqual(ListingTransition.objects.get(listing=self.listing).reason, reason)

    def test_withdraw_records_reason_and_actor(self):
        self.client.force_login(self.moderator)
        reason = "Se retira por información de contacto que requiere comprobación."
        self.assertEqual(self.action("withdraw", apply="1", reason=reason).status_code, 302)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "removed")
        transition = ListingTransition.objects.get(listing=self.listing)
        self.assertEqual(transition.actor, self.moderator)
        self.assertEqual(transition.reason, reason)

    def test_view_only_staff_cannot_execute_moderation_action(self):
        staff = get_user_model().objects.create_user(
            "mod-readonly@example.com", "StrongPassword84!", display_name="Consulta", is_staff=True
        )
        staff.user_permissions.add(
            Permission.objects.get(content_type__app_label="listings", codename="view_listing")
        )
        self.client.force_login(staff)
        self.assertNotContains(self.client.get(self.changelist), "Aprobar publicaciones pendientes")
        self.action("withdraw", apply="1", reason="Intento de retirada sin permisos suficientes.")
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "pending")
        self.assertFalse(ListingTransition.objects.exists())

    def test_photo_previews_use_authorized_routes_without_signed_keys(self):
        self.client.force_login(self.moderator)
        response = self.client.get(reverse("admin:listings_listing_change", args=[self.listing.pk]))
        self.assertContains(response, reverse("listings:image", args=[self.photo.pk, "thumb"]))
        response = self.client.get(reverse("admin:listings_listingimage_change", args=[self.photo.pk]))
        self.assertContains(response, "Vista previa autorizada")
        self.assertContains(response, reverse("listings:image", args=[self.photo.pk, "full"]))
        self.assertNotContains(response, "X-Amz-Signature")
