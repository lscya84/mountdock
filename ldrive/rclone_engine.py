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
        Windows 세션 격리 방지를 위한 고급 마운트 로직.
        """
        self.last_err = ""
        drive_path = f"{drive_letter.upper()}:"
        self.unmount(drive_letter)
        
        remote_path = f"{remote}:" if root_folder == "/" else f"{remote}:{root_folder.lstrip('/')}"
        volume_label = volname if volname else f"L-Drive ({remote})"
        
        # [핵심] 탐색기 표시 보장을 위한 네트워크 모드 강제 및 따옴표 처리
        cmd = [
            f'"{self.rclone_path}"', 
            "mount",
            f'"{remote_path}"', 
            f'"{drive_path}"',
            "--vfs-cache-mode", vfs_mode,
            "--volname", f'"{volume_label}"',
            "--network-mode",
            "--winfsp-mount-as-network",
            "--no-console"
        ]

        if self.rclone_conf_path:
            cmd.extend(["--config", f'"{self.rclone_conf_path}"'])

        if custom_args:
            cmd.extend(shlex.split(custom_args))

        try:
            # shell=False를 유지하되 전체 커맨드 문자열로 실행하여 따옴표 보존
            full_cmd = " ".join(cmd)
            logger.info(f"마운트 명령 실행: {full_cmd}")
            
            process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
                encoding='utf-8',
                errors='replace'
            )
            
            # 초기 3초 생존 검사
            time.sleep(3)
            if process.poll() is not None:
                self.last_err = process.stderr.read().strip()
                logger.error(f"마운트 즉시 실패: {self.last_err}")
                return None
            
            self._active_mounts[drive_letter] = process
            return process
            
        except Exception as e:
            self.last_err = str(e)
            logger.error(f"실행 예외: {e}")
            return None

    def is_process_alive(self, drive_letter: str) -> bool:
        if drive_letter not in self._active_mounts: return False
        proc = self._active_mounts[drive_letter]
        if proc.poll() is not None:
            try:
                err = proc.stderr.read().strip()
                if err: self.last_err = err
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
        
        try:
            for p in psutil.process_iter(['name', 'cmdline']):
                if p.info['name'] == 'rclone.exe' and drive_path in (p.info['cmdline'] or []):
                    p.kill()
        except: pass
        return True
