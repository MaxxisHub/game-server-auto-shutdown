"""PySide6 GUI for configuring AMP Auto Shutdown."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from PySide6 import QtCore, QtWidgets

from amp_autoshutdown.api_amp import AMPClient, AMPAPIError
from amp_autoshutdown.config import Config, ConfigManager, LOG_DIR, MaintenanceWindow
from amp_autoshutdown_gui import service_control

LOGGER = logging.getLogger(__name__)


class LogViewerDialog(QtWidgets.QDialog):
    def __init__(self, log_path: Path, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.log_path = log_path
        self.setWindowTitle("Service Logs")
        self.resize(800, 400)
        layout = QtWidgets.QVBoxLayout(self)
        self.text_edit = QtWidgets.QPlainTextEdit(self)
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)
        btn_refresh = QtWidgets.QPushButton("Refresh", self)
        btn_refresh.clicked.connect(self.load_content)
        layout.addWidget(btn_refresh)
        self.load_content()

    def load_content(self) -> None:
        if not self.log_path.exists():
            self.text_edit.setPlainText("Log file not found yet. Trigger the service to generate logs.")
            return
        try:
            with self.log_path.open("r", encoding="utf-8", errors="ignore") as handle:
                all_text = handle.read()
        except OSError as exc:
            self.text_edit.setPlainText(f"Failed to read log file: {exc}")
            return
        self.text_edit.setPlainText(all_text)
        self.text_edit.verticalScrollBar().setValue(self.text_edit.verticalScrollBar().maximum())


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AMP Auto Shutdown Manager")
        self.resize(900, 700)

        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()
        self.api_key_value = self.config_manager.get_api_key(self.config.api_key_alias) or ""

        self._build_ui()
        self._apply_config()
        self._refresh_service_status()

        self.status_timer = QtCore.QTimer(self)
        self.status_timer.timeout.connect(self._refresh_service_status)
        self.status_timer.start(15000)

    # UI construction --------------------------------------------------
    def _build_ui(self) -> None:
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        if not service_control.is_user_admin():
            notice = QtWidgets.QLabel(
                "WARNING: Administrator privileges are required to install or manage the Windows Service.",
                self,
            )
            notice.setStyleSheet("color: #b58900; font-weight: bold;")
            layout.addWidget(notice)

        layout.addWidget(self._build_connection_box())
        layout.addWidget(self._build_monitor_box())
        layout.addWidget(self._build_instances_box())
        layout.addWidget(self._build_maintenance_box())
        layout.addWidget(self._build_service_box())
        layout.addStretch(1)

    def _build_connection_box(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("AMP Connection", self)
        grid = QtWidgets.QGridLayout(box)

        self.base_url_input = QtWidgets.QLineEdit(box)
        self.api_key_input = QtWidgets.QLineEdit(box)
        self.api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.verify_ssl_checkbox = QtWidgets.QCheckBox("Verify TLS certificates", box)
        self.verify_ssl_checkbox.setChecked(True)

        btn_test = QtWidgets.QPushButton("Test Connection", box)
        btn_test.clicked.connect(self._on_test_connection)
        btn_fetch = QtWidgets.QPushButton("Fetch Instances", box)
        btn_fetch.clicked.connect(self._on_fetch_instances)

        grid.addWidget(QtWidgets.QLabel("AMP Base URL"), 0, 0)
        grid.addWidget(self.base_url_input, 0, 1, 1, 3)
        grid.addWidget(QtWidgets.QLabel("API Key"), 1, 0)
        grid.addWidget(self.api_key_input, 1, 1, 1, 3)
        grid.addWidget(self.verify_ssl_checkbox, 2, 0, 1, 2)
        grid.addWidget(btn_test, 2, 2)
        grid.addWidget(btn_fetch, 2, 3)
        return box

    def _build_monitor_box(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Monitoring Settings", self)
        grid = QtWidgets.QGridLayout(box)

        self.poll_interval_spin = QtWidgets.QSpinBox(box)
        self.poll_interval_spin.setRange(5, 3600)
        self.poll_interval_spin.setSuffix(" s")

        self.idle_delay_spin = QtWidgets.QSpinBox(box)
        self.idle_delay_spin.setRange(1, 240)
        self.idle_delay_spin.setSuffix(" min")

        self.global_threshold_spin = QtWidgets.QSpinBox(box)
        self.global_threshold_spin.setRange(0, 500)

        self.dry_run_checkbox = QtWidgets.QCheckBox("Dry-run mode (log only)", box)

        grid.addWidget(QtWidgets.QLabel("Poll Interval"), 0, 0)
        grid.addWidget(self.poll_interval_spin, 0, 1)
        grid.addWidget(QtWidgets.QLabel("Idle Delay"), 0, 2)
        grid.addWidget(self.idle_delay_spin, 0, 3)
        grid.addWidget(QtWidgets.QLabel("Global Player Threshold"), 1, 0)
        grid.addWidget(self.global_threshold_spin, 1, 1)
        grid.addWidget(self.dry_run_checkbox, 1, 2, 1, 2)
        return box

    def _build_instances_box(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Instances", self)
        vbox = QtWidgets.QVBoxLayout(box)

        self.instances_table = QtWidgets.QTableWidget(0, 3, box)
        self.instances_table.setHorizontalHeaderLabels(["Monitor", "Instance", "Threshold"])
        self.instances_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.instances_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        vbox.addWidget(self.instances_table)
        return box

    def _build_maintenance_box(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Maintenance Windows", self)
        vbox = QtWidgets.QVBoxLayout(box)

        self.maintenance_table = QtWidgets.QTableWidget(0, 3, box)
        self.maintenance_table.setHorizontalHeaderLabels(["Days (e.g. Mon,Wed,*)", "Start (HH:MM)", "End (HH:MM)"])
        self.maintenance_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        vbox.addWidget(self.maintenance_table)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_add = QtWidgets.QPushButton("Add", box)
        btn_remove = QtWidgets.QPushButton("Remove", box)
        btn_add.clicked.connect(self._on_add_maintenance)
        btn_remove.clicked.connect(self._on_remove_maintenance)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_remove)
        btn_layout.addStretch(1)
        vbox.addLayout(btn_layout)
        return box

    def _build_service_box(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Windows Service", self)
        vbox = QtWidgets.QVBoxLayout(box)

        self.service_status_label = QtWidgets.QLabel("Status: Unknown", box)
        vbox.addWidget(self.service_status_label)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_install = QtWidgets.QPushButton("Install Service", box)
        btn_start = QtWidgets.QPushButton("Start Service", box)
        btn_stop = QtWidgets.QPushButton("Stop Service", box)
        btn_uninstall = QtWidgets.QPushButton("Uninstall Service", box)
        btn_view_logs = QtWidgets.QPushButton("View Logs", box)

        btn_install.clicked.connect(self._on_install_service)
        btn_start.clicked.connect(self._on_start_service)
        btn_stop.clicked.connect(self._on_stop_service)
        btn_uninstall.clicked.connect(self._on_uninstall_service)
        btn_view_logs.clicked.connect(self._on_view_logs)

        btn_layout.addWidget(btn_install)
        btn_layout.addWidget(btn_start)
        btn_layout.addWidget(btn_stop)
        btn_layout.addWidget(btn_uninstall)
        btn_layout.addWidget(btn_view_logs)
        vbox.addLayout(btn_layout)

        btn_save = QtWidgets.QPushButton("Save Settings", box)
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._on_save_settings)
        vbox.addWidget(btn_save)

        return box

    # Configuration handling ------------------------------------------
    def _apply_config(self) -> None:
        self.base_url_input.setText(self.config.amp_base_url)
        self.api_key_input.setText(self.api_key_value)
        self.verify_ssl_checkbox.setChecked(self.config.verify_ssl)
        self.poll_interval_spin.setValue(self.config.poll_interval_seconds)
        self.idle_delay_spin.setValue(self.config.idle_delay_minutes)
        self.global_threshold_spin.setValue(self.config.global_player_threshold)
        self.dry_run_checkbox.setChecked(self.config.dry_run)

        self._populate_instances_table(self.config.selected_instances, self.config.per_instance_thresholds)
        self._populate_maintenance_table(self.config.maintenance_windows)

    def _collect_config_from_ui(self) -> Config:
        cfg = Config()
        cfg.amp_base_url = self.base_url_input.text().strip()
        cfg.api_key_alias = self.config.api_key_alias
        cfg.poll_interval_seconds = self.poll_interval_spin.value()
        cfg.idle_delay_minutes = self.idle_delay_spin.value()
        cfg.global_player_threshold = self.global_threshold_spin.value()
        cfg.dry_run = self.dry_run_checkbox.isChecked()
        cfg.verify_ssl = self.verify_ssl_checkbox.isChecked()

        selected_instances: List[str] = []
        per_instance_thresholds: Dict[str, int] = {}
        for row in range(self.instances_table.rowCount()):
            name_item = self.instances_table.item(row, 1)
            if name_item is None:
                continue
            instance_name = name_item.data(QtCore.Qt.UserRole) or name_item.text()
            checkbox_item = self.instances_table.item(row, 0)
            if checkbox_item and checkbox_item.checkState() == QtCore.Qt.Checked:
                selected_instances.append(instance_name)
            spin_widget = self.instances_table.cellWidget(row, 2)
            if isinstance(spin_widget, QtWidgets.QSpinBox):
                per_instance_thresholds[instance_name] = spin_widget.value()
        cfg.selected_instances = selected_instances
        cfg.per_instance_thresholds = per_instance_thresholds

        maintenance_windows: List[MaintenanceWindow] = []
        for row in range(self.maintenance_table.rowCount()):
            days_item = self.maintenance_table.item(row, 0)
            start_item = self.maintenance_table.item(row, 1)
            end_item = self.maintenance_table.item(row, 2)
            if not days_item:
                continue
            days = [segment.strip().lower() for segment in days_item.text().split(',') if segment.strip()]
            maintenance_windows.append(
                MaintenanceWindow(
                    days=days or ["*"],
                    start=start_item.text().strip() if start_item else "00:00",
                    end=end_item.text().strip() if end_item else "00:00",
                )
            )
        cfg.maintenance_windows = maintenance_windows
        return cfg

    # Table helpers ----------------------------------------------------
    def _populate_instances_table(self, selected: List[str], thresholds: Dict[str, int]) -> None:
        self.instances_table.setRowCount(0)
        for name in selected:
            row = self.instances_table.rowCount()
            self.instances_table.insertRow(row)
            checkbox = QtWidgets.QTableWidgetItem()
            checkbox.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            checkbox.setCheckState(QtCore.Qt.Checked)
            self.instances_table.setItem(row, 0, checkbox)

            label = QtWidgets.QTableWidgetItem(name)
            label.setData(QtCore.Qt.UserRole, name)
            self.instances_table.setItem(row, 1, label)

            threshold = QtWidgets.QSpinBox(self.instances_table)
            threshold.setRange(0, 500)
            threshold.setValue(thresholds.get(name, self.config.global_player_threshold))
            self.instances_table.setCellWidget(row, 2, threshold)

    def _populate_maintenance_table(self, windows: List[MaintenanceWindow]) -> None:
        self.maintenance_table.setRowCount(0)
        for window in windows:
            row = self.maintenance_table.rowCount()
            self.maintenance_table.insertRow(row)
            self.maintenance_table.setItem(row, 0, QtWidgets.QTableWidgetItem(','.join(window.days)))
            self.maintenance_table.setItem(row, 1, QtWidgets.QTableWidgetItem(window.start))
            self.maintenance_table.setItem(row, 2, QtWidgets.QTableWidgetItem(window.end))

    # Button handlers --------------------------------------------------
    def _on_test_connection(self) -> None:
        client = self._client_from_ui()
        if not client:
            return
        if client.test_connection():
            QtWidgets.QMessageBox.information(self, "AMP", "Connection successful")
        else:
            QtWidgets.QMessageBox.warning(self, "AMP", "Connection failed. Check URL and API key.")

    def _on_fetch_instances(self) -> None:
        client = self._client_from_ui()
        if not client:
            return
        try:
            instances = client.list_instances()
        except AMPAPIError as exc:
            QtWidgets.QMessageBox.critical(self, "AMP", f"Failed to fetch instances: {exc}")
            return
        selected = set(self.config.selected_instances)
        thresholds = self.config.per_instance_thresholds.copy()
        self.instances_table.setRowCount(0)
        for entry in instances:
            name = str(entry.get("id") or entry.get("name") or entry)
            row = self.instances_table.rowCount()
            self.instances_table.insertRow(row)
            checkbox = QtWidgets.QTableWidgetItem()
            checkbox.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            checkbox.setCheckState(QtCore.Qt.Checked if (selected and name in selected) or not selected else QtCore.Qt.Unchecked)
            self.instances_table.setItem(row, 0, checkbox)
            label = QtWidgets.QTableWidgetItem(entry.get("name", name))
            label.setData(QtCore.Qt.UserRole, name)
            self.instances_table.setItem(row, 1, label)
            threshold_widget = QtWidgets.QSpinBox(self.instances_table)
            threshold_widget.setRange(0, 500)
            threshold_widget.setValue(thresholds.get(name, self.config.global_player_threshold))
            self.instances_table.setCellWidget(row, 2, threshold_widget)

    def _on_save_settings(self) -> None:
        new_config = self._collect_config_from_ui()
        api_key = self.api_key_input.text().strip()
        try:
            self.config_manager.save(new_config, api_key if api_key else None)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Save Failed", str(exc))
            return
        self.config = new_config
        self.api_key_value = api_key
        QtWidgets.QMessageBox.information(self, "Settings", "Configuration saved")

    def _on_install_service(self) -> None:
        self._run_service_action(service_control.install_service)

    def _on_start_service(self) -> None:
        self._run_service_action(service_control.start_service)

    def _on_stop_service(self) -> None:
        self._run_service_action(service_control.stop_service)

    def _on_uninstall_service(self) -> None:
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Uninstall Service",
            "This will stop the service and delete stored configuration. Continue?",
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return
        self._run_service_action(service_control.uninstall_service)
        self.config_manager.delete_storage()

    def _on_view_logs(self) -> None:
        log_path = LOG_DIR / "amp_autoshutdown.log"
        dialog = LogViewerDialog(log_path, self)
        dialog.exec()

    def _on_add_maintenance(self) -> None:
        row = self.maintenance_table.rowCount()
        self.maintenance_table.insertRow(row)
        self.maintenance_table.setItem(row, 0, QtWidgets.QTableWidgetItem("*"))
        self.maintenance_table.setItem(row, 1, QtWidgets.QTableWidgetItem("00:00"))
        self.maintenance_table.setItem(row, 2, QtWidgets.QTableWidgetItem("06:00"))

    def _on_remove_maintenance(self) -> None:
        selected = self.maintenance_table.currentRow()
        if selected >= 0:
            self.maintenance_table.removeRow(selected)

    # Helpers ----------------------------------------------------------
    def _run_service_action(self, func) -> None:
        try:
            if func is service_control.install_service:
                if getattr(sys, "frozen", False):
                    func(Path(sys.executable))
                else:
                    func(Path(sys.executable), extra_args="-m amp_autoshutdown --service")
            else:
                func()
        except PermissionError as exc:
            QtWidgets.QMessageBox.critical(self, "Permission Denied", str(exc))
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Error", str(exc))
        finally:
            self._refresh_service_status()

    def _refresh_service_status(self) -> None:
        try:
            status = service_control.query_status()
        except Exception as exc:
            status = f"Unavailable ({exc})"
        self.service_status_label.setText(f"Status: {status}")

    def _client_from_ui(self) -> Optional[AMPClient]:
        base_url = self.base_url_input.text().strip()
        api_key = self.api_key_input.text().strip()
        if not base_url or not api_key:
            QtWidgets.QMessageBox.warning(self, "Input", "Provide both base URL and API key.")
            return None
        try:
            return AMPClient(base_url, api_key, verify_ssl=self.verify_ssl_checkbox.isChecked())
        except ValueError as exc:
            QtWidgets.QMessageBox.critical(self, "Input", str(exc))
            return None


def run_gui() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
