import json
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from telegram_fritz_wol.config import ConfigError, load_devices, load_settings

from .common import DEVICES, OfflineTestCase, settings


class ConfigTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        # All temporary files remain inside the workspace.
        folder = TemporaryDirectory(dir=".")
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "devices.json"
        self.entries = [asdict(device) for device in DEVICES]
        self.write(self.entries)
        sample = settings()
        self.env = {
            "TELEGRAM_BOT_TOKEN": sample.token,
            "TELEGRAM_ALLOWED_USER_IDS": "123, 456",
            "FRITZ_USERNAME": sample.fritz_username,
            "FRITZ_PASSWORD": sample.fritz_password,
            "DEVICES_FILE": str(self.path),
        }

    def write(self, entries):
        self.path.write_text(json.dumps({"devices": entries}), encoding="utf-8")

    def test_valid_settings_and_secret_repr(self):
        result = load_settings(self.env)
        self.assertEqual(result.allowed_user_ids, frozenset({123, 456}))
        self.assertEqual(result.devices, DEVICES)
        self.assertEqual(result.fritz_address, "192.168.178.1")
        self.assertEqual(result.timeout, 5)
        self.assertEqual(result.language, "en")
        for secret in (result.token, result.fritz_username, result.fritz_password):
            self.assertNotIn(secret, repr(result))

    def test_explicit_supported_languages(self):
        for language in ("it", "en"):
            with self.subTest(language=language):
                self.assertEqual(load_settings({**self.env, "BOT_LANGUAGE": language}).language, language)

    def test_unsupported_languages_are_rejected_without_echoing_values(self):
        for language in ("", "de", "EN", "it-IT", " it ", "secret-invalid-language"):
            with self.subTest(language=language), self.assertRaises(ConfigError) as caught:
                load_settings({**self.env, "BOT_LANGUAGE": language})
            self.assertEqual(str(caught.exception), "Unsupported BOT_LANGUAGE. Use en or it.")

    def test_configuration_errors_use_selected_language(self):
        for language, expected in (("en", "Invalid TELEGRAM_BOT_TOKEN format."),
                                   ("it", "Formato TELEGRAM_BOT_TOKEN non valido.")):
            with self.subTest(language=language), self.assertRaises(ConfigError) as caught:
                load_settings({**self.env, "BOT_LANGUAGE": language, "TELEGRAM_BOT_TOKEN": "sensitive"})
            self.assertEqual(str(caught.exception), expected)
            self.assertNotIn("sensitive", str(caught.exception))

    def test_duplicate_json_key_error_uses_selected_language(self):
        self.path.write_text('{"devices": [], "devices": []}', encoding="utf-8")
        for language, expected in (("en", "Duplicate JSON key in the devices file."),
                                   ("it", "Chiave JSON duplicata nel file dispositivi.")):
            with self.subTest(language=language), self.assertRaises(ConfigError) as caught:
                load_settings({**self.env, "BOT_LANGUAGE": language})
            self.assertEqual(str(caught.exception), expected)

    def test_required_values_fail_closed(self):
        for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USER_IDS", "FRITZ_USERNAME", "FRITZ_PASSWORD"):
            for value in (None, "", " ", "REPLACE_WITH_VALUE"):
                with self.subTest(key=key, value=value):
                    env = self.env.copy()
                    if value is None:
                        env.pop(key)
                    else:
                        env[key] = value
                    with self.assertRaises(ConfigError):
                        load_settings(env)

    def test_invalid_user_id_lists(self):
        for value in ("0", "-123", "123,", "123,,456", "@username", "1.2", str(2**52)):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                load_settings({**self.env, "TELEGRAM_ALLOWED_USER_IDS": value})

    def test_malformed_token_and_error_redaction(self):
        secret = "deliberately-invalid-secret-token"
        with self.assertRaises(ConfigError) as caught:
            load_settings({**self.env, "TELEGRAM_BOT_TOKEN": secret})
        self.assertNotIn(secret, str(caught.exception))

    def test_timeout_bounds(self):
        for value in ("0", "16", "nan", "inf", "-inf", "abc"):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                load_settings({**self.env, "FRITZ_TIMEOUT_SECONDS": value})

    def test_router_address_validation(self):
        for value in ("http://192.168.178.1", "fritz.box", "8.8.8.8", "127.0.0.1", "224.0.0.1", "0.0.0.0"):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                load_settings({**self.env, "FRITZ_ADDRESS": value})

    def test_device_schema_and_limits(self):
        for value in ([], [self.entries[0]] * 33, "invalid", [{"id": "a"}], [None], [{**self.entries[0], "extra": 1}]):
            self.write(value)
            with self.subTest(value=value), self.assertRaises(ConfigError):
                load_devices(self.path)

    def test_invalid_device_values(self):
        cases = (
            ("id", "../test"), ("id", "test:a"), ("id", "x" * 25), ("id", 1),
            ("name", ""), ("name", "x" * 33), ("name", "Test\nName"), ("name", " Name"),
            ("mac", "REPLACE_WITH_MAC"), ("mac", "00:00:00:00:00:00"),
            ("mac", "FF:FF:FF:FF:FF:FF"), ("mac", "01:00:00:00:00:01"),
            ("mac", "02-00-00-00-00-01"), ("mac", 1),
        )
        for key, value in cases:
            self.write([{**self.entries[0], key: value}])
            with self.subTest(key=key, value=value), self.assertRaises(ConfigError):
                load_devices(self.path)

    def test_duplicate_ids_and_macs(self):
        for key in ("id", "mac"):
            self.write([self.entries[0], {**self.entries[1], key: self.entries[0][key]}])
            with self.subTest(key=key), self.assertRaises(ConfigError):
                load_devices(self.path)

    def test_mac_case_normalization(self):
        self.write([{**self.entries[0], "mac": "02:ab:cd:ef:00:01"}])
        self.assertEqual(load_devices(self.path)[0].mac, "02:AB:CD:EF:00:01")

    def test_missing_malformed_and_oversize_json(self):
        self.path.unlink()
        with self.assertRaises(ConfigError):
            load_devices(self.path)
        for content in ("{", "[]", '{"devices": [], "devices": []}', " " * 65537):
            self.path.write_text(content, encoding="utf-8")
            with self.subTest(content=content[:50]), self.assertRaises(ConfigError):
                load_devices(self.path)

    def test_example_devices_intentionally_reject_placeholders(self):
        with self.assertRaises(ConfigError):
            load_devices(Path("config/devices.example.json"))
