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

    def __init__(self, engine: RcloneEngine, remote: str, drive_letter: str, vfs_mode: str, 
                 root_folder: str = "/", custom_args: str = "", volname: str = ""):
        super().__init__()
        self.engine = engine
        self.remote = remote
        self.drive_letter = drive_letter
        self.vfs_mode = vfs_mode
        self.root_folder = root_folder
        self.custom_args = custom_args
        self.volname = volname
        
        self.is_running = True
        self.drive_path = f"{self.drive_letter.upper()}:\\"

    def run(self):
        logger.info(f"Watcher 가동: {self.remote}")
        
        # 1. 초기 상태 엄격 체크 (최대 12초)
        if not self._wait_and_validate_mount(timeout=12):
            self.status_changed.emit("Disconnected")
            return

        # 2. 메인 주기적 감시
        while self.is_running:
            if self._check_connection():
                self.status_changed.emit("Connected")
                self.msleep(5000)
            else:
                self.log_emitted.emit(f"[Watcher] {self.remote} 연결 유실 감지.")
                self._handle_reconnect()

    def _wait_and_validate_mount(self, timeout=12) -> bool:
        """ 드라이브 문자가 OS에 나타나는지 매초 체크합니다. """
        for i in range(timeout):
            if not self.is_running: return False
            
            # 프로세스 조기 사망 여부 초단위 체크
            if not self.engine.is_process_alive(self.drive_letter):
                err = self.engine.last_err
                msg = f"[Error] 마운트 실패: {err[:200]}" if err else "[Error] Rclone 프로세스가 예기치 않게 종료됨."
                self.log_emitted.emit(msg)
                return False
            
            # 실제 드라이브 존재 여부 확인
            if self._check_drive_exists():
                self.log_emitted.emit(f"[Success] {self.drive_letter}: 연결 완료.")
                self.status_changed.emit("Connected")
                return True
            
            self.status_changed.emit("Mounting...")
            self.msleep(1000)
            
        self.log_emitted.emit(f"[Warning] {self.remote} 드라이브 발견 실패 (타임아웃)")
        return False

    def _check_connection(self) -> bool:
        if not self.engine.is_process_alive(self.drive_letter): return False
        return self._check_drive_exists()

    def _check_drive_exists(self) -> bool:
        if os.path.exists(self.drive_path): return True
        try:
            for p in psutil.disk_partitions():
                if p.mountpoint.upper().startswith(f"{self.drive_letter.upper()}:"):
                    return True
        except: pass
        return False

    def _handle_reconnect(self):
        backoff = 2
        self.engine.unmount(self.drive_letter)
        
        while self.is_running:
            self.status_changed.emit(f"Fix ({backoff}s)")
            success = self.engine.mount(
                self.remote, self.drive_letter, self.vfs_mode, 
                self.root_folder, self.custom_args, self.volname
            )
            
            if success and self._wait_and_validate_mount(timeout=12):
                break
            
            self.msleep(backoff * 1000)
            backoff = min(backoff * 2, 30)

    def stop(self):
        self.is_running = False
        self.wait()
