import time
import socket
import os
import logging
import psutil
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal
from ldrive.rclone_engine import RcloneEngine

logger = logging.getLogger("Watcher")

class LDriveWatcher(QThread):
    status_changed = pyqtSignal(str)
    log_emitted = pyqtSignal(str)

    def __init__(self, engine: RcloneEngine, remote: str, drive_letter: str, vfs_mode: str, 
                 root_folder: str = "/", custom_args: str = "", volname: str = "",
                 process: subprocess.Popen = None):
        super().__init__()
        self.engine = engine
        self.remote = remote
        self.drive_letter = drive_letter
        self.vfs_mode = vfs_mode
        self.root_folder = root_folder
        self.custom_args = custom_args
        self.volname = volname
        self.process = process # 현재 감시 중인 rclone 프로세스 객체
        
        self.is_running = True
        self.check_interval = 5
        self.max_backoff = 30
        self.drive_path = f"{self.drive_letter.upper()}:\\"

    def run(self):
        logger.info(f"Watcher 스레드 시작: {self.remote}")
        
        # 초기 생존 확인 (Race Condition 방지)
        if not self._wait_and_check_alive(wait_sec=5):
            return

        while self.is_running:
            if self._check_connection():
                self.status_changed.emit("Connected")
                self.msleep(self.check_interval * 1000)
            else:
                self.status_changed.emit("Disconnected")
                self._handle_reconnect()

    def _wait_and_check_alive(self, wait_sec=8) -> bool:
        """프로세스가 살아있는지 주기적으로 확인하며 대기합니다."""
        for i in range(wait_sec):
            if not self.is_running: return False
            
            # 프로세스 사후 검증
            if self.process and self.process.poll() is not None:
                _, stderr = self.process.communicate()
                err_msg = stderr.decode('utf-8', errors='ignore').strip()
                self.log_emitted.emit(f"[Error] {self.remote} 프로세스가 즉시 종료됨 (Code: {self.process.returncode})")
                if err_msg: self.log_emitted.emit(f"[Detail] {err_msg[:200]}")
                self.status_changed.emit("Error")
                return False
            
            # 드라이브 확인
            if self._check_drive_exists():
                self.status_changed.emit("Connected")
                return True
                
            self.msleep(1000)
        
        self.log_emitted.emit(f"[Warning] {self.remote} 마운트 명령은 유지 중이나 드라이브가 응답하지 않습니다.")
        return False

    def _check_connection(self) -> bool:
        # 프로세스 생존 확인
        if self.process and self.process.poll() is not None:
            return False
        # 네트워크 및 드라이브 확인
        return self._is_network_available() and self._check_drive_exists()

    def _check_drive_exists(self) -> bool:
        if os.path.exists(self.drive_path) or os.path.exists(self.drive_path.rstrip("\\")):
            return True
        try:
            for p in psutil.disk_partitions():
                if p.mountpoint.upper().startswith(f"{self.drive_letter.upper()}:"):
                    return True
        except: pass
        return False

    def _is_network_available(self) -> bool:
        try:
            socket.setdefaulttimeout(3)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
            return True
        except: return False

    def _handle_reconnect(self):
        backoff = 1
        self.engine.unmount(self.drive_letter)
        
        while self.is_running:
            self.status_changed.emit(f"Reconnecting ({backoff}s...)")
            self.log_emitted.emit(f"[Watcher] {self.remote} 재연결 시도 중...")
            
            # 새 프로세스 생성
            self.process = self.engine.mount(
                self.remote, self.drive_letter, self.vfs_mode, 
                self.root_folder, self.custom_args, self.volname
            )
            
            if self.process and self._wait_and_check_alive(wait_sec=8):
                self.log_emitted.emit(f"[Watcher] {self.remote} 재연결 성공!")
                break
            
            self.msleep(backoff * 1000)
            backoff = min(backoff * 2, self.max_backoff)

    def stop(self):
        self.is_running = False
        self.wait()
