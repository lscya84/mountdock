import time
import socket
import os
import logging
import psutil
from PyQt6.QtCore import QThread, pyqtSignal
from ldrive.rclone_engine import RcloneEngine

logger = logging.getLogger("Watcher")

class LDriveWatcher(QThread):
    status_changed = pyqtSignal(str) # UI 카드 상태 업데이트
    log_emitted = pyqtSignal(str)     # 메인 창 로그창 업데이트

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
        
        # 1차 부팅 체크 (최초 마운트 성공 루프)
        if not self._wait_and_check_alive(wait_sec=8):
            return

        while self.is_running:
            if self._check_connection():
                self.status_changed.emit("Connected")
                self.msleep(self.check_interval * 1000)
            else:
                self._handle_reconnect()

    def _wait_and_check_alive(self, wait_sec=10) -> bool:
        """ rclone 프로세스 상태와 드라이브 노출 여부를 동시 검증합니다. """
        for i in range(wait_sec):
            if not self.is_running: return False
            
            # 프로세스 사후 검증
            if not self.engine.is_process_alive(self.drive_letter):
                err = self.engine.last_error
                self.log_emitted.emit(f"[Fatal] {self.remote} rclone 프로세스 종료")
                if err: self.log_emitted.emit(f"Rclone 치명적 오류: {err[:200]}")
                self.status_changed.emit("Error")
                return False
            
            # 드라이브 확인 (os.path + psutil 교차 검증)
            if self._check_drive_exists():
                self.status_changed.emit("Connected")
                return True
            else:
                self.status_changed.emit("Mounting...")
                
            self.msleep(1000)
        
        self.log_emitted.emit(f"[Timeout] {self.remote} 드라이브 발견 실패 ({wait_sec}초 경과)")
        return False

    def _check_connection(self) -> bool:
        # 프로세스 생리 상태 체크
        if not self.engine.is_process_alive(self.drive_letter):
            return False
        # 드라이브 실재 여부 체크
        return self._check_drive_exists()

    def _check_drive_exists(self) -> bool:
        """ OS에 마운트 지점이 성공적으로 열렸는지 확인합니다. """
        if os.path.exists(self.drive_path) or os.path.exists(self.drive_path.rstrip("\\")):
            return True
        # 보조 체크 (psutil)
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
            self.status_changed.emit(f"Repairing ({backoff}s...)")
            self.log_emitted.emit(f"[Repair] {self.remote} 재연결 시도 중...")
            
            res = self.engine.mount(
                self.remote, self.drive_letter, self.vfs_mode, 
                self.root_folder, self.custom_args, self.volname
            )
            
            if res and self._wait_and_check_alive(wait_sec=10):
                self.log_emitted.emit(f"[Success] {self.remote} 재연결 성공!")
                break
            
            self.msleep(backoff * 1000)
            backoff = min(backoff * 2, self.max_backoff)

    def stop(self):
        self.is_running = False
        self.wait()
