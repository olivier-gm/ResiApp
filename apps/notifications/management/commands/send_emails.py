from datetime import timedelta
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.notifications.models import EmailDelivery


class Command(BaseCommand):
    help = "Entrega correos pendientes; programa este comando cada minuto. No imprime datos privados."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        delivered = 0
        attempted = 0
        candidates = list(
            EmailDelivery.objects.filter(
                sent_at__isnull=True, next_attempt_at__lte=timezone.now()
            ).values_list("pk", flat=True)[: max(0, options["limit"])]
        )
        for pk in candidates:
            with transaction.atomic():
                mail = EmailDelivery.objects.select_for_update().get(pk=pk)
                if mail.sent_at or mail.next_attempt_at > timezone.now():
                    continue
                attempted += 1
                mail.attempts += 1
                try:
                    # shortcut: SMTP no ofrece entrega exactamente una vez, usar proveedor idempotente si se requiere esa garantía.
                    message = EmailMessage(
                        mail.subject,
                        mail.body,
                        settings.DEFAULT_FROM_EMAIL,
                        [mail.to],
                        headers={"Message-ID": f"<resive-{mail.pk}@notifications.resive>"},
                    )
                    if message.send(fail_silently=False) != 1:
                        raise RuntimeError("DeliveryNotAccepted")
                except (OSError, SMTPException, RuntimeError) as error:
                    mail.last_error = type(error).__name__[:100]
                    mail.next_attempt_at = timezone.now() + timedelta(
                        seconds=min(86400, 60 * 2 ** min(mail.attempts, 10))
                    )
                else:
                    mail.sent_at = timezone.now()
                    mail.last_error = ""
                    delivered += 1
                mail.save(update_fields=["attempts", "next_attempt_at", "sent_at", "last_error"])
        self.stdout.write(f"Intentados: {attempted}; entregados: {delivered}.")
