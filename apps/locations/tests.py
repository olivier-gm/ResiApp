import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import FederalEntity, Locality


class LocationTests(TestCase):
    def test_import_idempotent_and_dry_run(self):
        data = {
            "source": "test",
            "license": "test",
            "retrieved_at": "2026-10-28",
            "states": [{"code": "01", "name": "Estado"}],
            "localities": [{"code": "city", "name": "Ciudad", "state": "01"}],
        }
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "locations.json"
            file.write_text(json.dumps(data), encoding="utf-8")
            call_command("import_locations", str(file), dry_run=True)
            self.assertFalse(FederalEntity.objects.exists())
            call_command("import_locations", str(file))
            call_command("import_locations", str(file))
            self.assertEqual(Locality.objects.count(), 1)
            data["localities"][0]["state"] = "bad"
            file.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(CommandError):
                call_command("import_locations", str(file))
            self.assertEqual(Locality.objects.count(), 1)

    def test_invalid_parent_no_server_error(self):
        self.assertEqual(self.client.get("/ubicaciones/ciudades/?state=bad").status_code, 200)
