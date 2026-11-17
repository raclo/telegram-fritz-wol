from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telegram.error import NetworkError
from telegram.ext import CallbackQueryHandler, CommandHandler

from telegram_fritz_wol.bot import BotHandlers, build_application, is_authorized, on_error

from .common import AsyncOfflineTestCase, DEVICES, settings, update


class AuthorizationTests(AsyncOfflineTestCase):
    def setUp(self):
        super().setUp()
        self.service = SimpleNamespace(devices={d.id: d for d in DEVICES}, execute=AsyncMock(return_value="result"))
        self.handlers = BotHandlers(settings(), self.service)
        self.context = SimpleNamespace(args=["test-a"])

    async def test_authorization_uses_user_id_and_private_chat(self):
        self.assertTrue(is_authorized(update(), frozenset({123})))
        for candidate in (update(456), update(None), update(chat_type="group"),
                          update(chat_type="supergroup"), update(chat_type="channel"), update(chat_type=None)):
            self.assertFalse(is_authorized(candidate, frozenset({123})))
        self.assertFalse(is_authorized(update(), frozenset()))

    async def test_every_message_handler_denies_unauthorized_users(self):
        for user_id, chat_type in ((456, "private"), (None, "private"), (123, "group")):
            for handler in (self.handlers.help, self.handlers.list_devices, self.handlers.wol,
                            self.handlers.status, self.handlers.unknown):
                candidate = update(user_id, chat_type)
                await handler(candidate, self.context)
                self.assertIn("unauthorized", candidate.effective_message.reply_text.call_args.args[0])
        self.service.execute.assert_not_awaited()

    async def test_callbacks_deny_unauthorized_users_before_action(self):
        for user_id, chat_type in ((456, "private"), (123, "group"), (None, "private")):
            candidate = update(user_id, chat_type, callback="wol:test-a")
            await self.handlers.callback(candidate, self.context)
            candidate.callback_query.answer.assert_awaited_once()
            candidate.effective_message.reply_text.assert_not_awaited()
        self.service.execute.assert_not_awaited()

    async def test_forged_or_obsolete_callbacks_never_execute(self):
        for data in ("wol:unknown", "reboot:test-a", "wol:test-a:extra", "wol:", "garbage", object()):
            candidate = update(callback=data)
            await self.handlers.callback(candidate, self.context)
            candidate.callback_query.answer.assert_awaited_once()
            self.assertIn("Invalid selection", candidate.callback_query.answer.call_args.args[0])
        self.service.execute.assert_not_awaited()

    async def test_valid_callback_acknowledges_before_execution(self):
        candidate = update(callback="wol:test-a")
        async def execute(*args):
            candidate.callback_query.answer.assert_awaited_once()
            return "result"
        self.service.execute.side_effect = execute
        await self.handlers.callback(candidate, self.context)
        self.service.execute.assert_awaited_once_with("wol", "test-a")
        candidate.effective_message.reply_text.assert_awaited_once_with("result")

    async def test_inaccessible_callback_message_does_not_execute(self):
        candidate = update(callback="wol:test-a")
        candidate.callback_query.message = None
        await self.handlers.callback(candidate, self.context)
        self.service.execute.assert_not_awaited()

    async def test_command_arguments_and_selection(self):
        for handler, action in ((self.handlers.wol, "wol"), (self.handlers.status, "status")):
            await handler(update(), SimpleNamespace(args=[]))
            self.service.execute.assert_not_awaited()
            await handler(update(), SimpleNamespace(args=["test-a", "test-b"]))
            self.service.execute.assert_not_awaited()
            await handler(update(), SimpleNamespace(args=["test-b"]))
            self.service.execute.assert_awaited_once_with(action, "test-b")
            self.service.execute.reset_mock()

    async def test_keyboard_payloads_within_telegram_limit(self):
        keyboard = self.handlers.keyboard()
        for row in keyboard.inline_keyboard:
            for button in row:
                self.assertLessEqual(len(button.callback_data.encode("utf-8")), 64)
                action, identifier = button.callback_data.split(":")
                self.assertIn(action, ("wol", "status"))
                self.assertIn(identifier, self.service.devices)

    async def test_build_application_registers_handlers_without_network(self):
        with patch("telegram_fritz_wol.router.FritzConnection") as factory:
            application = build_application(settings())
            commands = set()
            callbacks = []
            for handler in application.handlers[0]:
                if isinstance(handler, CommandHandler):
                    commands.update(handler.commands)
                if isinstance(handler, CallbackQueryHandler):
                    callbacks.append(handler)
            self.assertEqual(commands, {"start", "help", "list", "status", "wol"})
            self.assertEqual(len(callbacks), 1)
            await application.post_shutdown(application)
            factory.assert_not_called()

    async def test_error_handler_redacts_sensitive_exception(self):
        context = SimpleNamespace(error=NetworkError("https://api.telegram.org/botSECRET_TOKEN"))
        with self.assertLogs("telegram_fritz_wol", level="ERROR") as captured:
            await on_error(None, context)
        self.assertNotIn("SECRET_TOKEN", " ".join(captured.output))
