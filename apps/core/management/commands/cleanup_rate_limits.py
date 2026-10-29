from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import RateWindow


class Command(BaseCommand):
    help = "Elimina ventanas de límites expiradas."

    def handle(self, *args, **options):
        count, _ = RateWindow.objects.filter(expires_at__lt=timezone.now()).delete()
        self.stdout.write(f"{count} ventanas eliminadas.")
