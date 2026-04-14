import sys
import os
import logging
from PyQt6.QtWidgets import QApplication, QStyle, QMessageBox, QSystemTrayIcon
from PyQt6.QtGui import QIcon, QAction

from ldrive.config_manager import ConfigManager
from ldrive.rclone_engine import RcloneEngine
from ldrive.ui_components import LDriveMainWindow, LDriveTrayIcon, DriveCardWidget, DriveSettingsDialog
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

        # 3. 다중 스레드 관리 (Key: Profile ID)
        self.watchers = {}

        # 4. 앱 바인딩
        self._wire_signals()
        self._setup_dashboards()
        
        # 경로 설정 안내
        if not rclone_conf:
            self.window.append_log("안내: 설정(⚙️)에서 rclone.conf 경로를 지정하면 목록을 더 정확히 불러올 수 있습니다.")

    def _wire_signals(self):
        """글로벌 시그널 연결"""
        self.window.add_requested.connect(self.handle_add_drive)
        self.window.settings_requested.connect(self.handle_settings)
        self.window.auto_start_check.stateChanged.connect(
            lambda state: self.config.set_auto_start(state == 2)
        )
        
        self.tray.show_requested.connect(self._show_window)
        self.tray.exit_requested.connect(self.exit_app)
        
        # 창 숨기기 로직
        self.window.closeEvent = self._on_close_event

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
        rclone_path = self.config.get("rclone_path", "rclone.exe")
        conf_path = self.config.get("rclone_conf_path", "")
        
        dialog = GlobalSettingsDialog(rclone_path, conf_path, self.window)
        if dialog.exec():
            new_rclone, new_conf = dialog.get_data()
            self.config.set("rclone_path", new_rclone)
            self.config.set("rclone_conf_path", new_conf)
            self.engine.set_paths(new_rclone, new_conf)
            self.window.append_log("전역 설정이 저장되었습니다.")
            # 리모트 목록 갱신을 위해 대시보드 리로드 고려 가능
            self._setup_dashboards()

    def _setup_dashboards(self):
        """저장된 모든 프로필을 대시보드 카드로 생성합니다."""
        self.window.clear_cards()
        profiles = self.config.get_profiles()
        
        # 자동 실행 체크박스 상태 업데이트
        self.window.auto_start_check.setChecked(self.config.get("auto_start", False))
        
        for profile in profiles:
            card = DriveCardWidget(profile)
            # 카드 시그널 연결
            card.toggle_requested.connect(self.handle_toggle_mount)
            card.edit_requested.connect(self.handle_edit_drive)
            card.delete_requested.connect(self.handle_delete_drive)
            
            # 이미 다른 곳에서 마운트된 적이 있는지 등은 추후 체크 가능
            self.window.add_card(card)
            
        self.window.append_log(f"대시보드 로드 완료: {len(profiles)}개의 드라이브")

    def handle_add_drive(self):
        """새 드라이브 추가 다이얼로그 실행"""
        remotes = self.engine.get_remotes()
        dialog = DriveSettingsDialog(remotes, self.window)
        
        if dialog.exec():
            new_data = dialog.get_data()
            self.config.add_profile(new_data)
            self._setup_dashboards()
            self.window.append_log(f"새 드라이브 추가됨: {new_data['remote']}")

    def handle_edit_drive(self, profile_id):
        """기존 드라이브 설정 수정"""
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
        """드라이브 삭제"""
        reply = QMessageBox.question(self.window, "삭제 확인", "정말로 이 드라이브를 삭제하시겠습니까?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            # 실행 중이면 중지
            if profile_id in self.watchers:
                self.handle_toggle_mount(profile_id, False)
            
            self.config.delete_profile(profile_id)
            self._setup_dashboards()
            self.window.append_log("드라이브 프로필이 삭제되었습니다.")

    def handle_toggle_mount(self, profile_id, should_start):
        """개별 드라이브의 시작/중지를 처리합니다."""
        profiles = self.config.get_profiles()
        profile = next((p for p in profiles if p["id"] == profile_id), None)
        if not profile: return

        # 해당 카드를 찾기 위해 레이아웃 순회
        card = self._find_card_by_id(profile_id)

        if should_start:
            # 마운트 시작
            self.window.append_log(f"[{profile['remote']}] 마운트 시도 중...")
            success = self.engine.mount(
                remote=profile["remote"],
                drive_letter=profile["letter"],
                vfs_mode=profile["vfs_mode"],
                root_folder=profile["root_folder"],
                custom_args=profile["custom_args"]
            )
            
            if success:
                # Watcher 생성
                watcher = LDriveWatcher(
                    self.engine, profile["remote"], profile["letter"], 
                    profile["vfs_mode"], profile["root_folder"], profile["custom_args"]
                )
                # 시그널 연결 (가장 중요: 특정 카드의 상태만 업데이트해야 함)
                if card:
                    watcher.status_changed.connect(card.set_status)
                watcher.log_emitted.connect(self.window.append_log)
                
                watcher.start()
                self.watchers[profile_id] = watcher
                if card: card.set_status("Connected")
            else:
                QMessageBox.critical(self.window, "에러", f"{profile['remote']} 마운트 실행에 실패했습니다.")
        else:
            # 마운트 중지
            self.window.append_log(f"[{profile['remote']}] 마운트 해제 중...")
            if profile_id in self.watchers:
                self.watchers[profile_id].stop()
                del self.watchers[profile_id]
            
            self.engine.unmount(profile["letter"])
            if card: card.set_status("Disconnected")

    def _find_card_by_id(self, profile_id):
        """UI 레이아웃에서 특정 ID를 가진 카드를 찾습니다."""
        for i in range(self.window.card_layout.count()):
            widget = self.window.card_layout.itemAt(i).widget()
            if isinstance(widget, DriveCardWidget) and widget.profile["id"] == profile_id:
                return widget
        return None

    def exit_app(self):
        """앱 완전 종료 절차"""
        self.window.append_log("시스템 종료 중... 모든 드라이브를 정리합니다.")
        
        # 1. 모든 감시 스레드 중지
        for wid in list(self.watchers.keys()):
            self.watchers[wid].stop()
        
        # 2. 모든 rclone 프로세스 Kill
        self.engine.kill_all_mounts()
        
        self.app.quit()

    def run(self):
        self.window.show()
        sys.exit(self.app.exec())

if __name__ == "__main__":
    app_instance = LDriveApp()
    app_instance.run()
