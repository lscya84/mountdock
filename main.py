import sys
import logging
from PyQt6.QtWidgets import QApplication, QStyle, QMessageBox
from PyQt6.QtGui import QIcon, QAction

from ldrive.config_manager import ConfigManager
from ldrive.rclone_engine import RcloneEngine
from ldrive.ui_components import LDriveMainWindow, LDriveTrayIcon
from ldrive.watcher import LDriveWatcher

# 로거 설정 (이미 ConfigManager에서 설정됨)
logger = logging.getLogger("Main")

class LDriveApp:
    """
    L-Drive Pro 전체 애플리케이션의 흐름을 관장하는 메인 컨트롤러 클래스입니다.
    """
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False) # 창을 닫아도 프로세스 종료 방지 (트레이 유지)

        # 1. 코어 엔진 초기화
        self.config = ConfigManager()
        self.engine = RcloneEngine(self.config.get("rclone_path", "rclone.exe"))
        
        # 2. UI 초기화
        self.window = LDriveMainWindow()
        
        # 아이콘 설정 (assets/icon.ico가 없으면 시스템 표준 아이콘 사용)
        self.default_icon = self.app.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon)
        self.window.setWindowIcon(self.default_icon)
        
        self.tray = LDriveTrayIcon(self.default_icon)
        self.tray.show()

        # 3. 런타임 변수
        self.watcher = None

        # 4. 앱 초기 설정 및 바인딩
        self._setup_ui_data()
        self._wire_signals()

        # 마운트 버튼 초기 상태 제어
        self.window.unmount_btn.setEnabled(False)

    def _setup_ui_data(self):
        """저장된 설정값을 UI에 반영합니다."""
        # 리모트 목록 로드
        remotes = self.engine.get_remotes()
        if remotes:
            self.window.remote_combo.addItems(remotes)
            # 마지막 사용 리모트 선택
            last_remote = self.config.get("last_mount_remote")
            if last_remote in remotes:
                self.window.remote_combo.setCurrentText(last_remote)
        else:
            self.window.append_log("등록된 Rclone 리모트가 없습니다. rclone config로 먼저 등록해주세요.")

        # 드라이브 문자 선택
        last_letter = self.config.get("last_drive_letter")
        index = self.window.drive_combo.findText(f"{last_letter}:")
        if index >= 0:
            self.window.drive_combo.setCurrentIndex(index)

        # VFS 모드 선택
        last_vfs = self.config.get("vfs_mode")
        if last_vfs == "writes":
            self.window.radio_work.setChecked(True)
        else:
            self.window.radio_media.setChecked(True)

        # 자동 실행 체크박스
        self.window.auto_start_check.setChecked(self.config.get("auto_start", False))

    def _wire_signals(self):
        """UI 이벤트와 비즈니스 로직을 연결합니다."""
        # 메인 버튼
        self.window.mount_btn.clicked.connect(self.handle_mount)
        self.window.unmount_btn.clicked.connect(self.handle_unmount)
        
        # 체크박스 (자동 실행 설정)
        self.window.auto_start_check.stateChanged.connect(
            lambda state: self.config.set_auto_start(state == 2)
        )

        # 트레이 신호
        self.tray.show_requested.connect(self.show_window)
        self.tray.unmount_requested.connect(self.handle_unmount)
        self.tray.exit_requested.connect(self.exit_app)
        
        # 메인 창 닫기 이벤트 오버라이딩 (트레이로 숨기기)
        self.window.closeEvent = self._on_close_event

    def _on_close_event(self, event):
        """X 버튼 클릭 시 종료하지 않고 트레이로 숨깁니다."""
        # 사용자가 수동으로 종료(Exit)를 누른 게 아니라면 숨기기
        if self.window.isVisible():
            self.window.hide()
            self.tray.showMessage(
                "L-Drive Pro",
                "프로그램이 트레이에서 실행 중입니다.",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
            event.ignore()

    def show_window(self):
        """창을 화면에 띄우고 포커스를 줍니다."""
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def handle_mount(self):
        """사용자 입력을 바탕으로 마운트를 시도하고 감시자를 실행합니다."""
        remote = self.window.remote_combo.currentText()
        drive_letter = self.window.drive_combo.currentText().replace(":", "")
        vfs_mode = "full" if self.window.radio_media.isChecked() else "writes"

        if not remote:
            QMessageBox.warning(self.window, "경고", "마운트할 리모트를 선택해주세요.")
            return

        self.window.append_log(f"마운트 시도 중: {remote} -> {drive_letter}:")
        
        if self.engine.mount(remote, drive_letter, vfs_mode):
            # 성공 시 설정 저장
            self.config.set("last_mount_remote", remote)
            self.config.set("last_drive_letter", drive_letter)
            self.config.set("vfs_mode", vfs_mode)
            
            # Watcher 시작
            self._start_watcher(remote, drive_letter, vfs_mode)
            
            # UI 상태 변경
            self.window.mount_btn.setEnabled(False)
            self.window.unmount_btn.setEnabled(True)
            self.window.set_status("Connected")
        else:
            self.window.append_log("마운트 실패! 로그를 확인하세요.")
            QMessageBox.critical(self.window, "오류", "마운트 실행 중 오류가 발생했습니다.")

    def _start_watcher(self, remote, drive_letter, vfs_mode):
        """연결 감시 스레드를 생성하고 시작합니다."""
        if self.watcher:
            self.watcher.stop()
        
        self.watcher = LDriveWatcher(self.engine, remote, drive_letter, vfs_mode)
        self.watcher.status_changed.connect(self.window.set_status)
        self.watcher.log_emitted.connect(self.window.append_log)
        self.watcher.start()

    def handle_unmount(self):
        """현재 마운트된 드라이브를 해제하고 감시자를 중지합니다."""
        if self.watcher:
            self.watcher.stop()
            self.watcher = None

        drive_letter = self.window.drive_combo.currentText().replace(":", "")
        self.window.append_log(f"마운트 해제 시도 중: {drive_letter}:")
        
        self.engine.unmount(drive_letter)
        
        # UI 상태 복구
        self.window.mount_btn.setEnabled(True)
        self.window.unmount_btn.setEnabled(False)
        self.window.set_status("Disconnected")
        self.window.append_log("마운트 해제 완료.")

    def exit_app(self):
        """애플리케이션을 완전히 종료합니다."""
        logger.info("애플리케이션 종료 절차 시작...")
        
        if self.watcher:
            self.watcher.stop()
        
        self.engine.kill_all_mounts()
        self.app.quit()

    def run(self):
        self.window.show()
        sys.exit(self.app.exec())

if __name__ == "__main__":
    app_instance = LDriveApp()
    app_instance.run()
