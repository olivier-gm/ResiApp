from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import EmailDelivery, Notification
from .services import notify, queue_email

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", PUBLIC_BASE_URL="https://resive.test"
)
class NotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "one@example.com", "password", display_name="Uno", email_verified=True
        )
        self.other = User.objects.create_user("two@example.com", "password", display_name="Dos")

    def test_notify_persists_notice_and_outbox_without_sending(self):
        notice = notify(self.user, "Nueva consulta", "/panel/consultas/")
        self.assertEqual(notice.user, self.user)
        self.assertEqual(EmailDelivery.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_unverified_user_receives_only_internal_notice(self):
        notify(self.other, "Aviso")
        self.assertEqual(Notification.objects.count(), 1)
        self.assertFalse(EmailDelivery.objects.exists())

    def test_email_preference_does_not_disable_internal_notices(self):
        self.user.email_notifications = False
        self.user.save()
        notify(self.user, "Nueva consulta")
        self.assertEqual(Notification.objects.count(), 1)
        self.assertFalse(EmailDelivery.objects.exists())

    def test_notification_rejects_external_and_protocol_relative_urls(self):
        for url in ["https://evil.test", "//evil.test", "javascript:alert(1)"]:
            with self.assertRaises(ValueError):
                notify(self.user, "Aviso", url)
        self.assertFalse(Notification.objects.exists())

    def test_notification_is_private(self):
        own = notify(self.user, "Aviso propio")
        other = notify(self.other, "Aviso secreto")
        self.client.force_login(self.user)
        response = self.client.get(reverse("notifications:inbox"))
        self.assertContains(response, "Aviso propio")
        self.assertNotContains(response, "Aviso secreto")
        self.assertEqual(
            self.client.post(reverse("notifications:mark_read", args=[other.pk])).status_code, 404
        )
        self.assertEqual(self.client.post(reverse("notifications:mark_read", args=[own.pk])).status_code, 302)
        own.refresh_from_db()
        self.assertIsNotNone(own.read_at)

    def test_worker_delivers_once_and_skips_sent(self):
        queued = queue_email(self.user.email, "Aviso", "Tu cuenta tiene una novedad.")
        call_command("send_emails", stdout=StringIO())
        call_command("send_emails", stdout=StringIO())
        queued.refresh_from_db()
        self.assertIsNotNone(queued.sent_at)
        self.assertEqual(queued.attempts, 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_worker_preserves_failed_mail_and_retries(self):
        queued = queue_email(self.user.email, "Aviso", "Mensaje")
        with patch("django.core.mail.EmailMessage.send", side_effect=ConnectionError("private detail")):
            call_command("send_emails", stdout=StringIO())
        queued.refresh_from_db()
        self.assertIsNone(queued.sent_at)
        self.assertEqual(queued.last_error, "ConnectionError")
        self.assertGreater(queued.next_attempt_at, timezone.now())
        EmailDelivery.objects.filter(pk=queued.pk).update(
            next_attempt_at=timezone.now() - timedelta(seconds=1)
        )
        call_command("send_emails", stdout=StringIO())
        queued.refresh_from_db()
        self.assertIsNotNone(queued.sent_at)
        self.assertEqual(queued.attempts, 2)
