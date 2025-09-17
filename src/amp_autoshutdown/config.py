"""Configuration management for AMP Auto Shutdown."""
from __future__ import annotations

import dataclasses
import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:  # Python 3.11+
    import tomllib  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for older interpreters
    import tomli as tomllib  # type: ignore

import tomli_w

try:
    import keyring
    from keyring.errors import KeyringError
except Exception:  # pragma: no cover - keyring unavailable
    keyring = None  # type: ignore
    KeyringError = Exception  # type: ignore

LOGGER = logging.getLogger(__name__)

PROGRAM_DATA_DIR = Path(os.environ.get("PROGRAMDATA", Path.home() / ".local" / "share"))
APP_DIR = PROGRAM_DATA_DIR / "AmpAutoShutdown"
CONFIG_PATH = APP_DIR / "config.toml"
LOG_DIR = APP_DIR / "logs"
CACHE_DIR = APP_DIR / "cache"
KEYRING_SERVICE = "AmpAutoShutdown"
DEFAULT_API_KEY_ALIAS = "default"
MAINTENANCE_DAY_VALUES = {"mon", "tue", "wed", "thu", "fri", "sat", "sun", "*"}


@dataclass
class MaintenanceWindow:
    """Represents a recurring maintenance window during which shutdown is suppressed."""

    days: List[str] = field(default_factory=lambda: ["sun"])
    start: str = "00:00"
    end: str = "06:00"

    def normalised_days(self) -> List[str]:
        return [d.lower() for d in self.days]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "days": [d.lower() for d in self.days],
            "start": self.start,
            "end": self.end,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MaintenanceWindow":
        days = data.get("days", [])
        if not isinstance(days, Iterable):
            days = []
        normalised = [str(day).lower() for day in days]
        valid = [d for d in normalised if d in MAINTENANCE_DAY_VALUES]
        if not valid:
            valid = ["*"]
        return cls(
            days=valid,
            start=str(data.get("start", "00:00")),
            end=str(data.get("end", "06:00")),
        )


@dataclass
class Config:
    """Application configuration persisted to TOML."""

    amp_base_url: str = ""
    api_key_alias: str = DEFAULT_API_KEY_ALIAS
    poll_interval_seconds: int = 30
    idle_delay_minutes: int = 10
    global_player_threshold: int = 0
    per_instance_thresholds: Dict[str, int] = field(default_factory=dict)
    selected_instances: List[str] = field(default_factory=list)
    maintenance_windows: List[MaintenanceWindow] = field(default_factory=list)
    dry_run: bool = True
    log_level: str = "INFO"
    verify_ssl: bool = True

    def to_dict(self, include_api_meta: bool = True) -> Dict[str, Any]:
        data = {
            "amp_base_url": self.amp_base_url,
            "api_key_alias": self.api_key_alias,
            "poll_interval_seconds": int(self.poll_interval_seconds),
            "idle_delay_minutes": int(self.idle_delay_minutes),
            "global_player_threshold": int(self.global_player_threshold),
            "per_instance_thresholds": {k: int(v) for k, v in self.per_instance_thresholds.items()},
            "selected_instances": list(self.selected_instances),
            "maintenance_windows": [window.to_dict() for window in self.maintenance_windows],
            "dry_run": bool(self.dry_run),
            "log_level": self.log_level,
            "verify_ssl": bool(self.verify_ssl),
        }
        if include_api_meta:
            data["api_key_present"] = keyring is not None and self.api_key_alias is not None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        maintenance_windows = [
            MaintenanceWindow.from_dict(entry)
            for entry in data.get("maintenance_windows", [])
            if isinstance(entry, dict)
        ]
        return cls(
            amp_base_url=str(data.get("amp_base_url", "")),
            api_key_alias=str(data.get("api_key_alias", DEFAULT_API_KEY_ALIAS)),
            poll_interval_seconds=int(data.get("poll_interval_seconds", 30)),
            idle_delay_minutes=int(data.get("idle_delay_minutes", 10)),
            global_player_threshold=int(data.get("global_player_threshold", 0)),
            per_instance_thresholds={
                str(key): int(value)
                for key, value in data.get("per_instance_thresholds", {}).items()
            },
            selected_instances=[str(item) for item in data.get("selected_instances", [])],
            maintenance_windows=maintenance_windows,
            dry_run=bool(data.get("dry_run", True)),
            log_level=str(data.get("log_level", "INFO")),
            verify_ssl=bool(data.get("verify_ssl", True)),
        )


DEFAULT_CONFIG = Config(
    maintenance_windows=[MaintenanceWindow(days=["sun"], start="01:00", end="05:00")]
)


class ConfigManager:
    """Handles loading, saving, and keyring management."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or CONFIG_PATH

    def ensure_directories(self) -> None:
        for path in {self.config_path.parent, LOG_DIR, CACHE_DIR}:
            path.mkdir(parents=True, exist_ok=True)

    def load(self) -> Config:
        if not self.config_path.exists():
            LOGGER.info("Config file not found, creating default configuration at %s", self.config_path)
            self.ensure_directories()
            self.save(DEFAULT_CONFIG)
            return dataclasses.replace(DEFAULT_CONFIG)
        with self.config_path.open("rb") as fh:
            raw = tomllib.load(fh)
        config = Config.from_dict(raw)
        return config

    def save(self, config: Config, api_key: Optional[str] = None) -> None:
        self.ensure_directories()
        if api_key:
            self._store_api_key(config.api_key_alias, api_key)
        with self.config_path.open("wb") as fh:
            tomli_w.dump(config.to_dict(), fh)

    def delete_storage(self) -> None:
        if self.config_path.parent.exists():
            shutil.rmtree(self.config_path.parent, ignore_errors=True)

    def get_api_key(self, alias: Optional[str] = None) -> Optional[str]:
        if keyring is None:
            return None
        alias = alias or DEFAULT_API_KEY_ALIAS
        try:
            return keyring.get_password(KEYRING_SERVICE, alias)
        except KeyringError as exc:  # pragma: no cover - depends on host environ
            LOGGER.warning("Failed to read API key from keyring: %s", exc)
            return None

    def _store_api_key(self, alias: Optional[str], api_key: str) -> None:
        if keyring is None:
            LOGGER.warning("keyring backend unavailable; API key will not be stored securely")
            return
        alias = alias or DEFAULT_API_KEY_ALIAS
        try:
            keyring.set_password(KEYRING_SERVICE, alias, api_key)
        except KeyringError as exc:  # pragma: no cover - depends on host environ
            LOGGER.warning("Failed to store API key in keyring: %s", exc)

    def clear_api_key(self, alias: Optional[str] = None) -> None:
        if keyring is None:
            return
        alias = alias or DEFAULT_API_KEY_ALIAS
        try:
            keyring.delete_password(KEYRING_SERVICE, alias)
        except KeyringError:
            pass
