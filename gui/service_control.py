"""Helpers to control the AMP Auto Shutdown Windows Service."""
from __future__ import annotations

import ctypes
import logging
from pathlib import Path

try:
    import win32service
    import win32serviceutil
    import pywintypes
    import winerror
except ImportError as exc:  # pragma: no cover - Windows only dependencies
    raise RuntimeError("Service control requires pywin32 on Windows") from exc

from amp_autoshutdown.service import SERVICE_NAME, SERVICE_DISPLAY_NAME, AmpAutoShutdownService

LOGGER = logging.getLogger(__name__)


def is_user_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # pragma: no cover - fails on non-Windows
        return False


def install_service(executable_path: Path, start: bool = True, extra_args: str = "--service") -> None:
    try:
        win32serviceutil.InstallService(
            AmpAutoShutdownService,
            SERVICE_NAME,
            SERVICE_DISPLAY_NAME,
            exeName=str(executable_path),
            exeArgs=extra_args,
            description="Monitors AMP instances and shuts down the host when idle.",
            startType=win32service.SERVICE_AUTO_START,
        )
    except pywintypes.error as exc:
        if exc.winerror == winerror.ERROR_SERVICE_EXISTS:
            LOGGER.info("Service already installed")
        elif exc.winerror == winerror.ERROR_ACCESS_DENIED:
            raise PermissionError("Administrator privileges required to install the service") from exc
        else:
            raise
    else:
        LOGGER.info("Service installed with executable %s", executable_path)
    if start:
        try:
            win32serviceutil.StartService(SERVICE_NAME)
        except pywintypes.error as exc:
            if exc.winerror == winerror.ERROR_SERVICE_ALREADY_RUNNING:
                LOGGER.info("Service already running")
            else:
                raise


def start_service() -> None:
    try:
        win32serviceutil.StartService(SERVICE_NAME)
    except pywintypes.error as exc:
        if exc.winerror == winerror.ERROR_SERVICE_ALREADY_RUNNING:
            LOGGER.info("Service already running")
        else:
            raise


def stop_service() -> None:
    try:
        win32serviceutil.StopService(SERVICE_NAME)
    except pywintypes.error as exc:
        if exc.winerror == winerror.ERROR_SERVICE_NOT_ACTIVE:
            LOGGER.info("Service already stopped")
        else:
            raise


def uninstall_service() -> None:
    try:
        stop_service()
    except pywintypes.error:
        pass
    try:
        win32serviceutil.RemoveService(SERVICE_NAME)
    except pywintypes.error as exc:
        if exc.winerror == winerror.ERROR_SERVICE_DOES_NOT_EXIST:
            LOGGER.info("Service already removed")
        else:
            raise


def is_service_installed() -> bool:
    try:
        win32serviceutil.QueryServiceStatus(SERVICE_NAME)
    except pywintypes.error as exc:
        if exc.winerror == winerror.ERROR_SERVICE_DOES_NOT_EXIST:
            return False
        raise
    return True


def query_status() -> str:
    try:
        status = win32serviceutil.QueryServiceStatus(SERVICE_NAME)
    except pywintypes.error as exc:
        if exc.winerror == winerror.ERROR_SERVICE_DOES_NOT_EXIST:
            return "Not Installed"
        raise
    state = status[1]
    mapping = {
        win32service.SERVICE_STOPPED: "Stopped",
        win32service.SERVICE_START_PENDING: "Start Pending",
        win32service.SERVICE_STOP_PENDING: "Stop Pending",
        win32service.SERVICE_RUNNING: "Running",
        win32service.SERVICE_CONTINUE_PENDING: "Continue Pending",
        win32service.SERVICE_PAUSE_PENDING: "Pause Pending",
        win32service.SERVICE_PAUSED: "Paused",
    }
    return mapping.get(state, f"Unknown ({state})")


def amp_autoshutdown_service_class_string() -> str:
    module = AmpAutoShutdownService.__module__
    return f"{module}.{AmpAutoShutdownService.__name__}"

