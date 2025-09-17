"""Windows Service integration for AMP Auto Shutdown."""
from __future__ import annotations

import logging
import threading

try:  # pywin32 imports (only available on Windows)
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil
except ImportError as exc:  # pragma: no cover - handled at runtime on non-Windows
    servicemanager = None  # type: ignore
    win32event = None  # type: ignore
    win32service = None  # type: ignore
    win32serviceutil = None  # type: ignore
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None

from .config import ConfigManager
from .monitor import Monitor

LOGGER = logging.getLogger(__name__)

SERVICE_NAME = "AmpAutoShutdown"
SERVICE_DISPLAY_NAME = "AMP Auto Shutdown"
SERVICE_DESCRIPTION = "Shuts down the host when AMP instances are idle."


class AmpAutoShutdownService(win32serviceutil.ServiceFramework):  # type: ignore[misc]
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION

    def __init__(self, args):
        if IMPORT_ERROR:
            raise IMPORT_ERROR
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event_handle = win32event.CreateEvent(None, 0, 0, None)
        self.hWaitStop = self.stop_event_handle
        self._stop_flag = threading.Event()
        self.monitor = Monitor(ConfigManager())
        self._thread: threading.Thread | None = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        LOGGER.info("Service stop requested")
        win32event.SetEvent(self.stop_event_handle)
        self._stop_flag.set()

    def SvcDoRun(self):
        LOGGER.info("Service starting")
        servicemanager.LogInfoMsg(f"{SERVICE_DISPLAY_NAME} starting")
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        self._thread = threading.Thread(target=self.monitor.run, args=(self._stop_flag,), daemon=True)
        self._thread.start()
        win32event.WaitForSingleObject(self.stop_event_handle, win32event.INFINITE)
        self._shutdown()
        LOGGER.info("Service stopped")
        servicemanager.LogInfoMsg(f"{SERVICE_DISPLAY_NAME} stopped")

    def _shutdown(self):
        self._stop_flag.set()
        if self._thread:
            self._thread.join(timeout=30)


def handle_command_line() -> None:
    if IMPORT_ERROR:
        raise RuntimeError("pywin32 is required to manage the Windows Service") from IMPORT_ERROR
    win32serviceutil.HandleCommandLine(AmpAutoShutdownService)


def run_service() -> None:
    if IMPORT_ERROR:
        raise RuntimeError("pywin32 is required to run the Windows Service") from IMPORT_ERROR
    servicemanager.Initialize()
    servicemanager.PrepareToHostSingle(AmpAutoShutdownService)
    servicemanager.StartServiceCtrlDispatcher()


__all__ = [
    "AmpAutoShutdownService",
    "handle_command_line",
    "run_service",
    "SERVICE_NAME",
]
