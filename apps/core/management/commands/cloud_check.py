import os
import uuid
from smtplib import SMTPException

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import DatabaseError, connection


class Command(BaseCommand):
    help = "Comprueba PostgreSQL y R2 contra un entorno de desarrollo declarado; no imprime secretos."

    def add_arguments(self, parser):
        parser.add_argument("--confirm-development-target", action="store_true")
        parser.add_argument(
            "--smtp-to", help="Opcional: enviar un correo de prueba a esta dirección indicada explícitamente."
        )

    def handle(self, *args, **options):
        if not options["confirm_development_target"] or os.getenv("RESIVE_CLOUD_CHECK_ALLOWED") != "1":
            raise CommandError(
                "Requiere RESIVE_CLOUD_CHECK_ALLOWED=1 y --confirm-development-target en un entorno de desarrollo."
            )
        if getattr(settings, "LOCAL_DEMO", False) or connection.vendor != "postgresql":
            raise CommandError("Esta comprobación requiere PostgreSQL remoto y R2, no el modo local.")
        storage_config = settings.STORAGES.get("default", {})
        storage_options = storage_config.get("OPTIONS", {})
        if (
            storage_config.get("BACKEND") != "storages.backends.s3.S3Storage"
            or not storage_options.get("querystring_auth", True)
            or storage_options.get("custom_domain")
        ):
            raise CommandError(
                "Configura R2 privado mediante S3Storage con URLs firmadas y sin dominio público."
            )
        if options.get("smtp_to"):
            try:
                validate_email(options["smtp_to"])
            except ValidationError:
                raise CommandError("La dirección SMTP de prueba no es válida.") from None
            if settings.EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend":
                raise CommandError("La prueba SMTP requiere el backend SMTP real.")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if cursor.fetchone() != (1,):
                    raise CommandError("PostgreSQL no devolvió el resultado esperado.")
        except CommandError:
            raise
        except DatabaseError as error:
            raise CommandError(f"Falló la conexión PostgreSQL ({type(error).__name__}).") from None
        self.stdout.write("PostgreSQL: consulta de conexión correcta.")
        key = f"smoke-check/{uuid.uuid4().hex}.txt"
        cleanup_keys = {key}
        problem = None
        try:
            payload = b"ResiVe development storage check\n"
            saved = default_storage.save(key, ContentFile(payload))
            cleanup_keys.add(saved)
            with default_storage.open(saved, "rb") as handle:
                if handle.read() != payload:
                    raise CommandError("R2 devolvió contenido diferente.")
            url = default_storage.url(saved)
            if "X-Amz-Signature=" not in url:
                raise CommandError("R2 no generó una URL firmada.")
        except (BotoCoreError, ClientError, OSError, CommandError, ValueError) as error:
            problem = f"Falló la comprobación R2 ({type(error).__name__})."
        finally:
            for cleanup_key in cleanup_keys:
                try:
                    default_storage.delete(cleanup_key)
                except (BotoCoreError, ClientError, OSError) as error:
                    problem = f"Falló la limpieza del objeto temporal R2 ({type(error).__name__}); revisa el prefijo smoke-check."
        if problem:
            raise CommandError(problem)
        self.stdout.write(
            "R2: escritura, lectura, URL firmada y eliminación correctas. La privacidad del bucket debe comprobarse también en Cloudflare."
        )
        if options.get("smtp_to"):
            try:
                sent = send_mail(
                    "Prueba de correo ResiVe",
                    "Este correo confirma una prueba solicitada del entorno de desarrollo de ResiVe.",
                    settings.DEFAULT_FROM_EMAIL,
                    [options["smtp_to"]],
                    fail_silently=False,
                )
            except (SMTPException, OSError, ValueError) as error:
                raise CommandError(f"Falló la prueba SMTP ({type(error).__name__}).") from None
            if sent != 1:
                raise CommandError("SMTP no aceptó el correo de prueba.")
            self.stdout.write(
                "SMTP: correo aceptado por el servidor; comprueba su llegada en la bandeja de destino."
            )
