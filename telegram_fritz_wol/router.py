"""Synchronous TR-064 adapter; invoked in a worker thread by the bot."""

from enum import Enum
from threading import Lock

from fritzconnection import FritzConnection
from fritzconnection.core.exceptions import (
    FritzAuthorizationError,
    FritzConnectionException,
    FritzLookUpError,
    FritzSecurityError,
)
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

from .config import Settings


class Reachability(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"


class RouterError(Exception):
    """Safe error category: never carries the original exception message."""

    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


class FritzRouter:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._connection = None
        self._lock = Lock()

    def _call(self, action: str, mac: str) -> dict:
        with self._lock:
            try:
                if self._connection is None:
                    self._connection = FritzConnection(
                        address=self._settings.fritz_address,
                        user=self._settings.fritz_username,
                        password=self._settings.fritz_password,
                        timeout=self._settings.timeout,
                        use_tls=False,
                        use_cache=False,
                        redact_debug_log=True,
                    )
                return self._connection.call_action("Hosts1", action, NewMACAddress=mac)
            except FritzLookUpError:
                raise RouterError("unknown_host") from None
            except (FritzAuthorizationError, FritzSecurityError):
                raise RouterError("authentication") from None
            except Timeout:
                raise RouterError("timeout") from None
            except ConnectionError:
                raise RouterError("connection") from None
            except HTTPError as exc:
                category = "authentication" if exc.response is not None and exc.response.status_code in (401, 403) else "router"
                raise RouterError(category) from None
            except (FritzConnectionException, RequestException):
                raise RouterError("router") from None

    def wake(self, mac: str) -> None:
        # No automatic retry: a lost reply does not mean the command wasn't sent.
        self._call("X_AVM-DE_WakeOnLANByMACAddress", mac)

    def status(self, mac: str) -> Reachability:
        try:
            reply = self._call("GetSpecificHostEntry", mac)
        except RouterError as exc:
            if exc.category == "unknown_host":
                return Reachability.UNKNOWN
            raise
        active = reply.get("NewActive")
        if type(active) is bool:
            return Reachability.ACTIVE if active else Reachability.INACTIVE
        if type(active) is int and active in (0, 1):
            return Reachability.ACTIVE if active else Reachability.INACTIVE
        if isinstance(active, str):
            if active.strip().lower() in ("1", "true"):
                return Reachability.ACTIVE
            if active.strip().lower() in ("0", "false"):
                return Reachability.INACTIVE
        return Reachability.UNKNOWN

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.session.close()
                self._connection = None
