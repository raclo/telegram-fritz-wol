from io import StringIO
from unittest.mock import patch
import signal

from telegram_fritz_wol.__main__ import main
from telegram_fritz_wol.config import ConfigError

from .common import OfflineTestCase, settings


class EntrypointTests(OfflineTestCase):
    def test_check_config_has_no_network_or_application_start(self):
        with patch("sys.argv", ["bot", "--check-config"]), \
             patch("telegram_fritz_wol.__main__.load_settings", return_value=settings()), \
             patch("telegram_fritz_wol.bot.build_application") as build:
            self.assertEqual(main(), 0)
            build.assert_not_called()

    def test_invalid_config_exits_before_building_bot(self):
        with patch("sys.argv", ["bot"]), \
             patch("telegram_fritz_wol.__main__.load_settings", side_effect=ConfigError("Invalid configuration")), \
             patch("telegram_fritz_wol.bot.build_application") as build:
            self.assertEqual(main(), 2)
            build.assert_not_called()

    def test_unsupported_language_exits_before_building_bot_without_leaking_value(self):
        output = StringIO()
        with patch("sys.argv", ["bot"]), patch("sys.stderr", output), \
             patch.dict("os.environ", {"BOT_LANGUAGE": "SECRET_UNSUPPORTED_LANGUAGE"}, clear=True), \
             patch("telegram_fritz_wol.bot.build_application") as build:
            self.assertEqual(main(), 2)
            build.assert_not_called()
        self.assertIn("Unsupported BOT_LANGUAGE", output.getvalue())
        self.assertNotIn("SECRET_UNSUPPORTED_LANGUAGE", output.getvalue())

    def test_polling_options_and_sigterm(self):
        with patch("sys.argv", ["bot"]), \
             patch("telegram_fritz_wol.__main__.load_settings", return_value=settings()), \
             patch("telegram_fritz_wol.bot.build_application") as build:
            self.assertEqual(main(), 0)
            options = build.return_value.run_polling.call_args.kwargs
            self.assertIn(signal.SIGTERM, options["stop_signals"])
            self.assertTrue(options["drop_pending_updates"])
            self.assertEqual(options["allowed_updates"], ["message", "callback_query"])

    def test_startup_failure_never_logs_exception_details(self):
        output = StringIO()
        with patch("sys.argv", ["bot"]), patch("sys.stderr", output), \
             patch("telegram_fritz_wol.__main__.load_settings", return_value=settings()), \
             patch("telegram_fritz_wol.bot.build_application", side_effect=RuntimeError("SECRET_TOKEN")):
            self.assertEqual(main(), 1)
        self.assertNotIn("SECRET_TOKEN", output.getvalue())
