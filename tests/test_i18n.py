import asyncio
from string import Formatter
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from telegram.error import NetworkError
from telegram.ext import CommandHandler

from telegram_fritz_wol.bot import BotHandlers, build_application, on_error
from telegram_fritz_wol.i18n import MESSAGES, translate
from telegram_fritz_wol.router import Reachability, RouterError
from telegram_fritz_wol.service import WolService

from .common import AsyncOfflineTestCase, DEVICES, OfflineTestCase, settings, update


class TranslationTests(OfflineTestCase):
    def test_languages_have_complete_matching_keys_and_placeholders(self):
        self.assertEqual(set(MESSAGES), {"en", "it"})
        self.assertEqual(set(MESSAGES["en"]), set(MESSAGES["it"]))
        for key in MESSAGES["en"]:
            placeholders = []
            for language in ("en", "it"):
                text = MESSAGES[language][key]
                self.assertTrue(text.strip(), (language, key))
                fields = {field for _, field, _, _ in Formatter().parse(text) if field is not None}
                self.assertTrue(all(field.isidentifier() for field in fields), key)
                placeholders.append(fields)
            self.assertEqual(*placeholders, key)

    def test_every_template_renders_named_placeholders(self):
        for language, messages in MESSAGES.items():
            for key, template in messages.items():
                fields = {field for _, field, _, _ in Formatter().parse(template) if field is not None}
                values = {field: f"test-{field}" for field in fields}
                with self.subTest(language=language, key=key):
                    result = translate(language, key, **values)
                    self.assertNotIn("{", result)
                    self.assertNotIn("}", result)
                    for value in values.values():
                        self.assertIn(value, result)

    def test_device_name_is_rendered_literally(self):
        for language in MESSAGES:
            name = "PC {name} <test>"
            self.assertIn(name, translate(language, "wol_accepted", name=name))

    def test_missing_placeholder_is_not_silently_ignored(self):
        for language in MESSAGES:
            with self.subTest(language=language), self.assertRaises(KeyError):
                translate(language, "wol_accepted")


class LocalizedBotTests(AsyncOfflineTestCase):
    def handlers(self, language):
        service = SimpleNamespace(devices={d.id: d for d in DEVICES}, execute=AsyncMock(return_value="result"))
        return BotHandlers(settings(language), service), service

    async def test_buttons_are_translated_but_callback_payloads_are_identical(self):
        expected = (("wol:test-a", "status:test-a"), ("wol:test-b", "status:test-b"))
        for language, labels in (("en", ("Wake Test A", "Status Test A")),
                                 ("it", ("Accendi Test A", "Stato Test A"))):
            handlers, _ = self.handlers(language)
            keyboard = handlers.keyboard().inline_keyboard
            self.assertEqual(tuple(tuple(b.callback_data for b in row) for row in keyboard), expected)
            self.assertEqual(tuple(b.text for b in keyboard[0]), labels)

    async def test_help_list_selection_usage_and_unknown_command_use_instance_language(self):
        for language in MESSAGES:
            handlers, service = self.handlers(language)
            candidate = update()
            # The user's own Telegram language must not override the instance.
            candidate.effective_user.language_code = "it" if language == "en" else "en"
            context = SimpleNamespace(args=[])
            for handler, key in ((handlers.help, "help"), (handlers.wol, "select_device"),
                                 (handlers.status, "select_device"), (handlers.unknown, "unknown_command")):
                await handler(candidate, context)
                self.assertEqual(candidate.effective_message.reply_text.call_args.args[0], translate(language, key))
            await handlers.list_devices(candidate, context)
            self.assertEqual(candidate.effective_message.reply_text.call_args.args[0],
                             translate(language, "device_list", devices="test-a — Test A\ntest-b — Test B"))
            await handlers.wol(candidate, SimpleNamespace(args=["test-a", "test-b"]))
            self.assertEqual(candidate.effective_message.reply_text.call_args.args[0],
                             translate(language, "command_usage", action="wol"))
            service.execute.assert_not_awaited()

    async def test_authorization_denials_are_localized_without_executing_commands(self):
        for language in MESSAGES:
            handlers, service = self.handlers(language)
            for user_id, chat_type in ((456, "private"), (123, "group"), (None, "private")):
                for handler in (handlers.help, handlers.list_devices, handlers.wol, handlers.status, handlers.unknown):
                    candidate = update(user_id, chat_type)
                    await handler(candidate, SimpleNamespace(args=["test-a"]))
                    candidate.effective_message.reply_text.assert_awaited_once_with(translate(language, "access_denied"))
                candidate = update(user_id, chat_type, callback="wol:test-a")
                await handlers.callback(candidate, None)
                candidate.callback_query.answer.assert_awaited_once_with(translate(language, "access_denied"), show_alert=True)
                candidate.effective_message.reply_text.assert_not_awaited()
            service.execute.assert_not_awaited()

    async def test_invalid_and_unavailable_callback_messages_are_localized(self):
        for language in MESSAGES:
            handlers, service = self.handlers(language)
            for data in ("wol:unknown", "reboot:test-a", "wol:test-a:extra", "invalid"):
                candidate = update(callback=data)
                await handlers.callback(candidate, None)
                candidate.callback_query.answer.assert_awaited_once_with(translate(language, "invalid_selection"), show_alert=True)
            candidate = update(callback="wol:test-a")
            candidate.callback_query.message = None
            await handlers.callback(candidate, None)
            candidate.callback_query.answer.assert_awaited_once_with(translate(language, "message_unavailable"), show_alert=True)
            service.execute.assert_not_awaited()

    async def test_valid_commands_and_callbacks_forward_unchanged_ids_and_actions(self):
        for language in MESSAGES:
            handlers, service = self.handlers(language)
            for action in ("wol", "status"):
                await getattr(handlers, action)(update(), SimpleNamespace(args=["test-b"]))
                service.execute.assert_awaited_once_with(action, "test-b")
                service.execute.reset_mock()
                candidate = update(callback=f"{action}:test-a")
                await handlers.callback(candidate, None)
                service.execute.assert_awaited_once_with(action, "test-a")
                candidate.callback_query.answer.assert_awaited_once_with()
                service.execute.reset_mock()

    async def test_registered_commands_and_service_language(self):
        for language in MESSAGES:
            with patch("telegram_fritz_wol.bot.WolService") as factory:
                factory.return_value.close = AsyncMock()
                application = build_application(settings(language))
                self.assertEqual(factory.call_args.args[2], language)
                commands = set().union(*(h.commands for h in application.handlers[0] if isinstance(h, CommandHandler)))
                self.assertEqual(commands, {"start", "help", "list", "status", "wol"})
                await application.post_shutdown(application)

    async def test_unexpected_errors_use_instance_language_without_leaking_details(self):
        for language in MESSAGES:
            candidate = update()
            context = SimpleNamespace(error=NetworkError("SECRET_TOKEN"),
                                      application=SimpleNamespace(bot_data={"settings": settings(language)}))
            with self.assertLogs("telegram_fritz_wol", level="ERROR") as captured:
                await on_error(candidate, context)
            candidate.effective_message.reply_text.assert_awaited_once_with(translate(language, "operation_failed"))
            self.assertNotIn("SECRET_TOKEN", " ".join(captured.output))


class LocalizedServiceTests(AsyncOfflineTestCase):
    async def test_wol_message_in_each_language_preserves_mac_and_uncertainty(self):
        for language, expected in (("en", "Power-on has not been verified."),
                                   ("it", "L'accensione non è stata verificata.")):
            router = MagicMock()
            service = WolService(DEVICES, router, language)
            reply = await service.execute("wol", "test-a")
            self.assertIn("Test A", reply)
            self.assertIn(expected, reply)
            router.wake.assert_called_once_with(DEVICES[0].mac)
            router.status.assert_not_called()

    async def test_status_states_are_translated_and_never_wake(self):
        for language in MESSAGES:
            router = MagicMock()
            service = WolService(DEVICES, router, language)
            for state, key in ((Reachability.ACTIVE, "status_active"),
                               (Reachability.INACTIVE, "status_inactive"), (Reachability.UNKNOWN, "status_unknown")):
                router.status.return_value = state
                reply = await service.execute("status", "test-a")
                self.assertEqual(reply, translate(language, "status_result", name="Test A", state=translate(language, key)))
                if language == "it":
                    self.assertIn("Le informazioni del router potrebbero non essere aggiornate.", reply)
                    self.assertNotIn("Il dato può essere ritardato", reply)
                else:
                    self.assertIn("Router information may be out of date.", reply)
                router.status.assert_called_with(DEVICES[0].mac)
            router.wake.assert_not_called()

    async def test_router_errors_and_unknown_selection_are_localized(self):
        for language in MESSAGES:
            for action in ("wol", "status"):
                for category in ("authentication", "timeout", "connection", "unknown_host", "router"):
                    router = MagicMock()
                    getattr(router, "wake" if action == "wol" else "status").side_effect = RouterError(category)
                    service = WolService(DEVICES, router, language)
                    message = await service.execute(action, "test-a")
                    error = translate(language, f"error_{category}")
                    self.assertEqual(message, translate(language, "wol_error", error=error) if action == "wol" else error)
            router = MagicMock()
            service = WolService(DEVICES, router, language)
            self.assertEqual(await service.execute("wol", "unknown"), translate(language, "not_configured"))
            router.wake.assert_not_called()

    async def test_cooldown_and_concurrent_clicks_are_unchanged_in_both_languages(self):
        for language in MESSAGES:
            router = MagicMock()
            service = WolService(DEVICES, router, language)
            with patch("telegram_fritz_wol.service.time.monotonic", return_value=100):
                replies = await asyncio.gather(*(service.execute("wol", "test-a") for _ in range(3)))
                self.assertEqual(replies[1:], [translate(language, "cooldown")] * 2)
                router.wake.assert_called_once_with(DEVICES[0].mac)
                await service.execute("wol", "test-b")
                self.assertEqual(router.wake.call_count, 2)
            with patch("telegram_fritz_wol.service.time.monotonic", return_value=111):
                await service.execute("wol", "test-a")
            self.assertEqual(router.wake.call_count, 3)
