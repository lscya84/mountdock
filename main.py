import sys
import os
import logging
import subprocess
from PyQt6.QtWidgets import QApplication, QStyle, QMessageBox, QSystemTrayIcon
from PyQt6.QtGui import QIcon, QAction

from ldrive.config_manager import ConfigManager
from ldrive.rclone_engine import RcloneEngine
from ldrive.ui_components import LDriveMainWindow, LDriveTrayIcon, DriveCardWidget, DriveSettingsDialog, GlobalSettingsDialog
from ldrive.watcher import LDriveWatcher

# 로거 설정
logger = logging.getLogger("Main")

class LDriveApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # 1. 코어 초기화
        self.config = ConfigManager()
        self.engine = RcloneEngine(self.config.get("rclone_path", "rclone.exe"), 
                                   self.config.get("rclone_conf_path", ""))
        
        # 2. UI 초기화
        self.window = LDriveMainWindow()
        
        icon_path = LDriveMainWindow.resource_path(os.path.join("assets", "icon.ico"))
        self.default_icon = QIcon(icon_path) if os.path.exists(icon_path) else self.app.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon)
        self.window.setWindowIcon(self.default_icon)
        
        self.tray = LDriveTrayIcon(self.default_icon)
        self.tray.show()

        # 3. 다중 스레드 관리
        self.watchers = {}

        # 4. 앱 바인딩
        self._wire_signals()
        
        # 5. 초기 테마 적용
        current_theme = self.config.get("theme", "light")
        self.window._apply_styles(current_theme)

        # 6. 대시보드 로드
        self._setup_dashboards()
        
        # 7. 실행 모드
        if self.config.get("start_minimized"):
            self.window.hide()
        else:
            self.window.show()

    def _wire_signals(self):
        self.window.add_requested.connect(self.handle_add_drive)
        self.window.settings_requested.connect(self.handle_settings)
        self.window.theme_toggle_requested.connect(self.handle_theme_toggle)
        self.tray.show_requested.connect(self._show_window)
        self.tray.exit_requested.connect(self.exit_app)
        self.window.closeEvent = self._on_close_event

    def handle_theme_toggle(self):
        theme = "dark" if self.config.get("theme") == "light" else "light"
        self.config.set("theme", theme)
        self.window._apply_styles(theme)

    def _show_window(self):
        self.window.show()
        self.window.raise_(); self.window.activateWindow()

    def _on_close_event(self, event):
        self.exit_app(); event.accept()

    def handle_settings(self):
        dialog = GlobalSettingsDialog(self.config.config, self.window)
        if dialog.exec():
            data = dialog.get_data()
            for k, v in data.items():
                if k == "auto_start": self.config.set_auto_start(v)
                else: self.config.set(k, v)
            self.engine.set_paths(data["rclone_path"], data["rclone_conf_path"])
            self.window.append_log("Settings saved.")

    def _setup_dashboards(self):
        self.window.clear_cards()
        for profile in self.config.get_profiles():
            card = DriveCardWidget(profile)
            card.toggle_requested.connect(self.handle_toggle_mount)
            card.edit_requested.connect(self.handle_edit_drive)
            card.delete_requested.connect(self.handle_delete_drive)
            # 이미 실행 중인 경우 상태 동기화 (Watcher가 관리 중이라면)
            if profile["id"] in self.watchers:
                card.set_status("Connected")
            self.window.add_card(card)

    def handle_add_drive(self):
        dialog = DriveSettingsDialog(self.engine.get_remotes(), self.window)
        if dialog.exec():
            self.config.add_profile(dialog.get_data())
            self._setup_dashboards()

    def handle_edit_drive(self, pid):
        profile = next((p for p in self.config.get_profiles() if p["id"] == pid), None)
        if not profile: return
        if pid in self.watchers:
            QMessageBox.warning(self.window, "Error", "Stop drive before editing.")
            return
        dialog = DriveSettingsDialog(self.engine.get_remotes(), self.window, profile)
        if dialog.exec():
            self.config.update_profile(pid, dialog.get_data())
            self._setup_dashboards()

    def handle_delete_drive(self, pid):
        if pid in self.watchers: self.handle_toggle_mount(pid, False)
        self.config.delete_profile(pid)
        self._setup_dashboards()

    def handle_toggle_mount(self, pid, should_start):
        profile = next((p for p in self.config.get_profiles() if p["id"] == pid), None)
        card = self._find_card(pid)
        if not card: return

        if should_start:
            proc = self.engine.mount(profile["remote"], profile["letter"], 
                                    profile["vfs_mode"], profile["root_folder"], 
                                    profile.get("custom_args", ""), profile.get("volname", ""))
            if proc:
                watcher = LDriveWatcher(self.engine, profile["remote"], profile["letter"],
                                        profile["vfs_mode"], profile["root_folder"], 
                                        profile.get("custom_args", ""), profile.get("volname", ""))
                watcher.status_changed.connect(card.set_status)
                watcher.log_emitted.connect(self.window.append_log)
                watcher.start()
                self.watchers[pid] = watcher
            else:
                self.window.append_log(f"Mount Error: {self.engine.last_error}")
                QMessageBox.critical(self.window, "Mount Failed", f"Rclone Error:\n\n{self.engine.last_error}")
        else:
            if pid in self.watchers:
                self.watchers[pid].stop(); del self.watchers[pid]
            self.engine.unmount(profile["letter"])
            card.set_status("Disconnected")

    def _find_card(self, pid):
        for i in range(self.window.card_layout.count()):
            w = self.window.card_layout.itemAt(i).widget()
            if isinstance(w, DriveCardWidget) and w.profile["id"] == pid: return w
        return None

    def exit_app(self):
        for w in self.watchers.values(): w.stop()
        self.engine.kill_all_mounts()
        self.app.quit()

if __name__ == "__main__":
    LDriveApp().app.exec()
