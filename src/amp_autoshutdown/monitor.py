"""Monitoring loop for AMP Auto Shutdown."""
from __future__ import annotations

import logging
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Dict, Optional

from .api_amp import AMPAPIError, AMPClient
from .config import Config, ConfigManager
from .logging_setup import configure_logging

LOGGER = logging.getLogger(__name__)
SHUTDOWN_COMMAND = ["shutdown", "/s", "/t", "0"]


@dataclass
class ShutdownState:
    last_activity: datetime
    shutdown_triggered: bool = False


class ShutdownDecider:
    """Tracks activity and decides when an idle period justifies shutdown."""

    def __init__(self, config: Config) -> None:
        now = datetime.utcnow()
        self.state = ShutdownState(last_activity=now)
        self.update_config(config)

    def update_config(self, config: Config) -> None:
        self.config = config
        self.idle_delta = timedelta(minutes=max(1, config.idle_delay_minutes))

    def _threshold_for(self, instance_name: str) -> int:
        return self.config.per_instance_thresholds.get(instance_name, self.config.global_player_threshold)

    def register_observation(self, player_counts: Dict[str, int]) -> bool:
        if not player_counts:
            LOGGER.debug("No player counts provided; skipping shutdown evaluation")
            return False
        now = datetime.utcnow()
        above_threshold = any(
            count > self._threshold_for(name)
            for name, count in player_counts.items()
        )
        if above_threshold:
            LOGGER.debug("Activity detected; resetting idle timer")
            self.state.last_activity = now
            self.state.shutdown_triggered = False
            return False
        idle_time = now - self.state.last_activity
        LOGGER.debug("All instances below threshold for %s", idle_time)
        if idle_time >= self.idle_delta:
            LOGGER.debug("Idle period exceeded grace of %s", self.idle_delta)
            if not self.state.shutdown_triggered:
                self.state.shutdown_triggered = True
                return True
        return False


class Monitor:
    """Coordinates AMP polling and shutdown decisions."""

    def __init__(self, config_manager: Optional[ConfigManager] = None) -> None:
        self.config_manager = config_manager or ConfigManager()
        self.decider: Optional[ShutdownDecider] = None
        self.shutdown_initiated = False

    def run(self, stop_event: Optional[threading.Event] = None) -> None:
        stop_event = stop_event or threading.Event()
        config = self.config_manager.load()
        log_path = configure_logging(config.log_level)
        LOGGER.info("Monitor starting; logging to %s", log_path)
        self.decider = ShutdownDecider(config)

        while not stop_event.is_set():
            try:
                config = self.config_manager.load()
                configure_logging(config.log_level)
                if self.decider:
                    self.decider.update_config(config)
                self._poll_once(config, stop_event)
            except Exception as exc:  # pragma: no cover - defensive catch
                LOGGER.exception("Unhandled error in monitor loop: %s", exc)
            wait_seconds = max(5, config.poll_interval_seconds)
            stop_event.wait(wait_seconds)
        LOGGER.info("Monitor stop requested")

    def _poll_once(self, config: Config, stop_event: threading.Event) -> None:
        if not config.selected_instances:
            LOGGER.warning("No AMP instances selected for monitoring; skipping cycle")
            return

        if self._in_maintenance_window(config):
            LOGGER.debug("Within maintenance window; skipping shutdown checks")
            if self.decider:
                self.decider.state.last_activity = datetime.utcnow()
            return

        api_key = self.config_manager.get_api_key(config.api_key_alias)
        client = AMPClient(
            base_url=config.amp_base_url,
            api_key=api_key,
            verify_ssl=config.verify_ssl,
        )

        try:
            player_counts = client.get_player_counts(config.selected_instances)
        except AMPAPIError as exc:
            LOGGER.warning("AMP API unavailable: %s", exc)
            return

        LOGGER.info("Player counts: %s", player_counts)
        if self.decider and self.decider.register_observation(player_counts):
            self._trigger_shutdown(config)
            stop_event.set()

    def _trigger_shutdown(self, config: Config) -> None:
        if self.shutdown_initiated:
            LOGGER.debug("Shutdown already initiated; skipping")
            return
        self.shutdown_initiated = True
        if config.dry_run:
            LOGGER.warning("Dry-run enabled; system shutdown skipped")
            return
        LOGGER.warning("Idle threshold exceeded; issuing system shutdown command")
        try:
            subprocess.run(SHUTDOWN_COMMAND, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            LOGGER.error("Failed to execute shutdown command: %s", exc)

    def _in_maintenance_window(self, config: Config) -> bool:
        if not config.maintenance_windows:
            return False
        now = datetime.now()
        now_day = now.strftime("%a").lower()
        now_time = now.time()
        for window in config.maintenance_windows:
            days = {d.lower() for d in (window.days or ["*"])}
            if "*" not in days and now_day not in days:
                continue
            if self._time_in_window(now_time, window.start, window.end):
                return True
        return False

    @staticmethod
    def _time_in_window(current: time, start: str, end: str) -> bool:
        try:
            start_time = datetime.strptime(start, "%H:%M").time()
            end_time = datetime.strptime(end, "%H:%M").time()
        except ValueError:
            LOGGER.warning("Invalid maintenance window definitions: %s - %s", start, end)
            return False
        if start_time <= end_time:
            return start_time <= current <= end_time
        return current >= start_time or current <= end_time


def run_in_thread(stop_event: Optional[threading.Event] = None) -> threading.Thread:
    """Helper to run the monitor in a background thread (used by service)."""
    monitor = Monitor()
    stop_event = stop_event or threading.Event()
    thread = threading.Thread(target=monitor.run, args=(stop_event,), daemon=True)
    thread.start()
    return thread
