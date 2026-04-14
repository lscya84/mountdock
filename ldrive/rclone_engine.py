import subprocess
import os
import logging
import psutil
import time
from typing import Dict, List, Optional

logger = logging.getLogger("RcloneEngine")

class RcloneEngine:
    """
    Rclone 프로세스 생명주기 및 에러 진단 기능이 강화된 엔진입니다.
    """
    def __init__(self, rclone_path: str = "rclone.exe", rclone_conf_path: str = ""):
        self.rclone_path = rclone_path
        self.rclone_conf_path = rclone_conf_path
        self._active_mounts: Dict[str, subprocess.Popen] = {}
        self.last_error = ""

    def set_paths(self, rclone_path: str, rclone_conf_path: str):
        self.rclone_path = rclone_path
        self.rclone_conf_path = rclone_conf_path

    def get_remotes(self) -> List[str]:
        try:
            cmd = [self.rclone_path, "listremotes"]
            if self.rclone_conf_path and os.path.exists(self.rclone_conf_path):
                cmd.extend(["--config", self.rclone_conf_path])
            
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                return [line.strip().replace(":", "") for line in result.stdout.splitlines() if line.strip()]
            return []
        except: return []

    def mount(self, remote: str, drive_letter: str, vfs_mode: str = "full", root_folder: str = "/", custom_args: str = "", volname: str = "") -> Optional[subprocess.Popen]:
        """
        드라이브 마운트 실행 및 1초간의 초기 생존 검증을 수행합니다.
        """
        self.last_error = ""
        drive_path = f"{drive_letter.upper()}:"
        
        # 중복 마운트 체크
        if drive_letter in self._active_mounts:
            if self.is_process_alive(drive_letter):
                logger.warning(f"{drive_letter}: 이미 마운트 중입니다.")
                return self._active_mounts[drive_letter]
        
        # 경로 및 볼륨명 조립
        remote_path = f"{remote}:" if root_folder == "/" else f"{remote}:{root_folder.lstrip('/')}"
        volume_label = volname if volname else f"L-Drive ({remote})"
        
        # 명령어 구성 (Windows 기본 최적화 옵션)
        cmd = [
            self.rclone_path, "mount",
            remote_path, drive_path,
            "--vfs-cache-mode", vfs_mode,
            "--volname", volume_label,
            "--no-console"
        ]

        if self.rclone_conf_path and os.path.exists(self.rclone_conf_path):
            cmd.extend(["--config", self.rclone_conf_path])

        if custom_args:
            import shlex
            cmd.extend(shlex.split(custom_args))

        try:
            logger.info(f"Rclone 마운트 시도: {' '.join(cmd)}")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
                encoding='utf-8',
                errors='replace'
            )
            
            # 즉시 종료 여부 진단 (1초 대기)
            time.sleep(1.2)
            if process.poll() is not None:
                # 프로세스가 죽었다면 에러 원인 읽기
                self.last_error = process.stderr.read().strip()
                logger.error(f"Rclone 치명적 오류 (Code {process.returncode}): {self.last_error}")
                return None
            
            self._active_mounts[drive_letter] = process
            return process
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"마운트 실행 중 예외 발생: {e}")
            return None

    def is_process_alive(self, drive_letter: str) -> bool:
        """ rclone 프로세스의 상태를 확인합니다. """
        if drive_letter not in self._active_mounts:
            return False
        proc = self._active_mounts[drive_letter]
        if proc.poll() is not None:
            # 보관된 에러 메시지 업데이트 시도
            try:
                err_data = proc.stderr.read().strip()
                if err_data: self.last_error = err_data
            except: pass
            return False
        return True

    def unmount(self, drive_letter: str) -> bool:
        """ 드라이브 마운트를 해제하고 강제 종료를 수행합니다. """
        drive_path = f"{drive_letter.upper()}:"
        
        # 1. 관리 중인 프로세스 트리 종료
        if drive_letter in self._active_mounts:
            proc = self._active_mounts[drive_letter]
            try:
                parent = psutil.Process(proc.pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
            except: pass
            del self._active_mounts[drive_letter]
        
        # 2. 잔류 rclone.exe 정리 (명령어 인수 대조)
        try:
            for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                if p.info['name'] == 'rclone.exe':
                    cmd_line = p.info['cmdline'] or []
                    if drive_path in cmd_line:
                        psutil.Process(p.info['pid']).kill()
        except: pass
        
        return True

    def kill_all_mounts(self):
        for drive in list(self._active_mounts.keys()):
            self.unmount(drive)
