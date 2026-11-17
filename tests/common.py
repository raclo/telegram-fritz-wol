import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Message, Update

from telegram_fritz_wol.config import Device, Settings

# Synthetic test fixtures, unrelated to the deployment devices or accounts.
DEVICES = (
    Device("test-a", "Test A", "02:00:00:00:00:01"),
    Device("test-b", "Test B", "02:00:00:00:00:02"),
)


def settings(language="en"):
    return Settings("123:" + "A" * 35, frozenset({123}), "192.168.178.1",
                    "test-user", "test-password", 5, DEVICES, language)


def update(user_id=123, chat_type="private", callback=None):
    result = MagicMock(spec=Update)
    result.effective_user = SimpleNamespace(id=user_id) if user_id is not None else None
    result.effective_chat = SimpleNamespace(id=123, type=chat_type) if chat_type else None
    message = MagicMock(spec=Message)
    message.reply_text = AsyncMock()
    result.effective_message = message
    result.callback_query = None
    result.get_bot.return_value = SimpleNamespace(send_chat_action=AsyncMock(return_value=True))
    if callback is not None:
        result.callback_query = SimpleNamespace(data=callback, message=message, answer=AsyncMock())
    return result


class NetworkBlocker:
    def setUp(self):
        super().setUp()
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.getaddrinfo"):
            blocker = patch(target, side_effect=AssertionError("Network forbidden in unit tests"))
            blocker.start()
            self.addCleanup(blocker.stop)


class OfflineTestCase(NetworkBlocker, unittest.TestCase):
    pass


class AsyncOfflineTestCase(NetworkBlocker, unittest.IsolatedAsyncioTestCase):
    pass
