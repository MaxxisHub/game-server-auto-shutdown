"""CLI entry point for the AMP Auto Shutdown bundle."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from amp_autoshutdown.config import ConfigManager
from amp_autoshutdown.logging_setup import configure_logging

LOGGER = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AMP Auto Shutdown launcher")
    parser.add_argument("--service", action="store_true", help="Run as Windows Service")
    parser.add_argument("--install-service", action="store_true", help="Install the Windows Service")
    parser.add_argument("--uninstall-service", action="store_true", help="Uninstall the Windows Service")
    parser.add_argument("--start-service", action="store_true", help="Start the Windows Service")
    parser.add_argument("--stop-service", action="store_true", help="Stop the Windows Service")
    parser.add_argument("--gui", action="store_true", help="Force GUI launch")
    args = parser.parse_args(argv)

    if args.service:
        from amp_autoshutdown.service import run_service

        run_service()
        return 0

    config_manager = ConfigManager()
    config = config_manager.load()
    configure_logging(config.log_level)

    from amp_autoshutdown_gui import service_control

    is_frozen = getattr(sys, "frozen", False)
    if is_frozen:
        service_binary = Path(sys.executable)
        service_args = "--service"
    else:
        service_binary = Path(sys.executable)
        service_args = "-m amp_autoshutdown --service"
        LOGGER.debug("Running unfrozen launcher; service actions will call Python interpreter")

    if args.install_service:
        service_control.install_service(service_binary, extra_args=service_args)
        return 0

    if args.uninstall_service:
        service_control.uninstall_service()
        config_manager.delete_storage()
        return 0

    if args.start_service:
        service_control.start_service()
        return 0

    if args.stop_service:
        service_control.stop_service()
        return 0

    if not service_control.is_service_installed():
        LOGGER.info("Service not installed; installing before launching GUI")
        try:
            service_control.install_service(service_binary, extra_args=service_args)
        except PermissionError as exc:
            LOGGER.error("Administrator privileges required to install the service: %s", exc)
    else:
        LOGGER.debug("Service already installed")

    launch_gui()
    return 0


def launch_gui() -> None:
    from amp_autoshutdown_gui.app import run_gui

    run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
