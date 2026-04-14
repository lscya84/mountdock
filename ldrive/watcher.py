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
        self.check_interval = 5
        self.max_backoff = 30
        self.drive_path = f"{self.drive_letter.upper()}:\\"

    def run(self):
        logger.info(f"Watcher 스레드 시작: {self.remote}")
        
        # 초기 마운트 시도 (이미 main에서 한 번 실행되었더라도 watcher 레벨에서 재검증)
        if not self._wait_and_check_alive(wait_sec=8):
            return

        while self.is_running:
            if self._check_connection():
                self.status_changed.emit("Connected")
                self.msleep(self.check_interval * 1000)
            else:
                self.log_emitted.emit(f"[Watcher] {self.remote} 연결 유실 감지.")
                self._handle_reconnect()

    def _wait_and_check_alive(self, wait_sec=8) -> bool:
        """ rclone 프로세스 및 드라이브 실재 여부를 교차 검증하며 대기합니다. """
        for i in range(wait_sec):
            if not self.is_running: return False
            
            # 프로세스 실시간 생존 체크
            if not self.engine.is_process_alive(self.drive_letter):
                err = self.engine.last_error
                if err: self.log_emitted.emit(f"[Error] rclone 예기치 않게 죽음: {err[:200]}")
                else: self.log_emitted.emit(f"[Error] {self.remote} 프로세스 종료됨.")
                self.status_changed.emit("Error")
                return False
            
            # 드라이브 실재 여부 체크 (OS 수준)
            if self._check_drive_exists():
                self.status_changed.emit("Connected")
                return True
                
            self.msleep(1000)
        
        self.log_emitted.emit(f"[Warning] {self.remote} 8초 이상 대기했지만 {self.drive_letter}:를 찾을 수 없습니다.")
        return False

    def _check_connection(self) -> bool:
        # 프로세스 생존 상태 체크
        if not self.engine.is_process_alive(self.drive_letter):
            return False
        # 드라이브 실재 여부 체크
        return self._check_drive_exists()

    def _check_drive_exists(self) -> bool:
        """ OS에 드라이브 문자가 성공적으로 마운트되었는지 확인합니다. """
        # 기본 체크
        if os.path.exists(self.drive_path) or os.path.exists(self.drive_path.rstrip("\\")):
            return True
        # 보조 체크 (psutil)
        try:
            for p in psutil.disk_partitions():
                if p.mountpoint.upper().startswith(f"{self.drive_letter.upper()}:"):
                    return True
        except: pass
        return False

    def _handle_reconnect(self):
        backoff = 1
        self.engine.unmount(self.drive_letter)
        
        while self.is_running:
            self.status_changed.emit(f"Reconnecting ({backoff}s...)")
            self.log_emitted.emit(f"[Watcher] {self.remote} 재연결 시도 중...")
            
            res = self.engine.mount(
                self.remote, self.drive_letter, self.vfs_mode, 
                self.root_folder, self.custom_args, self.volname
            )
            
            # 여기서 res는 Popen 객체거나 None
            if res and self._wait_and_check_alive(wait_sec=8):
                self.log_emitted.emit(f"[Watcher] {self.remote} 재연결 성공!")
                break
            
            self.status_changed.emit("Error")
            self.msleep(backoff * 1000)
            backoff = min(backoff * 2, self.max_backoff)

    def stop(self):
        self.is_running = False
        self.wait()
