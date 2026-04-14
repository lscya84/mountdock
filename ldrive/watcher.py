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
        logger.info(f"Watcher 실행: {self.remote}")
        
        # 1. 초기 마운트 완료 확인
        if not self._wait_for_explorer(timeout=15):
            self.status_changed.emit("Disconnected")
            return

        # 2. 메인 동기화 루프
        while self.is_running:
            if self._check_connection():
                self.status_changed.emit("Connected")
                self.msleep(5000)
            else:
                self.log_emitted.emit(f"[Watcher] {self.remote} 연결 해제됨.")
                self._handle_reconnect()

    def _wait_for_explorer(self, timeout=12) -> bool:
        """ 프로세스 생존과 탐색기 드라이브 실재 여부를 분리하여 진단합니다. """
        for i in range(timeout):
            if not self.is_running: return False
            
            # 프로세스 돌연사 체크
            if not self.engine.is_process_alive(self.drive_letter):
                err = self.engine.last_err
                msg = f"[Error] 마운트 실패: {err[:200]}" if err else "[Error] Rclone 비정상 종료."
                self.log_emitted.emit(msg)
                return False
            
            # 실제 드라이브 확인
            if self._check_drive_exists():
                self.log_emitted.emit(f"[Success] {self.drive_letter}: 탐색기 연결 완료.")
                self.status_changed.emit("Connected")
                return True
            
            # 프로세스는 살아있으나 탐색기에는 없는 경우
            self.status_changed.emit("Waiting Network...")
            self.msleep(1000)
            
        self.log_emitted.emit(f"[Warning] {self.remote} 프로세스는 동작 중이나 탐색기 표시에 실패했습니다 (세션 이슈 가능성)")
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
            self.status_changed.emit(f"Repairing ({backoff}s)")
            success = self.engine.mount(
                self.remote, self.drive_letter, self.vfs_mode, 
                self.root_folder, self.custom_args, self.volname
            )
            
            if success and self._wait_for_explorer(timeout=12):
                break
            
            self.msleep(backoff * 1000)
            backoff = min(backoff * 2, 30)

    def stop(self):
        self.is_running = False
        self.wait()
