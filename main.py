import ctypes
import os
import sys

from PyQt6.QtCore import QSharedMemory, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox, QStyle

from ldrive.config_manager import ConfigManager
from ldrive.rclone_engine import RcloneEngine
from ldrive.ui_components import (
    DriveCardWidget,
    DriveSettingsDialog,
    GlobalSettingsDialog,
    LDriveMainWindow,
    LDriveTrayIcon,
)
from ldrive.watcher import LDriveWatcher


class LDriveApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setApplicationName("L-Drive")
        self.is_admin = self._is_running_as_admin()
        self.started_from_startup = "--startup" in sys.argv

        self.config = ConfigManager()
        self.shared_memory = None
        if self.config.get("single_instance", True) and not self._acquire_single_instance():
            QMessageBox.information(None, "L-Drive", "L-Drive is already running.")
            raise SystemExit(0)

        self.engine = RcloneEngine(
            self.config.resolve_rclone_path(),
            self.config.resolve_rclone_conf_path(),
        )
        self.config.check_and_fix_startup()
        self.window = LDriveMainWindow()

        icon_path = LDriveMainWindow.resource_path(os.path.join("assets", "icon.ico"))
        self.default_icon = (
            QIcon(icon_path)
            if os.path.exists(icon_path)
            else self.app.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon)
        )
        self.window.setWindowIcon(self.default_icon)

        if self.is_admin:
            admin_message = (
                "관리자 권한으로 실행 중입니다. 이 상태에서 만든 드라이브는 일반 Windows 탐색기에서 "
                "보이지 않을 수 있습니다. 일반 권한으로 다시 실행하세요."
            )
            self.window.set_warning_banner(admin_message)
            self.window.append_log(f"[Warning] {admin_message}")

        self.tray = LDriveTrayIcon(self.default_icon)
        self.tray.show()
        self.watchers = {}

        self._wire_signals()

        current_theme = self.config.get("theme", "light")
        self.window._apply_styles(current_theme)
        self._setup_dashboards()

        if self.config.get("mount_on_launch"):
            self._mount_startup_profiles()

        should_start_hidden = self.config.get("start_minimized") or self.started_from_startup
        if should_start_hidden:
            self.window.hide()
        else:
            self.window.show()

    def _wire_signals(self):
        self.window.add_requested.connect(self.handle_add_drive)
        self.window.settings_requested.connect(self.handle_settings)
        self.window.theme_toggle_requested.connect(self.handle_theme_toggle)
        self.tray.show_requested.connect(self._show_window)
        self.tray.exit_requested.connect(self.exit_app)
        self.tray.toggle_mount_requested.connect(self.handle_toggle_mount)
        self.window.closeEvent = self._on_close_event

    def handle_theme_toggle(self):
        theme = "dark" if self.config.get("theme") == "light" else "light"
        self.config.set("theme", theme)
        self.window._apply_styles(theme)
        self.window.update_overview(len(self.config.get_profiles()), len(self.watchers), theme)
        if self.is_admin:
            self.window.set_warning_banner(
                "관리자 권한으로 실행 중입니다. 일반 Windows 탐색기 호환을 위해 일반 권한으로 다시 실행하세요."
            )

    def _show_window(self):
        self.window.showNormal()
        self.window.setWindowState(
            self.window.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive
        )
        self.window.raise_()
        self.window.activateWindow()

    def _on_close_event(self, event):
        if self.config.get("minimize_to_tray", True):
            self.window.hide()
            self.tray.showMessage("L-Drive", "L-Drive is still running in the system tray.")
            self.window.append_log("Window hidden to tray.")
            event.ignore()
            return

        self.exit_app()
        event.accept()

    def handle_settings(self):
        dialog = GlobalSettingsDialog(self.config.config, self.window)
        if dialog.exec():
            data = dialog.get_data()
            for key, value in data.items():
                if key == "auto_start":
                    self.config.set_auto_start(value)
                else:
                    self.config.set(key, value)
            self.engine.set_paths(
                self.config.resolve_rclone_path(data["rclone_path"]),
                self.config.resolve_rclone_conf_path(data["rclone_conf_path"]),
            )
            self.window.append_log("Settings saved.")
            self.window.update_overview(
                len(self.config.get_profiles()),
                len(self.watchers),
                self.config.get("theme", "light"),
            )

    def _setup_dashboards(self):
        self.window.clear_cards()
        profiles = self.config.get_profiles()
        active_count = len(self.watchers)

        if not profiles:
            self.window.show_empty_state()
            self.window.update_overview(0, active_count, self.config.get("theme", "light"))
            return

        for profile in profiles:
            card = DriveCardWidget(profile)
            card.toggle_requested.connect(self.handle_toggle_mount)
            card.edit_requested.connect(self.handle_edit_drive)
            card.delete_requested.connect(self.handle_delete_drive)
            if profile["id"] in self.watchers:
                card.set_status("Connected")
            self.window.add_card(card)

        self.window.update_overview(len(profiles), active_count, self.config.get("theme", "light"))
        self.tray.set_profiles([
            {
                "id": p["id"],
                "letter": p["letter"],
                "remote": p["remote"],
                "root_folder": p.get("root_folder", "/"),
                "mounted": p["id"] in self.watchers,
            }
            for p in profiles
        ])

    def handle_add_drive(self):
        dialog = DriveSettingsDialog(self.engine.get_remotes(), self.window)
        if dialog.exec():
            self.config.add_profile(dialog.get_data())
            self._setup_dashboards()

    def handle_edit_drive(self, pid):
        profile = next((p for p in self.config.get_profiles() if p["id"] == pid), None)
        if not profile:
            return
        if pid in self.watchers:
            QMessageBox.warning(self.window, "Error", "Stop drive before editing.")
            return

        dialog = DriveSettingsDialog(self.engine.get_remotes(), self.window, profile)
        if dialog.exec():
            self.config.update_profile(pid, dialog.get_data())
            self._setup_dashboards()

    def handle_delete_drive(self, pid):
        if pid in self.watchers:
            self.handle_toggle_mount(pid, False)
        self.config.delete_profile(pid)
        self._setup_dashboards()

    def handle_toggle_mount(self, pid, should_start):
        profile = next((p for p in self.config.get_profiles() if p["id"] == pid), None)
        card = self._find_card(pid)
        if not profile or not card:
            return

        if should_start:
            if self.is_admin:
                self.window.append_log("[Blocked] 관리자 권한 실행 중이라 마운트를 차단했습니다.")
                QMessageBox.warning(
                    self.window,
                    "Run Without Administrator",
                    "관리자 권한으로 실행 중이면 마운트 드라이브가 일반 Windows 탐색기에서 보이지 않을 수 있습니다.\n\n"
                    "L-Drive를 일반 권한으로 다시 실행한 뒤 마운트하세요.",
                )
                card.set_status("Admin Block")
                return

            process = self.engine.mount(
                profile["remote"],
                profile["letter"],
                profile["vfs_mode"],
                profile["root_folder"],
                profile.get("custom_args", profile.get("extra_flags", "")),
                profile.get("volname", ""),
                profile.get("cache_dir", ""),
            )
            if process:
                watcher = LDriveWatcher(
                    self.engine,
                    profile["remote"],
                    profile["letter"],
                    profile["vfs_mode"],
                    profile["root_folder"],
                    profile.get("custom_args", profile.get("extra_flags", "")),
                    profile.get("volname", ""),
                    profile.get("cache_dir", ""),
                )
                watcher.status_changed.connect(card.set_status)
                watcher.log_emitted.connect(self.window.append_log)
                watcher.start()
                self.watchers[pid] = watcher
                self.window.update_overview(
                    len(self.config.get_profiles()),
                    len(self.watchers),
                    self.config.get("theme", "light"),
                )
            else:
                self.window.append_log(f"Mount Error: {self.engine.last_error}")
                QMessageBox.critical(self.window, "Mount Failed", f"Rclone Error:\n\n{self.engine.last_error}")
        else:
            if pid in self.watchers:
                self.watchers[pid].stop()
                del self.watchers[pid]
            self.engine.unmount(profile["letter"])
            card.set_status("Disconnected")
            self.window.update_overview(
                len(self.config.get_profiles()),
                len(self.watchers),
                self.config.get("theme", "light"),
            )

    def _find_card(self, pid):
        for i in range(self.window.card_layout.count()):
            widget = self.window.card_layout.itemAt(i).widget()
            if isinstance(widget, DriveCardWidget) and widget.profile["id"] == pid:
                return widget
        return None

    def _mount_startup_profiles(self):
        for profile in self.config.get_profiles():
            if profile.get("auto_mount"):
                self.handle_toggle_mount(profile["id"], True)

    def _acquire_single_instance(self):
        self.shared_memory = QSharedMemory("LDrive_SingleInstance")
        if self.shared_memory.attach():
            return False
        return self.shared_memory.create(1)

    def exit_app(self):
        for watcher in self.watchers.values():
            watcher.stop()
        self.engine.kill_all_mounts()
        self.app.quit()

    def _is_running_as_admin(self):
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False


if __name__ == "__main__":
    LDriveApp().app.exec()
