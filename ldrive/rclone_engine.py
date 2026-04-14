import subprocess
import os
import logging
import psutil
import time
import shlex
import ctypes
from typing import Dict, List, Optional

logger = logging.getLogger("RcloneEngine")

class RcloneEngine:
    def __init__(self, rclone_path: str = "rclone.exe", rclone_conf_path: str = ""):
        self.rclone_path = rclone_path
        self.rclone_conf_path = rclone_conf_path
        self._active_mounts: Dict[str, subprocess.Popen] = {}
        self.last_err = ""

    def set_paths(self, rclone_path: str, rclone_conf_path: str):
        self.rclone_path = rclone_path
        self.rclone_conf_path = rclone_conf_path

    def is_admin(self):
        try: return ctypes.windll.shell32.IsUserAnAdmin()
        except: return False

    def get_remotes(self) -> List[str]:
        try:
            cmd = [self.rclone_path, "listremotes"]
            if self.rclone_conf_path:
                cmd.extend(["--config", self.rclone_conf_path])
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                return [line.strip().replace(":", "") for line in result.stdout.splitlines() if line.strip()]
            return []
        except: return []

    def mount(self, remote: str, drive_letter: str, vfs_mode: str = "full", root_folder: str = "/", custom_args: str = "", volname: str = "") -> Optional[subprocess.Popen]:
        """
        Rclone 마운트를 실행하고 초기 상태를 정밀 진단합니다.
        """
        self.last_err = ""
        drive_path = f"{drive_letter.upper()}:"
        
        # 기실행 중인 동일 드라이브 정리
        self.unmount(drive_letter)
        
        remote_path = f"{remote}:" if root_folder == "/" else f"{remote}:{root_folder.lstrip('/')}"
        volume_label = volname if volname else f"L-Drive ({remote})"
        
        # 네이티브 윈도우 환경 최적화 옵션
        cmd = [
            self.rclone_path, "mount",
            remote_path, drive_path,
            "--vfs-cache-mode", vfs_mode,
            "--volname", volume_label,
            "--network-mode", # 세션 격리 방지
            "--no-console"
        ]

        if self.is_admin():
            cmd.append("--winfsp-mount-as=admin")

        if self.rclone_conf_path:
            cmd.extend(["--config", self.rclone_conf_path])

        if custom_args:
            cmd.extend(shlex.split(custom_args))

        try:
            logger.info(f"마운트 시도: {' '.join(cmd)}")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
                encoding='utf-8',
                errors='replace'
            )
            
            # 초기 2초간 생사 확인 (즉시 종료 대응)
            time.sleep(2.5)
            if process.poll() is not None:
                self.last_err = process.stderr.read().strip()
                logger.error(f"마운트 즉시 실패: {self.last_err}")
                return None
            
            self._active_mounts[drive_letter] = process
            return process
            
        except Exception as e:
            self.last_err = str(e)
            logger.error(f"마운트 실행 중 예외: {e}")
            return None

    def is_process_alive(self, drive_letter: str) -> bool:
        if drive_letter not in self._active_mounts:
            return False
        proc = self._active_mounts[drive_letter]
        if proc.poll() is not None:
            try:
                msg = proc.stderr.read().strip()
                if msg: self.last_err = msg
            except: pass
            return False
        return True

    def unmount(self, drive_letter: str) -> bool:
        drive_path = f"{drive_letter.upper()}:"
        if drive_letter in self._active_mounts:
            proc = self._active_mounts[drive_letter]
            try:
                p = psutil.Process(proc.pid)
                for child in p.children(recursive=True): child.kill()
                p.kill()
            except: pass
            del self._active_mounts[drive_letter]
        
        # 잔류 프로세스 강제 클린업
        try:
            for p in psutil.process_iter(['name', 'cmdline']):
                if p.info['name'] == 'rclone.exe' and drive_path in (p.info['cmdline'] or []):
                    p.kill()
        except: pass
        return True
