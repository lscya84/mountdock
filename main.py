import ctypes
import os
import sys
import webbrowser
from pathlib import Path

from PyQt6.QtCore import QFileSystemWatcher, QSharedMemory, QTimer, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox, QStyle

from mountdock import __version__
from mountdock.app_updater import AppUpdater
from mountdock.config_manager import ConfigManager
from mountdock.google_auth import GoogleAuthManager
from mountdock.i18n import tr
from mountdock.rclone_engine import RcloneEngine
from mountdock.rclone_updater import RcloneUpdater
from mountdock.sync_service import SyncService, SyncServiceError
from mountdock.ui_components import (
    AppUpdateDialog,
    AppUpdateWorker,
    DriveCardWidget,
    DriveSettingsDialog,
    GlobalSettingsDialog,
    GoogleSyncDialog,
    LDriveMainWindow,
    LDriveTrayIcon,
    PassphraseDialog,
    RcloneConfigDialog,
    RcloneUpdateDialog,
    RcloneUpdateWorker,
)
from mountdock.watcher import LDriveWatcher
from mountdock.windows_drive_icons import apply_drive_icon, clear_drive_icon


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
        self.app_updater = AppUpdater()
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
        self.remote_details = []
        self._active_rclone_worker = None
        self._active_app_update_worker = None
        self._conf_file_watcher = QFileSystemWatcher()
        self._conf_file_watcher.fileChanged.connect(self._on_rclone_conf_changed)
        self._auto_sync_timer = QTimer()
        self._auto_sync_timer.setSingleShot(True)
        self._auto_sync_timer.timeout.connect(self._run_auto_google_sync)
        self._last_conf_mtime = None

        self._wire_signals()

        current_theme = self.config.get("theme", "light")
        self.window._apply_styles(current_theme)
        self._refresh_remote_cache()
        self._refresh_rclone_conf_watch()
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
        app_version_info = self._get_app_version_info()
        settings_data["rclone_version_status"] = version_info["label"]
        settings_data["rclone_update_available"] = version_info["update_available"]
        settings_data["rclone_update_tooltip"] = version_info["tooltip"]
        settings_data["app_version_status"] = app_version_info["label"]
        settings_data["app_update_available"] = app_version_info["update_available"]
        settings_data["app_update_tooltip"] = app_version_info["tooltip"]
        settings_data["app_download_url"] = app_version_info["download_url"]
        settings_data["app_installer_url"] = app_version_info["installer_url"]
        settings_data["app_installer_name"] = app_version_info["installer_name"]
        dialog = GlobalSettingsDialog(settings_data, self.lang, self.window)
        dialog.set_app_installer_url(app_version_info["installer_url"])
        self._update_google_sync_dialog_state(dialog)
        while True:
            if not dialog.exec():
                return
            if dialog.check_app_update_requested:
                dialog.check_app_update_requested = False
                self._handle_app_update_check(dialog)
                continue
            if dialog.install_app_update_requested:
                dialog.install_app_update_requested = False
                self._handle_app_update_install(dialog)
                continue
            if dialog.open_app_download_requested:
                dialog.open_app_download_requested = False
                self._open_app_download_page(dialog.config_data.get("app_download_url") or self.app_updater.get_releases_url())
                continue
            data = dialog.get_data()
            if dialog.update_rclone_requested:
                dialog.update_rclone_requested = False
                self._handle_rclone_update(dialog, data)
                continue
            if dialog.open_rclone_config_requested:
                dialog.open_rclone_config_requested = False
                self._handle_rclone_config(data)
                continue
            if dialog.open_google_sync_requested:
                dialog.open_google_sync_requested = False
                self._handle_google_sync_dialog(dialog, data)
                continue

            try:
                self._persist_rclone_conf(data)
            except Exception as exc:
                QMessageBox.warning(self.window, tr(self.lang, "error"), str(exc))
                continue

            self._apply_settings_data(data, refresh_remotes=True)
            self.window.append_log(tr(self.lang, "settings_saved"))
            self._setup_dashboards()
            return

    def _apply_settings_data(self, data, refresh_remotes=True):
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
        self._refresh_rclone_conf_watch()
        if refresh_remotes:
            self._refresh_remote_cache()

    def _build_sync_service(self, data=None):
        secret_path = self.config.resolve_google_client_secret_path((data or {}).get("google_client_secret_path"))
        token_path = self.config.resolve_google_token_path()
        auth_manager = GoogleAuthManager(secret_path, token_path)
        return SyncService(self.config, auth_manager)

    def _persist_google_client_secret(self, data) -> str:
        raw = (data.get("google_client_secret_path", "") or "").strip()
        if not raw:
            return self.config.resolve_google_client_secret_path()

        managed = Path(self.config.get_google_client_secret_store_path()).resolve()
        resolved = Path(self.config.resolve_google_client_secret_path(raw)).resolve()

        if resolved == managed and managed.exists():
            relative = os.path.relpath(managed, self.config.get_app_dir())
            data["google_client_secret_path"] = relative
            self.config.set("google_client_secret_path", relative)
            return str(managed)

        imported = self.config.import_google_client_secret(str(resolved))
        relative = os.path.relpath(imported, self.config.get_app_dir())
        data["google_client_secret_path"] = relative
        self.window.append_log(f"Imported Google OAuth client JSON to {imported}")
        return imported

    def _persist_rclone_conf(self, data) -> str:
        raw = (data.get("rclone_conf_path", "") or "").strip()
        if not raw:
            return self.config.resolve_rclone_conf_path()

        managed = Path(self.config.get_rclone_conf_store_path()).resolve()
        resolved = Path(self.config.resolve_rclone_conf_path(raw)).resolve()

        if resolved == managed and managed.exists():
            relative = os.path.relpath(managed, self.config.get_app_dir())
            data["rclone_conf_path"] = relative
            self.config.set("rclone_conf_path", relative)
            return str(managed)

        imported = self.config.import_rclone_conf(str(resolved))
        relative = os.path.relpath(imported, self.config.get_app_dir())
        data["rclone_conf_path"] = relative
        self.window.append_log(f"Imported rclone.conf to {imported}")
        self._refresh_rclone_conf_watch()
        return imported

    def _refresh_rclone_conf_watch(self):
        try:
            watched = self._conf_file_watcher.files()
            if watched:
                self._conf_file_watcher.removePaths(watched)
        except Exception:
            pass

        conf_path = (self.config.resolve_rclone_conf_path() or "").strip()
        if not conf_path:
            self._last_conf_mtime = None
            return

        path = Path(conf_path)
        if path.exists():
            try:
                self._conf_file_watcher.addPath(str(path))
                self._last_conf_mtime = path.stat().st_mtime_ns
            except Exception:
                self._last_conf_mtime = None
        else:
            self._last_conf_mtime = None

    def _on_rclone_conf_changed(self, path: str):
        conf_path = Path(path)
        if conf_path.exists():
            try:
                current_mtime = conf_path.stat().st_mtime_ns
            except Exception:
                current_mtime = None
            if current_mtime is not None and current_mtime == self._last_conf_mtime:
                self._refresh_rclone_conf_watch()
                return
            self._last_conf_mtime = current_mtime

        self._refresh_rclone_conf_watch()
        self._refresh_remote_cache()

        if self._is_google_auto_sync_ready():
            self.window.append_log(tr(self.lang, "google_sync_auto_detected"))
            self._auto_sync_timer.start(15000)

    def _is_google_auto_sync_ready(self) -> bool:
        if not bool(self.config.get("google_sync_enabled", False)):
            return False

        try:
            service = self._build_sync_service()
            if not service.auth.has_cached_credentials():
                return False
            return bool(service.load_cached_passphrase())
        except Exception:
            return False

    def _run_auto_google_sync(self):
        if not self._is_google_auto_sync_ready():
            return

        try:
            service = self._build_sync_service()
            passphrase = service.load_cached_passphrase()
            if not passphrase:
                return
            service.backup_current_conf(passphrase, interactive=False)
            self.window.append_log(tr(self.lang, "google_sync_auto_backup_ok"))
        except SyncServiceError as exc:
            self.window.append_log(tr(self.lang, "google_sync_auto_backup_failed", message=str(exc)))
        except Exception as exc:
            self.window.append_log(tr(self.lang, "google_sync_auto_backup_failed", message=str(exc)))

    def _handle_passphrase_cache(self, service: SyncService, remember: bool, passphrase: str):
        if remember:
            service.cache_passphrase(passphrase)
            self.window.append_log(tr(self.lang, "google_sync_cache_saved"))
        else:
            service.clear_cached_passphrase()
            self.window.append_log(tr(self.lang, "google_sync_cache_cleared"))

    def _update_google_sync_dialog_state(self, dialog: GlobalSettingsDialog, backup_exists=None):
        signed_in = False
        try:
            service = self._build_sync_service()
            signed_in = service.auth.has_cached_credentials() or bool(self.config.get("google_sync_enabled", False))
        except Exception:
            signed_in = bool(self.config.get("google_sync_enabled", False))
        dialog.set_google_sync_status(
            self.config.get("google_account_email", ""),
            self.config.get("google_sync_last_uploaded_at", ""),
            self.config.get("google_sync_last_downloaded_at", ""),
            self.config.resolve_rclone_conf_path() or self.config.get("rclone_conf_path", ""),
            self.config.resolve_google_token_path(),
            backup_exists,
            signed_in,
        )

    def _prompt_passphrase(self, title_key: str, prompt_key: str, require_confirm=False, remember_enabled=False):
        dialog = PassphraseDialog(
            self.lang,
            tr(self.lang, title_key),
            tr(self.lang, prompt_key),
            require_confirm=require_confirm,
            remember_enabled=remember_enabled,
            parent=self.window,
        )
        if dialog.exec():
            return dialog.get_passphrase(), dialog.remember_on_device()
        return "", False

    def _validate_google_client_secret(self, data) -> bool:
        raw = data.get("google_client_secret_path", "").strip()
        if not raw:
            QMessageBox.warning(self.window, tr(self.lang, "error"), tr(self.lang, "google_sync_no_secret"))
            return False
        try:
            resolved = self._persist_google_client_secret(data)
        except Exception:
            resolved = self.config.resolve_google_client_secret_path(raw)
        if not resolved or not Path(resolved).exists():
            QMessageBox.warning(self.window, tr(self.lang, "error"), tr(self.lang, "google_sync_secret_missing"))
            return False
        return True

    def _handle_google_sync_dialog(self, settings_dialog: GlobalSettingsDialog, data):
        self._apply_settings_data(data, refresh_remotes=False)
        sync_data = dict(self.config.config)
        dialog = GoogleSyncDialog(sync_data, self.lang, self.window)
        self._update_google_sync_dialog_state(dialog)
        def merged_data():
            values = dict(data)
            values.update(dialog.get_data())
            return values

        dialog.on_google_sign_in = lambda: self._handle_google_sign_in(dialog, merged_data())
        dialog.on_google_sign_out = lambda: self._handle_google_sign_out(dialog, merged_data())
        dialog.on_google_backup = lambda: self._handle_google_backup(dialog, merged_data())
        dialog.on_google_restore = lambda: self._handle_google_restore(dialog, merged_data())
        dialog.on_google_check_backup = lambda: self._handle_google_check_backup(dialog, merged_data())

        dialog.exec()
        final_data = merged_data()
        raw_secret = (final_data.get("google_client_secret_path", "") or "").strip()
        if raw_secret:
            try:
                self._persist_google_client_secret(final_data)
                self._apply_settings_data(final_data, refresh_remotes=False)
            except Exception as exc:
                QMessageBox.warning(self.window, tr(self.lang, "google_sync"), str(exc))
        self._update_google_sync_dialog_state(settings_dialog)

    def _handle_google_sign_in(self, dialog: GlobalSettingsDialog, data):
        if not self._validate_google_client_secret(data):
            return
        self._apply_settings_data(data, refresh_remotes=False)
        try:
            service = self._build_sync_service(data)
            service.sign_in(interactive=True)
        except SyncServiceError as exc:
            QMessageBox.critical(self.window, tr(self.lang, "google_sync"), tr(self.lang, "google_sync_action_failed", message=str(exc)))
            return
        self._update_google_sync_dialog_state(dialog)
        self.window.append_log(tr(self.lang, "google_sync_signin_ok"))
        QMessageBox.information(self.window, tr(self.lang, "google_sync"), tr(self.lang, "google_sync_signin_ok"))

    def _handle_google_sign_out(self, dialog: GlobalSettingsDialog, data):
        self._apply_settings_data(data, refresh_remotes=False)
        try:
            service = self._build_sync_service(data)
            service.sign_out()
        except SyncServiceError as exc:
            QMessageBox.critical(self.window, tr(self.lang, "google_sync"), tr(self.lang, "google_sync_action_failed", message=str(exc)))
            return
        self._update_google_sync_dialog_state(dialog)
        self.window.append_log(tr(self.lang, "google_sync_signout_ok"))
        QMessageBox.information(self.window, tr(self.lang, "google_sync"), tr(self.lang, "google_sync_signout_ok"))

    def _handle_google_backup(self, dialog: GlobalSettingsDialog, data):
        if not self._validate_google_client_secret(data):
            return
        passphrase, remember = self._prompt_passphrase("passphrase_title_backup", "passphrase_prompt_backup", require_confirm=True, remember_enabled=True)
        if not passphrase:
            return
        self._apply_settings_data(data, refresh_remotes=False)
        try:
            service = self._build_sync_service(data)
            service.backup_current_conf(passphrase, interactive=True)
            self._handle_passphrase_cache(service, remember, passphrase)
        except SyncServiceError as exc:
            QMessageBox.critical(self.window, tr(self.lang, "google_sync"), tr(self.lang, "google_sync_action_failed", message=str(exc)))
            return
        self._update_google_sync_dialog_state(dialog)
        self.window.append_log(tr(self.lang, "google_sync_backup_ok"))
        QMessageBox.information(self.window, tr(self.lang, "google_sync"), tr(self.lang, "google_sync_backup_ok"))

    def _handle_google_check_backup(self, dialog: GlobalSettingsDialog, data):
        if not self._validate_google_client_secret(data):
            return
        self._apply_settings_data(data, refresh_remotes=False)
        try:
            service = self._build_sync_service(data)
            exists = service.has_remote_backup(interactive=True)
        except SyncServiceError as exc:
            QMessageBox.critical(self.window, tr(self.lang, "google_sync"), tr(self.lang, "google_sync_action_failed", message=str(exc)))
            return
        self._update_google_sync_dialog_state(dialog, backup_exists=exists)
        self.window.append_log(tr(self.lang, "google_backup_exists") if exists else tr(self.lang, "google_backup_missing"))
        QMessageBox.information(self.window, tr(self.lang, "google_sync"), tr(self.lang, "google_backup_exists") if exists else tr(self.lang, "google_backup_missing"))

    def _handle_google_restore(self, dialog: GlobalSettingsDialog, data):
        if not self._validate_google_client_secret(data):
            return
        self._apply_settings_data(data, refresh_remotes=False)
        try:
            service = self._build_sync_service(data)
            passphrase = service.load_cached_passphrase()
            remember = False
            if passphrase:
                self.window.append_log(tr(self.lang, "google_sync_cached_passphrase"))
            else:
                passphrase, remember = self._prompt_passphrase("passphrase_title_restore", "passphrase_prompt_restore", require_confirm=False, remember_enabled=True)
                if not passphrase:
                    return
            target_path = service.get_restore_target_path()
            confirmed = QMessageBox.question(
                self.window,
                tr(self.lang, "google_restore_confirm_title"),
                tr(self.lang, "google_restore_confirm", path=str(target_path)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if confirmed != QMessageBox.StandardButton.Yes:
                return
            result = service.restore_conf(passphrase, interactive=True, target_path=target_path)
            if not service.load_cached_passphrase() and passphrase:
                self._handle_passphrase_cache(service, remember, passphrase)
        except SyncServiceError as exc:
            QMessageBox.critical(self.window, tr(self.lang, "google_sync"), tr(self.lang, "google_sync_action_failed", message=str(exc)))
            return

        self.engine.set_paths(
            self.config.resolve_rclone_path(),
            self.config.resolve_rclone_conf_path(),
        )
        self._refresh_rclone_conf_watch()
        self._refresh_remote_cache()
        self._update_google_sync_dialog_state(dialog)
        self.window.append_log(tr(self.lang, "google_sync_restore_ok"))
        message = tr(self.lang, "google_sync_restore_ok")
        if result.get("backup_path"):
            message = message + "\n\n" + tr(self.lang, "google_sync_restore_backup", path=result["backup_path"])
        QMessageBox.information(self.window, tr(self.lang, "google_sync"), message)

    def _refresh_bulk_action_state(self, profiles=None):
        if profiles is None:
            profiles = self.config.get_profiles()
        active_count = sum(1 for profile in profiles if profile["id"] in self.watchers)
        self.window.set_bulk_buttons_enabled(active_count < len(profiles), active_count > 0)
        self.window.update_overview(len(profiles), active_count, self.config.get("theme", "light"))
        self._refresh_tray_profiles(profiles)

    def _setup_dashboards(self):
        self.window.clear_cards()
        profiles = self.config.get_profiles()
        active_count = sum(1 for profile in profiles if profile["id"] in self.watchers)

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

        self._refresh_bulk_action_state(profiles)

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
            self._get_available_remote_details(),
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
            self._get_available_remote_details(),
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

    def _apply_profile_drive_icon(self, profile):
        try:
            icon_path = apply_drive_icon(
                self.config.get_app_dir(),
                profile.get("letter", ""),
                profile,
                remote_type=profile.get("remote_type", ""),
                remote_name=profile.get("remote", ""),
            )
            if icon_path:
                self.window.append_log(f"Applied drive icon for {profile.get('letter', '?')}: {icon_path}")
        except Exception as exc:
            self.window.append_log(f"Drive icon apply failed: {exc}")

    def _clear_profile_drive_icon(self, profile):
        try:
            clear_drive_icon(profile.get("letter", ""))
        except Exception as exc:
            self.window.append_log(f"Drive icon clear failed: {exc}")

    def _handle_watcher_finished(self, pid):
        watcher = self.watchers.get(pid)
        if watcher is None:
            return
        if not watcher.isFinished():
            return

        profile = next((p for p in self.config.get_profiles() if p["id"] == pid), None)
        self.watchers.pop(pid, None)
        card = self._find_card(pid)
        if card:
            card.set_status("Disconnected")
        if profile:
            self._clear_profile_drive_icon(profile)
        self._refresh_bulk_action_state()

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
                    self.lang,
                )
                watcher.status_changed.connect(card.set_status)
                watcher.log_emitted.connect(self.window.append_log)
                watcher.finished.connect(lambda pid=pid: self._handle_watcher_finished(pid))
                watcher.start()
                self.watchers[pid] = watcher
                self._apply_profile_drive_icon(profile)
                self._refresh_bulk_action_state()
            else:
                self.window.append_log(f"Mount Error: {self.engine.last_error}")
                QMessageBox.critical(self.window, tr(self.lang, "mount_failed"), f"Rclone Error:\n\n{self.engine.last_error}")
        else:
            if pid in self.watchers:
                self.watchers[pid].stop()
                del self.watchers[pid]
            self.engine.unmount(profile["letter"])
            self._clear_profile_drive_icon(profile)
            card.set_status("Disconnected")
            self._refresh_bulk_action_state()

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

    def _get_app_version_info(self):
        installed_version = __version__
        download_url = self.app_updater.get_releases_url()
        try:
            latest_release = self.app_updater.get_latest_release()
            latest_version = latest_release.get("version", "")
            download_url = latest_release.get("url") or download_url
        except Exception:
            latest_version = ""

        if installed_version and latest_version:
            if self.app_updater.is_update_available(installed_version, latest_version):
                return {
                    "label": tr(self.lang, "app_update_available", version=installed_version),
                    "update_available": True,
                    "tooltip": tr(self.lang, "tooltip_app_update_available", installed=installed_version, latest=latest_version),
                    "installed_version": installed_version,
                    "latest_version": latest_version,
                    "download_url": download_url,
                    "installer_url": latest_release.get("installer_url", ""),
                    "installer_name": latest_release.get("installer_name", ""),
                }
            return {
                "label": tr(self.lang, "app_latest", version=installed_version),
                "update_available": False,
                "tooltip": tr(self.lang, "tooltip_app_latest", version=installed_version),
                "installed_version": installed_version,
                "latest_version": latest_version,
                "download_url": download_url,
                "installer_url": latest_release.get("installer_url", ""),
                "installer_name": latest_release.get("installer_name", ""),
            }

        return {
            "label": tr(self.lang, "app_version_current", version=installed_version) if installed_version else tr(self.lang, "app_version_unknown"),
            "update_available": False,
            "tooltip": tr(self.lang, "tooltip_app_unknown"),
            "installed_version": installed_version,
            "latest_version": latest_version,
            "download_url": download_url,
            "installer_url": "",
            "installer_name": "",
        }

    def _handle_app_update_check(self, dialog):
        info = self._get_app_version_info()
        dialog.set_app_version_status(info["label"], info["update_available"], info["tooltip"], info["download_url"])
        dialog.set_app_installer_url(info.get("installer_url", ""))

        if info["latest_version"] and info["update_available"]:
            message = tr(
                self.lang,
                "app_update_available_message",
                installed=info["installed_version"],
                latest=info["latest_version"],
            )
            prompt = f"{message}\n\n{tr(self.lang, 'app_update_install_prompt')}"
            reply = QMessageBox.question(
                self.window,
                tr(self.lang, "app_update_title"),
                prompt,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._run_app_update_download(info)
            return

        if info["latest_version"]:
            QMessageBox.information(
                self.window,
                tr(self.lang, "app_update_title"),
                tr(
                    self.lang,
                    "app_update_latest_message",
                    installed=info["installed_version"],
                    latest=info["latest_version"],
                ),
            )
            return

        QMessageBox.warning(
            self.window,
            tr(self.lang, "app_update_title"),
            tr(self.lang, "app_update_unknown_message"),
        )

    def _open_app_download_page(self, url: str):
        try:
            webbrowser.open(url)
        except Exception as exc:
            QMessageBox.warning(self.window, tr(self.lang, "error"), str(exc))

    def _handle_app_update_install(self, dialog):
        info = self._get_app_version_info()
        dialog.set_app_version_status(info["label"], info["update_available"], info["tooltip"], info["download_url"])
        dialog.set_app_installer_url(info.get("installer_url", ""))
        self._run_app_update_download(info)

    def _run_app_update_download(self, info: dict):
        installer_url = info.get("installer_url", "")
        installer_name = info.get("installer_name", "")
        if not installer_url:
            QMessageBox.warning(
                self.window,
                tr(self.lang, "app_update_title"),
                tr(self.lang, "app_update_installer_missing"),
            )
            return

        update_dialog = AppUpdateDialog(info.get("installed_version", ""), info.get("latest_version", ""), self.lang, self.window)
        worker = AppUpdateWorker(self.app_updater, installer_url, installer_name)
        worker.progress_changed.connect(
            lambda percent: update_dialog.status_label.setText(tr(self.lang, "app_update_progress", percent=percent))
        )
        worker.progress_changed.connect(update_dialog.progress.setValue)
        worker.failed.connect(
            lambda message: self._finish_app_update_failure(update_dialog, message)
        )
        worker.finished_with_result.connect(
            lambda path: self._finish_app_update_success(update_dialog, path)
        )
        worker.start()
        self._active_app_update_worker = worker
        update_dialog.exec()

    def _finish_app_update_failure(self, dialog, message: str):
        dialog.close_btn.setEnabled(True)
        dialog.status_label.setText(message)
        QMessageBox.warning(self.window, tr(self.lang, "app_update_title"), message)

    def _finish_app_update_success(self, dialog, installer_path: str):
        dialog.progress.setValue(100)
        dialog.close_btn.setEnabled(True)
        dialog.status_label.setText(installer_path)
        try:
            self.app_updater.schedule_installer_after_pid_exits(installer_path, os.getpid())
        except Exception as exc:
            QMessageBox.warning(self.window, tr(self.lang, "app_update_title"), str(exc))
            return

        dialog.accept()
        self.window.append_log(f"Preparing app update installer: {installer_path}")
        self.exit_app()

    def _refresh_remote_cache(self, rclone_path=None, conf_path=None):
        active_rclone_path = rclone_path or self.engine.rclone_path
        active_conf_path = conf_path if conf_path is not None else self.engine.rclone_conf_path
        original_rclone_path = self.engine.rclone_path
        original_conf_path = self.engine.rclone_conf_path

        try:
            self.engine.set_paths(active_rclone_path, active_conf_path)
            parsed_entries = self.config.parse_rclone_conf(active_conf_path)
            parsed = [item.get("name") for item in parsed_entries if item.get("name")]
            listed = self.engine.get_remotes()
        finally:
            self.engine.set_paths(original_rclone_path, original_conf_path)

        merged = []
        detail_map = {}
        for entry in parsed_entries:
            name = entry.get("name")
            if not name:
                continue
            detail_map[name] = {
                "name": name,
                "type": entry.get("type", ""),
            }
        for name in parsed + listed:
            if name and name not in merged:
                merged.append(name)
                detail_map.setdefault(name, {"name": name, "type": ""})
        self.remote_cache = merged
        self.remote_details = [detail_map[name] for name in merged if name in detail_map]
        if merged:
            self.window.append_log(tr(self.lang, "loaded_remotes", count=len(merged)))
        else:
            self.window.append_log(tr(self.lang, "no_remotes"))

    def _get_available_remotes(self):
        if self.remote_cache:
            return self.remote_cache
        self._refresh_remote_cache()
        return self.remote_cache

    def _get_available_remote_details(self):
        if self.remote_details:
            return self.remote_details
        self._refresh_remote_cache()
        return self.remote_details

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
