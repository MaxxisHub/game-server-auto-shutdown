# AMP Auto Shutdown

[![CI](https://github.com/your-org/amp-auto-shutdown/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/amp-auto-shutdown/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

AMP Auto Shutdown installs a Windows service and desktop management app that monitor CubeCoders AMP game server instances. When all monitored instances remain below their player thresholds for the configured idle window, the service powers off the host. The bundled GUI makes it easy to install or remove the service, tune thresholds, review logs, and manage AMP credentials.

![Main window screenshot](docs/screenshots/main-window.png)
![Service status screenshot](docs/screenshots/service-status.png)

## Features
- Windows service implemented with pywin32 that survives reboots and logs to rotating files.
- PySide6 GUI for configuring AMP connection details, shutdown thresholds, dry-run mode, and maintenance windows.
- Secure API key storage via Windows Credential Manager (keyring) when available.
- Resilient AMP polling with timeouts, retries, and maintenance window suppression to avoid unwanted shutdowns.
- One-click service management: install, start, stop, uninstall, and log viewer.
- PyInstaller build script to ship a single EXE that installs the service on first launch and opens the GUI on subsequent runs.

## Architecture
`mermaid
graph TD
    Launcher[Single EXE Launcher] -->|--service| ServiceRunner[AmpAutoShutdownService]
    Launcher -->|GUI| GUI[PySide6 Manager]
    ServiceRunner --> Monitor
    Monitor --> AMPClient
    Monitor --> ConfigManager
    GUI --> ConfigManager
    GUI --> ServiceControl
    ServiceControl --> WindowsServiceManager
    AMPClient --> AMPAPI[(AMP REST API)]
    ConfigManager --> ConfigToml[config.toml + keyring]
    Monitor --> WindowsShutdown[/shutdown /s /t 0/]
`

## Prerequisites
- Windows 11 or Windows Server 2019/2022 with desktop experience.
- AMP instances reachable from the service host with a valid AMP API key.
- Python 3.11+ if you plan to run from source; otherwise download the packaged EXE.

## Quick Start (Packaged EXE)
1. Download AmpAutoShutdown.exe from the project releases page.
2. Run the EXE as an administrator the first time. The launcher installs the Windows service and opens the GUI.
3. In the GUI, set the AMP base URL, API key, and polling thresholds. Use **Test Connection** to verify AMP access.
4. Click **Fetch Instances** to populate available AMP instances, select the ones that should trigger shutdown, and adjust per-instance thresholds if required.
5. Configure optional maintenance windows and enable or disable dry-run mode.
6. Click **Save Settings**. The service immediately applies the new configuration.
7. Use **View Logs** to tail the rolling log file. When the monitored player counts stay at or below the configured thresholds for the idle delay, the host executes shutdown /s /t 0.

### Subsequent Launches
- Running the EXE again simply opens the GUI without touching the installed service.
- Use the GUI buttons to start, stop, or uninstall the service at any time.

## Configuration File
Settings are stored in %ProgramData%\AmpAutoShutdown\config.toml. An example with all options is available as config.example.toml.

- mp_base_url: Base URL of the AMP controller, e.g. https://amp.local:8080.
- poll_interval_seconds: Polling cadence (default 30 seconds).
- idle_delay_minutes: Required idle duration before shutdown (default 10 minutes).
- global_player_threshold: Player count that counts as active (default 0).
- per_instance_thresholds: Optional overrides keyed by instance ID.
- maintenance_windows: List of day/start/end entries where shutdown is suppressed.
- dry_run: When true, logs intent but skips the shutdown command.
- erify_ssl: Toggle TLS certificate verification for the AMP API.

API keys are stored in the Windows Credential Manager through keyring. If keyring is unavailable, the GUI warns you and the API key can be stored in plain text at your discretion.

## Service Behaviour
- The service starts automatically at boot, reloads the configuration on every polling cycle, and tolerates transient AMP API failures without shutting down the host.
- Maintenance windows are evaluated in local time and can span midnight.
- When all monitored instances stay at or below their thresholds for the idle delay, the service runs shutdown /s /t 0. Enable **Dry-run** to verify settings without rebooting the host.

## Building From Source
`powershell
# Clone and install dependencies
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]

# Run tests
pytest

# Build single-file EXE
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
`
The build script bundles the service and GUI into dist\AmpAutoShutdown.exe using PyInstaller.

## Manual Service Commands (Development)
`powershell
# Install using Python interpreter (development only)
python -m amp_autoshutdown --install-service
python -m amp_autoshutdown --start-service
python -m amp_autoshutdown --stop-service
python -m amp_autoshutdown --uninstall-service
`

## Logs
Rolling logs live at %ProgramData%\AmpAutoShutdown\logs\amp_autoshutdown.log. The GUI **View Logs** button opens a simple tail view, or you can open the file in your editor of choice.

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines and local setup notes. All contributors must abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

## License
Released under the [MIT License](LICENSE).
