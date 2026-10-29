import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.listings.models import Listing
from apps.notifications.models import Notification

from .models import Inquiry, Message, UserBlock, VisitRequest
from .services import create_inquiry, propose_visit, respond_visit, send_message


class InquiryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(
            "owner@example.com",
            "StrongPassword84!",
            display_name="Propietario",
            email_verified=True,
        )
        cls.seeker = User.objects.create_user(
            "seeker@example.com",
            "StrongPassword84!",
            display_name="Interesado",
            email_verified=True,
        )
        cls.outsider = User.objects.create_user(
            "outsider@example.com",
            "StrongPassword84!",
            display_name="Otro",
            email_verified=True,
        )
        cls.listing = Listing.objects.create(
            owner=cls.owner,
            title="Vivienda disponible",
            operation="rent",
            status="published",
            amount="200.00",
        )

    def new_inquiry(self):
        return create_inquiry(self.listing, self.seeker, "¿Hay disponibilidad para visitar?", uuid.uuid4())

    def test_duplicate_request_creates_one_thread_one_message_one_notification(self):
        token = uuid.uuid4()
        first = create_inquiry(self.listing, self.seeker, "Me interesa esta vivienda", token)
        second = create_inquiry(self.listing, self.seeker, "Me interesa esta vivienda", token)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Inquiry.objects.count(), 1)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.owner).count(), 1)

    def test_private_thread_rejects_outsider_get_and_post(self):
        inquiry = self.new_inquiry()
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(inquiry.get_absolute_url()).status_code, 404)
        self.assertEqual(
            self.client.post(
                inquiry.get_absolute_url(),
                {"body": "Mensaje no permitido", "client_token": uuid.uuid4()},
            ).status_code,
            404,
        )
        self.assertEqual(Message.objects.count(), 1)

    def test_services_reject_outsider_without_relying_on_views(self):
        inquiry = self.new_inquiry()
        with self.assertRaises(PermissionDenied):
            send_message(inquiry, self.outsider, "Mensaje no permitido", uuid.uuid4())
        with self.assertRaises(PermissionDenied):
            propose_visit(inquiry, self.outsider, timezone.now() + timedelta(days=1))
        visit = propose_visit(inquiry, self.seeker, timezone.now() + timedelta(days=1))
        with self.assertRaises(PermissionDenied):
            respond_visit(visit.pk, self.outsider, 1, "accept")

    def test_html_message_is_escaped_and_private_page_not_cached(self):
        inquiry = self.new_inquiry()
        send_message(inquiry, self.owner, "<script>alert('x')</script>", uuid.uuid4())
        self.client.force_login(self.seeker)
        response = self.client.get(inquiry.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert")
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_block_stops_both_directions_but_retains_history(self):
        inquiry = self.new_inquiry()
        UserBlock.objects.create(blocker=self.seeker, blocked=self.owner)
        for user in [self.seeker, self.owner]:
            with self.assertRaises(PermissionDenied):
                send_message(inquiry, user, "Este mensaje no debe enviarse", uuid.uuid4())
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(inquiry.get_absolute_url()).status_code, 200)

    def test_closed_listing_blocks_new_contacts_but_preserves_existing_messages(self):
        inquiry = self.new_inquiry()
        self.listing.status = "closed"
        self.listing.save()
        with self.assertRaises(PermissionDenied):
            create_inquiry(self.listing, self.outsider, "Me interesa consultar", uuid.uuid4())
        inquiry = Inquiry.objects.select_related("listing__owner", "interested").get(pk=inquiry.pk)
        send_message(inquiry, self.owner, "Gracias, ya se alquiló.", uuid.uuid4())
        self.assertEqual(inquiry.messages.count(), 2)

    def test_unverified_and_self_contact_rejected(self):
        self.seeker.email_verified = False
        with self.assertRaises(PermissionDenied):
            create_inquiry(self.listing, self.seeker, "Quiero consultar", uuid.uuid4())
        with self.assertRaises(PermissionDenied):
            create_inquiry(self.listing, self.owner, "Quiero consultar", uuid.uuid4())

    def test_only_recipient_marks_messages_read(self):
        inquiry = self.new_inquiry()
        self.client.force_login(self.owner)
        self.client.post(reverse("inquiries:mark_read", args=[inquiry.pk]))
        self.assertIsNotNone(inquiry.messages.get().read_at)

    def test_visits_require_other_acceptance_and_current_version(self):
        inquiry = self.new_inquiry()
        visit = propose_visit(inquiry, self.seeker, timezone.now() + timedelta(days=2))
        with self.assertRaises(PermissionDenied):
            respond_visit(visit.pk, self.seeker, 1, "accept")
        respond_visit(visit.pk, self.owner, 1, "accept")
        visit.refresh_from_db()
        self.assertEqual(visit.status, VisitRequest.Status.ACCEPTED)
        self.assertEqual(visit.version, 2)
        with self.assertRaises(ValidationError):
            respond_visit(visit.pk, self.seeker, 1, "cancel")
        respond_visit(visit.pk, self.owner, 2, "reschedule", timezone.now() + timedelta(days=4))
        visit.refresh_from_db()
        self.assertEqual(visit.status, VisitRequest.Status.PENDING)
        self.assertEqual(visit.proposed_by_id, self.owner.pk)
        respond_visit(visit.pk, self.seeker, 3, "accept")
        visit.refresh_from_db()
        self.assertEqual(visit.status, VisitRequest.Status.ACCEPTED)

    def test_visit_rejects_past_closed_and_outsider(self):
        inquiry = self.new_inquiry()
        with self.assertRaises(ValidationError):
            propose_visit(inquiry, self.owner, timezone.now() - timedelta(minutes=1))
        visit = propose_visit(inquiry, self.owner, timezone.now() + timedelta(days=1))
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse("inquiries:visit_respond", args=[visit.pk]),
            {"action": "accept", "version": 1},
        )
        self.assertEqual(response.status_code, 404)
        inquiry.listing.status = "closed"
        inquiry.listing.save()
        with self.assertRaises(ValidationError):
            propose_visit(inquiry, self.owner, timezone.now() + timedelta(days=1))

    def test_full_contact_and_visit_route(self):
        self.client.force_login(self.seeker)
        result = self.client.post(
            reverse("inquiries:create", args=[self.listing.pk]),
            {"body": "Quisiera coordinar una visita.", "client_token": uuid.uuid4()},
        )
        self.assertEqual(result.status_code, 302)
        inquiry = Inquiry.objects.get()
        self.assertEqual(self.client.get(inquiry.get_absolute_url()).status_code, 200)
        result = self.client.post(
            reverse("inquiries:visit_create", args=[inquiry.pk]),
            {"scheduled_at": (timezone.localtime() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")},
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(VisitRequest.objects.count(), 1)

    def test_block_views_only_for_thread_participants(self):
        inquiry = self.new_inquiry()
        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.post(reverse("inquiries:block", args=[inquiry.pk])).status_code,
            404,
        )
        self.client.force_login(self.seeker)
        self.assertEqual(
            self.client.post(reverse("inquiries:block", args=[inquiry.pk])).status_code,
            302,
        )
        self.assertTrue(UserBlock.objects.filter(blocker=self.seeker, blocked=self.owner).exists())
        self.client.post(reverse("inquiries:unblock", args=[inquiry.pk]))
        self.assertFalse(UserBlock.objects.exists())
