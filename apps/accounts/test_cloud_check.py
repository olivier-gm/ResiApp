from io import BytesIO, StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


@override_settings(
    LOCAL_DEMO=False,
    STORAGES={
        "default": {"BACKEND": "storages.backends.s3.S3Storage", "OPTIONS": {"querystring_auth": True}}
    },
)
class CloudCheckTests(SimpleTestCase):
    command_module = "apps.core.management.commands.cloud_check"

    def test_requires_both_explicit_development_guards(self):
        with patch.dict("os.environ", {"RESIVE_CLOUD_CHECK_ALLOWED": "0"}), self.assertRaises(CommandError):
            call_command("cloud_check", confirm_development_target=True, stdout=StringIO())
        with patch.dict("os.environ", {"RESIVE_CLOUD_CHECK_ALLOWED": "1"}), self.assertRaises(CommandError):
            call_command("cloud_check", stdout=StringIO())

    @override_settings(LOCAL_DEMO=True)
    def test_refuses_local_demo(self):
        with patch.dict("os.environ", {"RESIVE_CLOUD_CHECK_ALLOWED": "1"}), self.assertRaises(CommandError):
            call_command("cloud_check", confirm_development_target=True, stdout=StringIO())

    def run_with_storage(self, storage):
        connection = MagicMock()
        connection.vendor = "postgresql"
        connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (1,)
        with (
            patch.dict("os.environ", {"RESIVE_CLOUD_CHECK_ALLOWED": "1"}),
            patch(f"{self.command_module}.connection", connection),
            patch(f"{self.command_module}.default_storage", storage),
        ):
            call_command("cloud_check", confirm_development_target=True, stdout=StringIO())

    def test_success_verifies_own_object_and_deletes_it(self):
        storage = MagicMock()
        storage.save.side_effect = lambda key, content: key
        storage.open.return_value = BytesIO(b"ResiVe development storage check\n")
        storage.url.return_value = "https://r2.invalid/object?X-Amz-Signature=signature"
        self.run_with_storage(storage)
        key = storage.save.call_args.args[0]
        self.assertTrue(key.startswith("smoke-check/"))
        storage.delete.assert_called_once_with(key)

    def test_failure_cleans_requested_key_and_hides_secret_details(self):
        storage = MagicMock()
        storage.save.side_effect = OSError("secret credential must not be printed")
        with self.assertRaises(CommandError) as caught:
            self.run_with_storage(storage)
        self.assertNotIn("secret credential", str(caught.exception))
        self.assertEqual(storage.delete.call_count, 1)
