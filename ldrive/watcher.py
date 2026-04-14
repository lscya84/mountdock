import time
import socket
import os
import logging
from PySide6.QtCore import QThread, Signal as pyqtSignal
from ldrive.rclone_engine import RcloneEngine

logger = logging.getLogger("Watcher")

class LDriveWatcher(QThread):
    """
    네트워크 상태와 마운트된 드라이브의 연결성을 실시간으로 감시하고,
    연결이 끊겼을 때 스마트 재연결(Exponential Backoff)을 수행하는 스레드 클래스입니다.
    """
    
    # UI 업데이트를 위한 시그널 정의
    status_changed = pyqtSignal(str)     # 상태 메시지 (예: "Connected", "Reconnecting...")
    log_emitted = pyqtSignal(str)        # 로그 메시지 (UI 로그 뷰어용)

    def __init__(self, engine: RcloneEngine, remote: str, drive_letter: str, vfs_mode: str):
        super().__init__()
        self.engine = engine
        self.remote = remote
        self.drive_letter = drive_letter
        self.vfs_mode = vfs_mode
        
        self.is_running = True
        self.check_interval = 5  # 정상 상태일 때 체크 주기 (초)
        self.max_backoff = 30    # 재연결 최대 대기 시간 (초)
        
        self.drive_path = f"{self.drive_letter.upper()}:\\"

    def run(self):
        """
        스레드 실행 루프: 네트워크와 드라이브 상태를 주기적으로 확인합니다.
        """
        logger.info(f"Watcher 스레드 시작: {self.remote} -> {self.drive_path}")
        self.log_emitted.emit(f"[Watcher] 감시 시작: {self.remote} -> {self.drive_path}")
        
        while self.is_running:
            if self._check_connection():
                # 연결 상태가 양호하면 대기
                self.status_changed.emit("Connected")
                self.msleep(self.check_interval * 1000)
            else:
                # 연결이 끊겼거나 드라이브에 접근 불가한 경우 재연결 시도
                self.status_changed.emit("Disconnected")
                self.log_emitted.emit(f"[Watcher] 연결 끊김 감지! 재연결을 시도합니다.")
                self._handle_reconnect()
    
    def _check_connection(self) -> bool:
        """
        네트워크와 드라이브 상태를 모두 확인합니다.
        """
        # 1. 네트워크 확인 (Google DNS 8.8.8.8:53 연결 테스트)
        network_ok = self._is_network_available()
        
        # 2. 드라이브 접근 확인
        drive_ok = os.path.exists(self.drive_path)
        
        return network_ok and drive_ok

    def _is_network_available(self, host="8.8.8.8", port=53, timeout=3) -> bool:
        """소켓을 사용하여 네트워크 연결 여부를 확인합니다."""
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except Exception:
            return False

    def _handle_reconnect(self):
        """
        지수 백오프(Exponential Backoff) 로직을 적용하여 재연결을 시도합니다.
        """
        backoff = 1  # 시작 대기 시간 (1초)
        
        # 재연결 전 기존 프로세스 정리
        self.engine.unmount(self.drive_letter)
        
        while self.is_running:
            self.status_changed.emit(f"Reconnecting ({backoff}s...)")
            self.log_emitted.emit(f"[Watcher] {self.remote} 마운트 재시도 중... (대기: {backoff}초)")
            
            # 마운트 시도
            success = self.engine.mount(self.remote, self.drive_letter, self.vfs_mode)
            
            if success:
                # 마운트 명령어 실행 직후 바로 접근 가능한 것은 아니므로 잠시 대기
                self.msleep(2000)
                if os.path.exists(self.drive_path):
                    self.log_emitted.emit(f"[Watcher] {self.remote} 재연결 성공!")
                    self.status_changed.emit("Connected")
                    break
            
            # 실패 시 지수 백오프 적용
            self.msleep(backoff * 1000)
            backoff = min(backoff * 2, self.max_backoff)
            
            # 네트워크가 여전히 끊겨 있다면 백오프 진행 전에 네트워크 확인 루프를 돌 수도 있음
            if not self._is_network_available():
                self.log_emitted.emit("[Watcher] 네트워크 연결이 없습니다. 대기 중...")

    def stop(self):
        """감시 스레드를 안전하게 종료합니다."""
        self.is_running = False
        self.wait() # 스레드가 끝날 때까지 대기
        logger.info("Watcher 스레드가 중지되었습니다.")
