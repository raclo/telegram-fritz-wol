"""Device allowlist, bounded WoL frequency and truthful status messages."""

import asyncio
import logging
import time

from .config import Device
from .i18n import translate
from .router import FritzRouter, Reachability, RouterError

LOGGER = logging.getLogger("telegram_fritz_wol")
ERROR_KEYS = {
    "authentication": "error_authentication",
    "timeout": "error_timeout",
    "connection": "error_connection",
    "unknown_host": "error_unknown_host",
    "router": "error_router",
}


class WolService:
    def __init__(self, devices: tuple[Device, ...], router: FritzRouter, language: str = "en"):
        self.devices = {device.id: device for device in devices}
        self._language = language
        self._router = router
        self._last_attempt: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def execute(self, action: str, identifier: str) -> str:
        device = self.devices.get(identifier)
        if device is None or action not in ("wol", "status"):
            return translate(self._language, "not_configured")
        async with self._lock:
            if action == "wol":
                now = time.monotonic()
                previous = self._last_attempt.get(identifier)
                if previous is not None and now - previous < 10:
                    return translate(self._language, "cooldown")
                self._last_attempt[identifier] = now
            try:
                if action == "wol":
                    await asyncio.to_thread(self._router.wake, device.mac)
                    LOGGER.info("Richiesta WoL accettata dal router.")
                    return translate(self._language, "wol_accepted", name=device.name)
                state = await asyncio.to_thread(self._router.status, device.mac)
            except RouterError as exc:
                LOGGER.warning("Errore TR-064: %s.", exc.category)
                message = translate(self._language, ERROR_KEYS.get(exc.category, ERROR_KEYS["router"]))
                if action == "wol":
                    message = translate(self._language, "wol_error", error=message)
                return message
        labels = {
            Reachability.ACTIVE: "status_active",
            Reachability.INACTIVE: "status_inactive",
            Reachability.UNKNOWN: "status_unknown",
        }
        return translate(self._language, "status_result", name=device.name,
                         state=translate(self._language, labels[state]))

    async def close(self) -> None:
        await asyncio.to_thread(self._router.close)
