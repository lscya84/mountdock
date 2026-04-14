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
        logger.info(f"Watcher 시작: {self.remote} -> {self.drive_letter}:")
        
        # 1. 초기 5초간 집중 생존 모니터링
        if not self._initial_check():
            return

        # 2. 메인 감시 루프
        while self.is_running:
            if self._check_connection():
                self.status_changed.emit("Connected")
                self.msleep(5000) # 5초 간격 체크
            else:
                self.status_changed.emit("Broken")
                self._handle_reconnect()

    def _initial_check(self) -> bool:
        """ 드라이브가 올라올 때까지 프로세스 생사 여부를 초단위로 확인합니다. """
        for i in range(10): # 최대 10초 대기
            if not self.is_running: return False
            
            # 프로세스 즉시 사망 체크
            if not self.engine.is_process_alive(self.drive_letter):
                err = self.engine.last_error_msg
                msg = f"[Error] Rclone 프로세스 즉시 종료됨: {err[:200]}" if err else f"[Error] {self.remote} 마운트 중 프로세스가 죽었습니다."
                self.log_emitted.emit(msg)
                self.status_changed.emit("Fatal")
                return False
            
            # 드라이브 탐지 성공 여부
            if self._check_drive_exists():
                self.log_emitted.emit(f"[Success] {self.drive_letter}: 드라이브 연결 완료.")
                self.status_changed.emit("Connected")
                return True
                
            self.status_changed.emit("Wait...")
            self.msleep(1000)
            
        self.log_emitted.emit(f"[Timeout] {self.remote} 드라이브 발견 시간 초과.")
        return False

    def _check_connection(self) -> bool:
        if not self.engine.is_process_alive(self.drive_letter):
            return False
        return self._check_drive_exists()

    def _check_drive_exists(self) -> bool:
        if os.path.exists(self.drive_path) or os.path.exists(self.drive_path.rstrip("\\")):
            return True
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
            self.status_changed.emit(f"Repair ({backoff}s)")
            self.log_emitted.emit(f"[Watcher] {self.remote} 재연결 시도 중...")
            
            success = self.engine.mount(
                self.remote, self.drive_letter, self.vfs_mode, 
                self.root_folder, self.custom_args, self.volname
            )
            
            if success and self._initial_check():
                break
            
            self.msleep(backoff * 1000)
            backoff = min(backoff * 2, 30)

    def stop(self):
        self.is_running = False
        self.wait()
