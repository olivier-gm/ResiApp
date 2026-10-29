import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.locations.models import FederalEntity, Locality, Zone


class Command(BaseCommand):
    help = "Importa catálogo JSON validado sin borrar ubicaciones. --dry-run valida sin escribir."

    def add_arguments(self, parser):
        parser.add_argument("file", nargs="?", default=str(settings.BASE_DIR / "data/locations.json"))
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            data = json.loads(Path(options["file"]).read_text(encoding="utf-8"))
            if not all(
                data.get(key) for key in ["source", "license", "retrieved_at", "states", "localities"]
            ):
                raise ValueError("Faltan fuente, licencia, fecha o registros.")
            states = {row["code"]: row for row in data["states"]}
            cities = {row["code"]: row for row in data["localities"]}
            zones = {row["code"]: row for row in data.get("zones", [])}
            if (
                len(states) != len(data["states"])
                or len(cities) != len(data["localities"])
                or len(zones) != len(data.get("zones", []))
            ):
                raise ValueError("Códigos duplicados.")
            for rows, length in [(states.values(), 100), (cities.values(), 150), (zones.values(), 150)]:
                for row in rows:
                    if (
                        not row["name"].strip()
                        or len(row["name"]) > length
                        or not row["code"]
                        or len(row["code"]) > 30
                    ):
                        raise ValueError("Nombre o código inválido.")
            if any(row["state"] not in states for row in cities.values()):
                raise ValueError("Una localidad referencia una entidad inexistente.")
            if any(row["locality"] not in cities for row in zones.values()):
                raise ValueError("Una zona referencia una localidad inexistente.")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise CommandError(f"Catálogo inválido: {exc}") from exc
        if options["dry_run"]:
            self.stdout.write(
                f"Válido: {len(states)} entidades, {len(cities)} localidades, {len(zones)} zonas. Sin cambios."
            )
            return
        state_objects = {}
        for code, row in states.items():
            state_objects[code], _ = FederalEntity.objects.update_or_create(
                code=code, defaults={"name": row["name"]}
            )
        city_objects = {}
        for code, row in cities.items():
            city_objects[code], _ = Locality.objects.update_or_create(
                code=code,
                defaults={
                    "name": row["name"],
                    "state": state_objects[row["state"]],
                    "aliases": row.get("aliases", ""),
                },
            )
        for code, row in zones.items():
            Zone.objects.update_or_create(
                code=code, defaults={"name": row["name"], "locality": city_objects[row["locality"]]}
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Importadas {len(states)} entidades y {len(cities)} localidades. No se borraron registros."
            )
        )
