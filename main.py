import ctypes
import os
import sys

from PyQt6.QtCore import QSharedMemory, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox, QStyle

from mountdock.config_manager import ConfigManager
from mountdock.i18n import tr
from mountdock.rclone_engine import RcloneEngine
from mountdock.rclone_updater import RcloneUpdater
from mountdock.ui_components import (
    DriveCardWidget,
    DriveSettingsDialog,
    GlobalSettingsDialog,
    LDriveMainWindow,
    LDriveTrayIcon,
    RcloneConfigDialog,
    RcloneUpdateDialog,
    RcloneUpdateWorker,
)
from mountdock.watcher import LDriveWatcher


class LDriveApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setApplicationName("MountDock")

        icon_path = LDriveMainWindow.resource_path(os.path.join("assets", "icon.ico"))
        if os.path.exists(icon_path):
            self.app.setWindowIcon(QIcon(icon_path))
        self.is_admin = self._is_running_as_admin()
        self.started_from_startup = "--startup" in sys.argv

        self.config = ConfigManager()
        self.lang = self.config.get("language", "en")
        self.shared_memory = None
        if self.config.get("single_instance", True) and not self._acquire_single_instance():
            QMessageBox.information(None, "MountDock", tr(self.lang, "already_running"))
            raise SystemExit(0)

        self.engine = RcloneEngine(
            self.config.resolve_rclone_path(),
            self.config.resolve_rclone_conf_path(),
        )
        self.rclone_updater = RcloneUpdater()
        self.config.check_and_fix_startup()
        self.window = LDriveMainWindow(self.lang)

        self.default_icon = (
            self.app.windowIcon()
            if not self.app.windowIcon().isNull()
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

        self.tray = LDriveTrayIcon(self.default_icon, self.lang)
        self.tray.show()
        self.watchers = {}
        self.remote_cache = []
        self._active_rclone_worker = None

        self._wire_signals()

        current_theme = self.config.get("theme", "light")
        self.window._apply_styles(current_theme)
        self._refresh_remote_cache()
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
        self.window.mount_all_requested.connect(self.handle_mount_all)
        self.window.unmount_all_requested.connect(self.handle_unmount_all)
        self.tray.show_requested.connect(self._show_window)
        self.tray.exit_requested.connect(self.exit_app)
        self.tray.toggle_mount_requested.connect(self.handle_toggle_mount)
        self.window.closeEvent = self._on_close_event

    def handle_mount_all(self):
        for profile in self.config.get_profiles():
            if profile["id"] not in self.watchers:
                self.handle_toggle_mount(profile["id"], True)

    def handle_unmount_all(self):
        for profile in list(self.config.get_profiles()):
            if profile["id"] in self.watchers:
                self.handle_toggle_mount(profile["id"], False)

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
            self.tray.showMessage("MountDock", tr(self.lang, "tray_running"))
            self.window.append_log(tr(self.lang, "window_hidden"))
            event.ignore()
            return

        self.exit_app()
        event.accept()

    def handle_settings(self):
        settings_data = dict(self.config.config)
        version_info = self._get_rclone_version_info()
        settings_data["rclone_version_status"] = version_info["label"]
        settings_data["rclone_update_available"] = version_info["update_available"]
        settings_data["rclone_update_tooltip"] = version_info["tooltip"]
        dialog = GlobalSettingsDialog(settings_data, self.lang, self.window)
        while True:
            if not dialog.exec():
                return
            data = dialog.get_data()
            if dialog.update_rclone_requested:
                dialog.update_rclone_requested = False
                self._handle_rclone_update(dialog, data)
                continue
            if dialog.open_rclone_config_requested:
                dialog.open_rclone_config_requested = False
                self._handle_rclone_config(data)
                continue

            for key, value in data.items():
                if key == "auto_start":
                    self.config.set_auto_start(value)
                else:
                    self.config.set(key, value)
            self.lang = data.get("language", self.lang)
            self.window.set_language(self.lang)
            self.tray.lang = self.lang
            self.engine.set_paths(
                self.config.resolve_rclone_path(data["rclone_path"]),
                self.config.resolve_rclone_conf_path(data["rclone_conf_path"]),
            )
            self._refresh_remote_cache()
            self.window.append_log(tr(self.lang, "settings_saved"))
            self._setup_dashboards()
            return

    def _setup_dashboards(self):
        self.window.clear_cards()
        profiles = self.config.get_profiles()
        active_count = len(self.watchers)

        if not profiles:
            self.window.show_empty_state()
            self.window.set_bulk_buttons_enabled(False, False)
            self.window.update_overview(0, active_count, self.config.get("theme", "light"))
            return

        for profile in profiles:
            card = DriveCardWidget(profile, self.lang)
            card.toggle_requested.connect(self.handle_toggle_mount)
            card.edit_requested.connect(self.handle_edit_drive)
            card.delete_requested.connect(self.handle_delete_drive)
            if profile["id"] in self.watchers:
                card.set_status("Connected")
            self.window.add_card(card)

        self.window.set_bulk_buttons_enabled(active_count < len(profiles), active_count > 0)
        self.window.update_overview(len(profiles), active_count, self.config.get("theme", "light"))
        self._refresh_tray_profiles(profiles)

    def _refresh_tray_profiles(self, profiles=None):
        if profiles is None:
            profiles = self.config.get_profiles()
        self.tray.lang = self.lang
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
        profiles = self.config.get_profiles()
        used_letters = [p.get("letter", "") for p in profiles]
        used_remotes = [p.get("remote", "") for p in profiles]
        system_used_letters = self._get_system_used_drive_letters()
        dialog = DriveSettingsDialog(
            self._get_available_remotes(),
            self.lang,
            self.window,
            used_letters=used_letters,
            system_used_letters=system_used_letters,
            used_remotes=used_remotes,
        )
        if dialog.exec():
            self.config.add_profile(dialog.get_data())
            self._setup_dashboards()

    def handle_edit_drive(self, pid):
        profile = next((p for p in self.config.get_profiles() if p["id"] == pid), None)
        if not profile:
            return
        if pid in self.watchers:
            QMessageBox.warning(self.window, tr(self.lang, "error"), tr(self.lang, "stop_before_edit"))
            return

        profiles = self.config.get_profiles()
        used_letters = [p.get("letter", "") for p in profiles]
        used_remotes = [p.get("remote", "") for p in profiles]
        system_used_letters = self._get_system_used_drive_letters()
        dialog = DriveSettingsDialog(
            self._get_available_remotes(),
            self.lang,
            self.window,
            profile,
            used_letters=used_letters,
            system_used_letters=system_used_letters,
            used_remotes=used_remotes,
        )
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
                    tr(self.lang, "run_without_admin"),
                    tr(self.lang, "admin_mount_blocked"),
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
                self._refresh_tray_profiles()
            else:
                self.window.append_log(f"Mount Error: {self.engine.last_error}")
                QMessageBox.critical(self.window, tr(self.lang, "mount_failed"), f"Rclone Error:\n\n{self.engine.last_error}")
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
            self._refresh_tray_profiles()

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

    def _handle_rclone_update(self, dialog, data):
        try:
            current_path = self.config.resolve_rclone_path(data.get("rclone_path", ""))
            installed_version = self.rclone_updater.get_installed_version(current_path)
            latest_version = self.rclone_updater.get_latest_version()
            target_dir = self.config.get_rclone_target_dir(data.get("rclone_path", ""))

            if installed_version and not self.rclone_updater.is_update_available(installed_version, latest_version):
                QMessageBox.information(
                    self.window,
                    tr(self.lang, "rclone_update_title"),
                    tr(self.lang, "already_up_to_date", installed=installed_version, latest=latest_version),
                )
                info = self._get_rclone_version_info()
                dialog.set_rclone_version_status(info["label"], info["update_available"], info["tooltip"])
                return

            update_dialog = RcloneUpdateDialog(installed_version, latest_version, self.lang, self.window)
            worker = RcloneUpdateWorker(self.rclone_updater, target_dir, latest_version)
            self._active_rclone_worker = worker
            worker.progress_changed.connect(update_dialog.set_progress)
            worker.finished_with_result.connect(lambda result: self._on_rclone_update_finished(dialog, update_dialog, data, result))
            worker.failed.connect(lambda message: self._on_rclone_update_failed(dialog, update_dialog, message))
            worker.start()
            update_dialog.exec()
        except Exception as exc:
            self.window.append_log(f"rclone update failed: {exc}")
            QMessageBox.critical(self.window, tr(self.lang, "rclone_update_title"), str(exc))

    def _on_rclone_update_finished(self, dialog, update_dialog, data, result):
        installed = result["path"]
        relative_path = data.get("rclone_path", "").strip()
        if not relative_path:
            self.config.set("rclone_path", str(installed))
        self.engine.set_paths(
            self.config.resolve_rclone_path(str(installed)),
            self.config.resolve_rclone_conf_path(data.get("rclone_conf_path", "")),
        )

        if result.get("locked_fallback"):
            message = tr(self.lang, "rclone_locked", path=installed)
        else:
            message = tr(self.lang, "rclone_updated", version=result["version"], path=installed)

        info = self._get_rclone_version_info()
        dialog.set_rclone_version_status(info["label"], info["update_available"], info["tooltip"])
        update_dialog.mark_done(message)
        self.window.append_log(f"rclone updated: {installed}")
        self._active_rclone_worker = None

    def _on_rclone_update_failed(self, dialog, update_dialog, message):
        self.window.append_log(f"rclone update failed: {message}")
        update_dialog.mark_failed(message)
        self._active_rclone_worker = None

    def _handle_rclone_config(self, data):
        original_rclone_path = self.engine.rclone_path
        original_conf_path = self.engine.rclone_conf_path
        try:
            temp_rclone_path = self.config.resolve_rclone_path(data.get("rclone_path", ""))
            temp_conf_path = self.config.resolve_rclone_conf_path(data.get("rclone_conf_path", ""))
            self.engine.set_paths(temp_rclone_path, temp_conf_path)
            dialog = RcloneConfigDialog(self.engine, self.lang, self.window)
            dialog.exec()
            if dialog.config_changed:
                self._refresh_remote_cache(rclone_path=temp_rclone_path, conf_path=temp_conf_path)
                self.window.append_log(tr(self.lang, "rclone_config_refreshed"))
        finally:
            self.engine.set_paths(original_rclone_path, original_conf_path)

    def _get_rclone_version_info(self):
        current_path = self.config.resolve_rclone_path()
        installed_version = self.rclone_updater.get_installed_version(current_path)
        try:
            latest_version = self.rclone_updater.get_latest_version()
        except Exception:
            latest_version = "unknown"

        if installed_version and latest_version != "unknown":
            if self.rclone_updater.is_update_available(installed_version, latest_version):
                return {
                    "label": tr(self.lang, "rclone_update_available", version=installed_version),
                    "update_available": True,
                    "tooltip": tr(self.lang, "tooltip_update_available", installed=installed_version, latest=latest_version),
                }
            return {
                "label": tr(self.lang, "rclone_latest", version=installed_version),
                "update_available": False,
                "tooltip": tr(self.lang, "tooltip_latest", version=installed_version),
            }
        if installed_version:
            return {
                "label": tr(self.lang, "rclone_update_available", version=installed_version),
                "update_available": False,
                "tooltip": "Could not verify latest version",
            }
        return {
            "label": tr(self.lang, "rclone_not_detected"),
            "update_available": True,
            "tooltip": tr(self.lang, "tooltip_not_detected"),
        }

    def _refresh_remote_cache(self, rclone_path=None, conf_path=None):
        active_rclone_path = rclone_path or self.engine.rclone_path
        active_conf_path = conf_path if conf_path is not None else self.engine.rclone_conf_path
        original_rclone_path = self.engine.rclone_path
        original_conf_path = self.engine.rclone_conf_path

        try:
            self.engine.set_paths(active_rclone_path, active_conf_path)
            parsed = [item.get("name") for item in self.config.parse_rclone_conf(active_conf_path) if item.get("name")]
            listed = self.engine.get_remotes()
        finally:
            self.engine.set_paths(original_rclone_path, original_conf_path)

        merged = []
        for name in parsed + listed:
            if name and name not in merged:
                merged.append(name)
        self.remote_cache = merged
        if merged:
            self.window.append_log(tr(self.lang, "loaded_remotes", count=len(merged)))
        else:
            self.window.append_log(tr(self.lang, "no_remotes"))

    def _get_available_remotes(self):
        if self.remote_cache:
            return self.remote_cache
        self._refresh_remote_cache()
        return self.remote_cache

    def _get_system_used_drive_letters(self):
        used = set()
        try:
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for i in range(26):
                if bitmask & (1 << i):
                    used.add(chr(ord('A') + i))
        except Exception:
            pass
        return sorted(used)

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
