import sys
import os
import logging
from PyQt6.QtWidgets import QApplication, QStyle, QMessageBox, QSystemTrayIcon
from PyQt6.QtGui import QIcon, QAction

from ldrive.config_manager import ConfigManager
from ldrive.rclone_engine import RcloneEngine
from ldrive.ui_components import LDriveMainWindow, LDriveTrayIcon, DriveCardWidget, DriveSettingsDialog, GlobalSettingsDialog
from ldrive.watcher import LDriveWatcher

# 로거 설정
logger = logging.getLogger("Main")

class LDriveApp:
    """
    RaiDrive 스타일의 다중 마운트 대시보드를 관리하는 메인 앱 클래스입니다.
    """
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # 1. 코어 초기화
        self.config = ConfigManager()
        rclone_path = self.config.get("rclone_path", "rclone.exe")
        rclone_conf = self.config.get("rclone_conf_path", "")
        
        self.engine = RcloneEngine(rclone_path, rclone_conf)
        
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
        self._setup_dashboards()
        
        # 5. 초기 테마 적용
        current_theme = self.config.get("theme", "light")
        self.window._apply_styles(current_theme)

        # 6. 실행 모드 (트레이 모드 시작 여부)
        if self.config.get("start_minimized"):
            self.window.hide()
            self.tray.showMessage("L-Drive Pro", "앱이 트레이 모드로 시작되었습니다.", QSystemTrayIcon.MessageIcon.Information, 1500)
        else:
            self.window.show()

        if not rclone_conf:
            self.window.append_log("안내: 설정(⚙️)에서 rclone.conf 경로를 지정하면 목록을 더 정확히 불러올 수 있습니다.")

    def _wire_signals(self):
        """글로벌 시그널 연결"""
        self.window.add_requested.connect(self.handle_add_drive)
        self.window.settings_requested.connect(self.handle_settings)
        self.window.theme_toggle_requested.connect(self.handle_theme_toggle)
        
        self.tray.show_requested.connect(self._show_window)
        self.tray.exit_requested.connect(self.exit_app)
        
        self.window.closeEvent = self._on_close_event

    def handle_theme_toggle(self):
        """라이트/다크 테마를 실시간으로 전환합니다."""
        current_theme = self.config.get("theme", "light")
        new_theme = "dark" if current_theme == "light" else "light"
        
        # UI 적용
        self.window._apply_styles(new_theme)
        
        # 설정 저장
        self.config.set("theme", new_theme)
        self.window.append_log(f"테마가 {new_theme} 모드로 전환되었습니다.")

    def _show_window(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def _on_close_event(self, event):
        if self.window.isVisible():
            self.window.hide()
            self.tray.showMessage("L-Drive Pro", "대시보드가 트레이로 숨겨졌습니다.", QSystemTrayIcon.MessageIcon.Information, 1500)
            event.ignore()

    def handle_settings(self):
        """전역 설정 다이얼로그 실행"""
        # 현재 설정을 딕셔너리로 전달
        current_config = {
            "rclone_path": self.config.get("rclone_path"),
            "rclone_conf_path": self.config.get("rclone_conf_path"),
            "auto_start": self.config.get("auto_start"),
            "start_minimized": self.config.get("start_minimized")
        }
        
        dialog = GlobalSettingsDialog(current_config, self.window)
        if dialog.exec():
            new_data = dialog.get_data()
            
            # 엔진 경로 갱신
            self.engine.set_paths(new_data["rclone_path"], new_data["rclone_conf_path"])
            
            # 자동 실행 레지스트리 갱신 (상태가 변한 경우에만 호출)
            if new_data["auto_start"] != self.config.get("auto_start"):
                self.config.set_auto_start(new_data["auto_start"])
            
            # 나머지 설정 저장
            self.config.set("rclone_path", new_data["rclone_path"])
            self.config.set("rclone_conf_path", new_data["rclone_conf_path"])
            self.config.set("start_minimized", new_data["start_minimized"])
            self.config.set("auto_start", new_data["auto_start"]) # 재확인 저장
            
            self.window.append_log("전역 설정이 저장되었습니다.")
            self._setup_dashboards()

    def _setup_dashboards(self):
        """저장된 모든 프로필을 대시보드 카드로 생성합니다."""
        self.window.clear_cards()
        profiles = self.config.get_profiles()
        
        for profile in profiles:
            card = DriveCardWidget(profile)
            card.toggle_requested.connect(self.handle_toggle_mount)
            card.edit_requested.connect(self.handle_edit_drive)
            card.delete_requested.connect(self.handle_delete_drive)
            self.window.add_card(card)

    def handle_add_drive(self):
        remotes = self.engine.get_remotes()
        dialog = DriveSettingsDialog(remotes, self.window)
        if dialog.exec():
            new_data = dialog.get_data()
            self.config.add_profile(new_data)
            self._setup_dashboards()
            self.window.append_log(f"새 드라이브 추가됨: {new_data['remote']}")

    def handle_edit_drive(self, profile_id):
        profiles = self.config.get_profiles()
        profile = next((p for p in profiles if p["id"] == profile_id), None)
        if not profile: return

        if profile_id in self.watchers:
            QMessageBox.warning(self.window, "경고", "마운트 중에는 설정을 수정할 수 없습니다. 먼저 중지해주세요.")
            return

        remotes = self.engine.get_remotes()
        dialog = DriveSettingsDialog(remotes, self.window, profile=profile)
        if dialog.exec():
            updated_data = dialog.get_data()
            self.config.update_profile(profile_id, updated_data)
            self._setup_dashboards()
            self.window.append_log(f"설정 수정됨: {updated_data['remote']}")

    def handle_delete_drive(self, profile_id):
        reply = QMessageBox.question(self.window, "삭제 확인", "정말로 이 드라이브를 삭제하시겠습니까?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if profile_id in self.watchers:
                self.handle_toggle_mount(profile_id, False)
            self.config.delete_profile(profile_id)
            self._setup_dashboards()
            self.window.append_log("드라이브 프로필이 삭제되었습니다.")

    def handle_toggle_mount(self, profile_id, should_start):
        profiles = self.config.get_profiles()
        profile = next((p for p in profiles if p["id"] == profile_id), None)
        if not profile: return

        card = self._find_card_by_id(profile_id)

        if should_start:
            self.window.append_log(f"[{profile['remote']}] 마운트 시도 중...")
            success = self.engine.mount(
                remote=profile["remote"],
                drive_letter=profile["letter"],
                vfs_mode=profile["vfs_mode"],
                root_folder=profile["root_folder"],
                custom_args=profile["custom_args"],
                volname=profile.get("volname", "")
            )
            
            if success:
                watcher = LDriveWatcher(
                    self.engine, profile["remote"], profile["letter"], 
                    profile["vfs_mode"], profile["root_folder"], profile["custom_args"],
                    profile.get("volname", "")
                )
                if card:
                    watcher.status_changed.connect(card.set_status)
                watcher.log_emitted.connect(self.window.append_log)
                
                watcher.start()
                self.watchers[profile_id] = watcher
                if card: card.set_status("Connected")
            else:
                QMessageBox.critical(self.window, "에러", f"{profile['remote']} 마운트 실행에 실패했습니다.")
        else:
            self.window.append_log(f"[{profile['remote']}] 마운트 해제 중...")
            if profile_id in self.watchers:
                self.watchers[profile_id].stop()
                del self.watchers[profile_id]
            
            self.engine.unmount(profile["letter"])
            if card: card.set_status("Disconnected")

    def _find_card_by_id(self, profile_id):
        for i in range(self.window.card_layout.count()):
            widget = self.window.card_layout.itemAt(i).widget()
            if isinstance(widget, DriveCardWidget) and widget.profile["id"] == profile_id:
                return widget
        return None

    def exit_app(self):
        self.window.append_log("시스템 종료 중... 모든 드라이브를 정리합니다.")
        for wid in list(self.watchers.keys()):
            self.watchers[wid].stop()
        self.engine.kill_all_mounts()
        self.app.quit()

    def run(self):
        # __init__에서 show/hide 이미 처리함
        sys.exit(self.app.exec())

if __name__ == "__main__":
    app_instance = LDriveApp()
    app_instance.run()
