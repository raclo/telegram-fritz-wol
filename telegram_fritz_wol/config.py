"""Strict, offline configuration validation. Error messages never include values."""

import ipaddress
import json
import math
import os
import re
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Mapping

from .i18n import MESSAGES, translate


class ConfigError(ValueError):
    """Invalid local configuration; safe to display."""


@dataclass(frozen=True)
class Device:
    id: str
    name: str
    mac: str


@dataclass(frozen=True)
class Settings:
    token: str = field(repr=False)
    allowed_user_ids: frozenset[int]
    fritz_address: str
    fritz_username: str = field(repr=False)
    fritz_password: str = field(repr=False)
    timeout: float
    devices: tuple[Device, ...]
    language: str = "en"


def _required(env: Mapping[str, str], key: str, language: str) -> str:
    value = env.get(key, "")
    if not value.strip() or value.upper().startswith("REPLACE_"):
        raise ConfigError(translate(language, "config_required", variable=key))
    return value


def _unique_keys(pairs: list[tuple[str, object]], *, language: str) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError(translate(language, "config_duplicate_key"))
        result[key] = value
    return result


def load_devices(path: Path, language: str = "en") -> tuple[Device, ...]:
    try:
        if path.stat().st_size > 65536:
            raise ConfigError(translate(language, "config_file_size"))
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=partial(_unique_keys, language=language))
    except (OSError, UnicodeError, ValueError) as exc:
        if isinstance(exc, ConfigError):
            raise
        raise ConfigError(translate(language, "config_file_invalid")) from None
    if not isinstance(data, dict) or set(data) != {"devices"}:
        raise ConfigError(translate(language, "config_devices_key"))
    entries = data["devices"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 32:
        raise ConfigError(translate(language, "config_device_count"))
    devices = []
    ids, macs = set(), set()
    for item in entries:
        if not isinstance(item, dict) or set(item) != {"id", "name", "mac"}:
            raise ConfigError(translate(language, "config_device_fields"))
        identifier, name, mac = item["id"], item["name"], item["mac"]
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,23}", identifier):
            raise ConfigError(translate(language, "config_device_id"))
        if (not isinstance(name, str) or not 1 <= len(name) <= 32
                or name != name.strip() or not name.isprintable()):
            raise ConfigError(translate(language, "config_device_name"))
        if not isinstance(mac, str) or not re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", mac):
            raise ConfigError(translate(language, "config_device_mac"))
        octets = bytes.fromhex(mac.replace(":", ""))
        if octets == bytes(6) or octets[0] & 1:
            raise ConfigError(translate(language, "config_mac_unicast"))
        mac = mac.upper()
        if identifier in ids or mac in macs:
            raise ConfigError(translate(language, "config_duplicate_device"))
        ids.add(identifier)
        macs.add(mac)
        devices.append(Device(identifier, name, mac))
    return tuple(devices)


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    language = env.get("BOT_LANGUAGE", "en")
    if language not in MESSAGES:
        raise ConfigError(translate("en", "config_language"))
    token = _required(env, "TELEGRAM_BOT_TOKEN", language)
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]{20,}", token):
        raise ConfigError(translate(language, "config_token"))
    raw_ids = _required(env, "TELEGRAM_ALLOWED_USER_IDS", language).split(",")
    if any(not re.fullmatch(r"[0-9]+", value.strip()) for value in raw_ids):
        raise ConfigError(translate(language, "config_user_ids"))
    allowed_ids = frozenset(int(value.strip()) for value in raw_ids)
    if any(not 0 < value < 2**52 for value in allowed_ids):
        raise ConfigError(translate(language, "config_user_id_range"))
    address = env.get("FRITZ_ADDRESS", "192.168.178.1")
    try:
        ip = ipaddress.IPv4Address(address)
    except ipaddress.AddressValueError:
        raise ConfigError(translate(language, "config_address")) from None
    if ip.is_multicast or ip.is_unspecified or ip.is_loopback or not ip.is_private:
        raise ConfigError(translate(language, "config_address_private"))
    username = _required(env, "FRITZ_USERNAME", language)
    password = _required(env, "FRITZ_PASSWORD", language)
    try:
        timeout = float(env.get("FRITZ_TIMEOUT_SECONDS", "5"))
    except ValueError:
        raise ConfigError(translate(language, "config_timeout_numeric")) from None
    if not math.isfinite(timeout) or not 1 <= timeout <= 15:
        raise ConfigError(translate(language, "config_timeout_range"))
    devices = load_devices(Path(env.get("DEVICES_FILE", "/app/config/devices.json")), language)
    return Settings(token, allowed_ids, str(ip), username, password, timeout, devices, language)
