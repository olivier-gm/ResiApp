from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image, ImageDraw

from apps.listings.models import Amenity, Listing
from apps.listings.services import add_photo
from apps.locations.models import Locality


class Command(BaseCommand):
    help = "Crea datos claramente ficticios solo en LOCAL_DEMO. Requiere contraseña elegida por ti."

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.LOCAL_DEMO or not settings.DEBUG:
            raise CommandError("seed_demo solo está permitido en modo local.")
        if len(options["password"]) < 10:
            raise CommandError("Elige una contraseña local de al menos 10 caracteres.")
        user, _ = get_user_model().objects.get_or_create(
            email="demo@resive.local",
            defaults={"display_name": "Cuenta de demostración", "email_verified": True},
        )
        user.set_password(options["password"])
        user.save()
        for name in [
            "Agua",
            "Tanque de agua",
            "Internet",
            "Gas",
            "Electricidad de respaldo",
            "Ascensor",
            "Accesibilidad",
        ]:
            Amenity.objects.get_or_create(name=name)
        for city, state_code, title, amount, kind, color in [
            ("Caracas", "VE.25", "MUESTRA · Apartamento para una nueva etapa", "450", "apartment", "#c1ccae"),
            ("Valencia", "VE.07", "MUESTRA · Casa con espacio para compartir", "600", "house", "#ccbaa2"),
            ("Mérida", "VE.14", "MUESTRA · Anexo cerca de tus planes", "220", "annex", "#b1c5ca"),
        ]:
            locality = Locality.objects.filter(name=city, state__code=state_code).first()
            if not locality:
                continue
            listing, created = Listing.objects.get_or_create(
                owner=user,
                title=title,
                defaults={
                    "description": "Publicación ficticia para explorar ResiVe. Esta vivienda no existe ni se ofrece en alquiler. Las imágenes son ilustraciones de prueba.",
                    "locality": locality,
                    "amount": Decimal(amount),
                    "area": Decimal("80"),
                    "bedrooms": 2,
                    "property_type": kind,
                    "operation": "rent",
                },
            )
            if listing.locality_id != locality.pk:
                listing.locality = locality
                listing.save(update_fields=["locality"])
            if created:
                picture = Image.new("RGB", (1200, 800), color)
                draw = ImageDraw.Draw(picture)
                draw.rectangle((200, 200, 1000, 700), fill="#f3ecda")
                draw.polygon([(150, 210), (600, 50), (1050, 210)], fill="#55725a")
                draw.rectangle((320, 320, 520, 520), fill="#a6bdc5")
                draw.rectangle((700, 380, 870, 700), fill="#b18c69")
                draw.text(
                    (30, 740), "RESIVE / DEMOSTRACION - NO ES UNA OFERTA REAL", fill="#173d32", font_size=28
                )
                output = BytesIO()
                picture.save(output, "PNG")
                add_photo(
                    listing,
                    user,
                    SimpleUploadedFile("sample.png", output.getvalue(), content_type="image/png"),
                    "Ilustración de prueba; no es una vivienda real",
                )
                listing.status = "published"
                listing.save()
        self.stdout.write(
            "Datos ficticios preparados. Acceso: demo@resive.local con la contraseña proporcionada."
        )
