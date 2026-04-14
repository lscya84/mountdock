import subprocess
import os
import logging
import psutil
import time
import shlex
from typing import Dict, List, Optional

logger = logging.getLogger("RcloneEngine")

class RcloneEngine:
    def __init__(self, rclone_path: str = "rclone.exe", rclone_conf_path: str = ""):
        self.rclone_path = rclone_path
        self.rclone_conf_path = rclone_conf_path
        self._active_mounts: Dict[str, subprocess.Popen] = {}
        self.last_error_msg = ""

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
        Rclone 마운트를 실행하고 초기 생존 상태를 철저히 검증합니다.
        """
        self.last_error_msg = ""
        drive_path = f"{drive_letter.upper()}:"
        
        # 이미 관리 중인 프로세스가 있다면 정리
        self.unmount(drive_letter)
        
        remote_path = f"{remote}:" if root_folder == "/" else f"{remote}:{root_folder.lstrip('/')}"
        volume_label = volname if volname else f"L-Drive ({remote})"
        
        # 윈도우에서 가장 안정적인 핵심형 옵션만 사용
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
            cmd.extend(shlex.split(custom_args))

        try:
            logger.info(f"마운트 명령 실행: {' '.join(cmd)}")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
                encoding='utf-8',
                errors='replace'
            )
            
            # 초기 2초간 상태 모니터링 (즉시 사망 여부 확인)
            time.sleep(2)
            if process.poll() is not None:
                # 프로세스가 죽었다면 stderr 캡처
                self.last_error_msg = process.stderr.read().strip()
                logger.error(f"Rclone 즉시 종료됨: {self.last_error_msg}")
                return None
            
            self._active_mounts[drive_letter] = process
            return process
            
        except Exception as e:
            self.last_error_msg = str(e)
            logger.error(f"프로세스 시작 실패: {e}")
            return None

    def is_process_alive(self, drive_letter: str) -> bool:
        if drive_letter not in self._active_mounts:
            return False
        proc = self._active_mounts[drive_letter]
        if proc.poll() is not None:
            try:
                err = proc.stderr.read().strip()
                if err: self.last_error_msg = err
            except: pass
            return False
        return True

    def unmount(self, drive_letter: str) -> bool:
        drive_path = f"{drive_letter.upper()}:"
        
        if drive_letter in self._active_mounts:
            proc = self._active_mounts[drive_letter]
            try:
                parent = psutil.Process(proc.pid)
                for child in parent.children(recursive=True): child.kill()
                parent.kill()
            except: pass
            del self._active_mounts[drive_letter]
        
        # 시스템에 남은 찌꺼기 rclone 강제 정리
        try:
            for p in psutil.process_iter(['name', 'cmdline']):
                if p.info['name'] == 'rclone.exe' and drive_path in (p.info['cmdline'] or []):
                    p.kill()
        except: pass
        
        return True

    def kill_all_mounts(self):
        for drive in list(self._active_mounts.keys()):
            self.unmount(drive)
