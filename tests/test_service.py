import asyncio
from unittest.mock import MagicMock, patch

from telegram_fritz_wol.router import Reachability, RouterError
from telegram_fritz_wol.service import WolService

from .common import AsyncOfflineTestCase, DEVICES


class ServiceTests(AsyncOfflineTestCase):
    def setUp(self):
        super().setUp()
        self.router = MagicMock()
        self.service = WolService(DEVICES, self.router)

    async def test_only_configured_devices_and_actions(self):
        for action, identifier in (("wol", "missing"), ("wol", DEVICES[0].mac), ("reboot", "test-a")):
            reply = await self.service.execute(action, identifier)
            self.assertIn("not configured", reply)
        self.router.wake.assert_not_called()
        self.router.status.assert_not_called()

    async def test_wol_uses_configured_mac_and_does_not_confirm_power(self):
        reply = await self.service.execute("wol", "test-a")
        self.router.wake.assert_called_once_with(DEVICES[0].mac)
        self.router.status.assert_not_called()
        self.assertIn("Power-on has not been verified", reply)

    async def test_status_is_router_observation_and_never_wakes(self):
        for state in Reachability:
            self.router.status.return_value = state
            reply = await self.service.execute("status", "test-a")
            self.assertIn("router-reported status", reply)
            self.assertIn("Power-on or power-off has not been verified", reply)
            self.assertIn("No direct reachability test", reply)
        self.router.wake.assert_not_called()

    async def test_cooldown_per_device_and_expiration(self):
        with patch("telegram_fritz_wol.service.time.monotonic", return_value=100):
            await self.service.execute("wol", "test-a")
            reply = await self.service.execute("wol", "test-a")
            self.assertIn("10 seconds", reply)
            await self.service.execute("wol", "test-b")
        self.assertEqual(self.router.wake.call_count, 2)
        with patch("telegram_fritz_wol.service.time.monotonic", return_value=111):
            await self.service.execute("wol", "test-a")
        self.assertEqual(self.router.wake.call_count, 3)

    async def test_simultaneous_clicks_send_only_once(self):
        await asyncio.gather(*(self.service.execute("wol", "test-a") for _ in range(5)))
        self.router.wake.assert_called_once_with(DEVICES[0].mac)

    async def test_router_failures_have_safe_messages_and_no_retry(self):
        for category in ("timeout", "connection", "authentication", "router", "unknown_host"):
            service = WolService(DEVICES, self.router)
            self.router.wake.reset_mock()
            self.router.wake.side_effect = RouterError(category)
            reply = await service.execute("wol", "test-a")
            self.assertIn("WoL outcome unconfirmed", reply)
            self.router.wake.assert_called_once()
            await service.execute("wol", "test-a")
            self.router.wake.assert_called_once()

    async def test_async_shutdown_closes_router(self):
        await self.service.close()
        self.router.close.assert_called_once()
