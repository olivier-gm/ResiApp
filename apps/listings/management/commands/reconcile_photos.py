from datetime import timedelta

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from apps.listings.models import ListingImage


class Command(BaseCommand):
    help = "Detecta fotos huérfanas bajo listings/. Simulación por defecto; mínimo 24 h de gracia."

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true")
        parser.add_argument("--grace-hours", type=int, default=48)

    def handle(self, *args, **options):
        if options["grace_hours"] < 24:
            raise CommandError("El período de gracia no puede ser menor a 24 horas.")
        cutoff = timezone.now() - timedelta(hours=options["grace_hours"])
        candidates = 0
        try:
            for key in self.walk("listings"):
                if ListingImage.objects.filter(Q(object_key=key) | Q(thumbnail_key=key)).exists():
                    continue
                if default_storage.get_modified_time(key) > cutoff:
                    continue
                candidates += 1
                self.stdout.write(f"Huérfano: {key}")
                if options["delete"]:
                    default_storage.delete(key)
        except FileNotFoundError:
            pass
        self.stdout.write(
            f"{candidates} objetos {'eliminados' if options['delete'] else 'candidatos; simulación sin borrar'}."
        )

    def walk(self, prefix):
        directories, files = default_storage.listdir(prefix)
        for filename in files:
            yield f"{prefix}/{filename}"
        for directory in directories:
            yield from self.walk(f"{prefix}/{directory}")
