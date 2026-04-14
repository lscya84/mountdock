import time
import socket
import os
import logging
import psutil
from PyQt6.QtCore import QThread, pyqtSignal
from ldrive.rclone_engine import RcloneEngine

logger = logging.getLogger("Watcher")

class LDriveWatcher(QThread):
    status_changed = pyqtSignal(str)
    log_emitted = pyqtSignal(str)

    def __init__(self, engine: RcloneEngine, remote: str, drive_letter: str, vfs_mode: str, root_folder: str = "/", custom_args: str = "", volname: str = ""):
        super().__init__()
        self.engine = engine
        self.remote = remote
        self.drive_letter = drive_letter
        self.vfs_mode = vfs_mode
        self.root_folder = root_folder
        self.custom_args = custom_args
        self.volname = volname
        
        self.is_running = True
        self.check_interval = 5
        self.max_backoff = 30
        self.drive_path = f"{self.drive_letter.upper()}:\\"

    def run(self):
        logger.info(f"Watcher 스레드 시작: {self.remote} -> {self.drive_path}")
        self.log_emitted.emit(f"[Watcher] 감시 시작: {self.remote} -> {self.drive_path}")
        
        # Rclone이 드라이브를 완전히 띄울 넉넉한 시간을 줍니다.
        self.msleep(8000)
        
        while self.is_running:
            if self._check_connection():
                self.status_changed.emit("Connected")
                self.msleep(self.check_interval * 1000)
            else:
                self.status_changed.emit("Disconnected")
                self.log_emitted.emit(f"[Watcher] {self.remote} 연결 유실 감지 (드라이브 미발견).")
                self._handle_reconnect()

    def _check_connection(self) -> bool:
        if not self._is_network_available():
            return False
        return self._check_drive_exists()

    def _check_drive_exists(self) -> bool:
        """OS 수준에서 마운트 유무를 다각도로 확인합니다."""
        # 1. 표준 경로 체크
        if os.path.exists(self.drive_path) or os.path.exists(self.drive_path.rstrip("\\")):
            return True
        
        # 2. psutil 파티션 리스트 체크 (네트워크 드라이브 인식 보조)
        try:
            drive_letter_upper = self.drive_letter.upper()
            partitions = psutil.disk_partitions()
            for p in partitions:
                if p.mountpoint.upper().startswith(f"{drive_letter_upper}:"):
                    return True
        except Exception as e:
            logger.error(f"Partition check error: {e}")
            
        return False

    def _is_network_available(self, host="8.8.8.8", port=53, timeout=3) -> bool:
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except Exception:
            return False

    def _handle_reconnect(self):
        backoff = 1
        # 재연결 전 깔끔하게 한 번 밀어주기
        self.engine.unmount(self.drive_letter)
        
        while self.is_running:
            self.status_changed.emit(f"Reconnecting ({backoff}s...)")
            self.log_emitted.emit(f"[Watcher] {self.remote} 재연결 시도 중...")
            
            success = self.engine.mount(
                self.remote, self.drive_letter, self.vfs_mode, 
                self.root_folder, self.custom_args, self.volname
            )
            
            if success:
                # 등록 대기 경과 시간 (8초)
                self.msleep(8000)
                if self._check_drive_exists():
                    self.log_emitted.emit(f"[Watcher] {self.remote} 재연결 성공!")
                    self.status_changed.emit("Connected")
                    break
                else:
                    self.log_emitted.emit(f"[Watcher] {self.remote} 마운트 성공했으나 드라이브가 보이지 않습니다 (8초 경과).")
                    self.engine.unmount(self.drive_letter)
            
            self.msleep(backoff * 1000)
            backoff = min(backoff * 2, self.max_backoff)
            
            if not self._is_network_available():
                self.log_emitted.emit("[Watcher] 네트워크 연결 대기 중...")

    def stop(self):
        self.is_running = False
        self.wait()
        logger.info("Watcher 스레드가 중지되었습니다.")
