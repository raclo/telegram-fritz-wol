from types import SimpleNamespace
from unittest.mock import MagicMock

from telegram.error import BadRequest, Forbidden, NetworkError, TimedOut

from telegram_fritz_wol.bot import BotHandlers
from telegram_fritz_wol.i18n import translate
from telegram_fritz_wol.router import Reachability
from telegram_fritz_wol.service import WolService

from .common import AsyncOfflineTestCase, DEVICES, settings, update


class ActivityTests(AsyncOfflineTestCase):
    def handlers(self, language):
        router = MagicMock()
        router.status.return_value = Reachability.ACTIVE
        return BotHandlers(settings(language), WolService(DEVICES, router, language)), router

    async def test_commands_send_typing_before_tr064_in_both_languages(self):
        for language in ("en", "it"):
            for action, method in (("wol", "wake"), ("status", "status")):
                with self.subTest(language=language, action=action):
                    handlers, router = self.handlers(language)
                    candidate = update()
                    events = []
                    candidate.get_bot().send_chat_action.side_effect = lambda **kwargs: events.append("typing")

                    def call_router(mac):
                        events.append("tr064")
                        return Reachability.ACTIVE

                    getattr(router, method).side_effect = call_router
                    await getattr(handlers, action)(candidate, SimpleNamespace(args=["test-a"]))
                    self.assertEqual(events, ["typing", "tr064"])
                    candidate.get_bot().send_chat_action.assert_awaited_once_with(chat_id=123, action="typing")
                    getattr(router, method).assert_called_once_with(DEVICES[0].mac)
                    expected = (translate(language, "wol_accepted", name="Test A") if action == "wol" else
                                translate(language, "status_result", name="Test A", state=translate(language, "status_active")))
                    candidate.effective_message.reply_text.assert_awaited_once_with(expected)
                    candidate.effective_message.delete.assert_not_called()
                    candidate.effective_message.edit_text.assert_not_called()

    async def test_callbacks_acknowledge_then_send_typing_before_tr064(self):
        for language in ("en", "it"):
            for action, method in (("wol", "wake"), ("status", "status")):
                with self.subTest(language=language, action=action):
                    handlers, router = self.handlers(language)
                    candidate = update(callback=f"{action}:test-a")
                    events = []
                    candidate.callback_query.answer.side_effect = lambda: events.append("ack")
                    candidate.get_bot().send_chat_action.side_effect = lambda **kwargs: events.append("typing")

                    def call_router(mac):
                        events.append("tr064")
                        return Reachability.ACTIVE

                    getattr(router, method).side_effect = call_router
                    await handlers.callback(candidate, None)
                    self.assertEqual(events, ["ack", "typing", "tr064"])
                    candidate.callback_query.answer.assert_awaited_once_with()
                    candidate.get_bot().send_chat_action.assert_awaited_once_with(chat_id=123, action="typing")
                    getattr(router, method).assert_called_once_with(DEVICES[0].mac)
                    expected = (translate(language, "wol_accepted", name="Test A") if action == "wol" else
                                translate(language, "status_result", name="Test A", state=translate(language, "status_active")))
                    candidate.effective_message.reply_text.assert_awaited_once_with(expected)

    async def test_unauthorized_commands_and_callbacks_never_send_typing(self):
        for language in ("en", "it"):
            for user_id, chat_type in ((456, "private"), (None, "private"), (123, "group")):
                handlers, router = self.handlers(language)
                for action in ("wol", "status"):
                    candidate = update(user_id, chat_type)
                    await getattr(handlers, action)(candidate, SimpleNamespace(args=["test-a"]))
                    candidate.get_bot().send_chat_action.assert_not_awaited()
                    candidate = update(user_id, chat_type, callback=f"{action}:test-a")
                    await handlers.callback(candidate, None)
                    candidate.get_bot().send_chat_action.assert_not_awaited()
                router.wake.assert_not_called()
                router.status.assert_not_called()

    async def test_invalid_callbacks_never_send_typing(self):
        for language in ("en", "it"):
            handlers, router = self.handlers(language)
            for data in ("wol:unknown", "status:unknown", "reboot:test-a", "wol:test-a:extra", "invalid", object()):
                candidate = update(callback=data)
                await handlers.callback(candidate, None)
                candidate.get_bot().send_chat_action.assert_not_awaited()
                candidate.callback_query.answer.assert_awaited_once_with(translate(language, "invalid_selection"), show_alert=True)
            candidate = update(callback="wol:test-a")
            candidate.callback_query.message = None
            await handlers.callback(candidate, None)
            candidate.get_bot().send_chat_action.assert_not_awaited()
            router.wake.assert_not_called()
            router.status.assert_not_called()

    async def test_unconfigured_commands_keep_their_response_without_typing(self):
        for language in ("en", "it"):
            handlers, router = self.handlers(language)
            for action in ("wol", "status"):
                candidate = update()
                await getattr(handlers, action)(candidate, SimpleNamespace(args=["unknown"]))
                candidate.get_bot().send_chat_action.assert_not_awaited()
                candidate.effective_message.reply_text.assert_awaited_once_with(translate(language, "not_configured"))
            router.wake.assert_not_called()
            router.status.assert_not_called()

    async def test_menus_usage_and_other_commands_do_not_send_typing(self):
        for language in ("en", "it"):
            handlers, router = self.handlers(language)
            for action in ("wol", "status"):
                for args in ([], ["test-a", "test-b"]):
                    candidate = update()
                    await getattr(handlers, action)(candidate, SimpleNamespace(args=args))
                    candidate.get_bot().send_chat_action.assert_not_awaited()
            for handler in (handlers.help, handlers.list_devices, handlers.unknown):
                candidate = update()
                await handler(candidate, SimpleNamespace(args=[]))
                candidate.get_bot().send_chat_action.assert_not_awaited()
            router.wake.assert_not_called()
            router.status.assert_not_called()

    async def test_typing_failures_do_not_block_commands_or_callbacks_or_leak_details(self):
        for language in ("en", "it"):
            for action, method in (("wol", "wake"), ("status", "status")):
                for callback in (False, True):
                    for error in (TimedOut, NetworkError, Forbidden, BadRequest):
                        with self.subTest(language=language, action=action, callback=callback, error=error):
                            handlers, router = self.handlers(language)
                            candidate = update(callback=f"{action}:test-a" if callback else None)
                            candidate.get_bot().send_chat_action.side_effect = error("SECRET_TOKEN")
                            with self.assertLogs("telegram_fritz_wol", level="WARNING") as captured:
                                if callback:
                                    await handlers.callback(candidate, None)
                                    candidate.callback_query.answer.assert_awaited_once_with()
                                else:
                                    await getattr(handlers, action)(candidate, SimpleNamespace(args=["test-a"]))
                            getattr(router, method).assert_called_once_with(DEVICES[0].mac)
                            candidate.effective_message.reply_text.assert_awaited_once()
                            self.assertNotIn("SECRET_TOKEN", " ".join(captured.output))

    async def test_false_typing_result_does_not_block_operation(self):
        handlers, router = self.handlers("en")
        candidate = update()
        candidate.get_bot().send_chat_action.return_value = False
        await handlers.wol(candidate, SimpleNamespace(args=["test-a"]))
        router.wake.assert_called_once_with(DEVICES[0].mac)
