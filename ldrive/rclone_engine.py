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
        self.last_stderr = ""

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

    def is_admin(self):
        try: return ctypes.windll.shell32.IsUserAnAdmin()
        except: return False

    def mount(self, remote: str, drive_letter: str, vfs_mode: str = "full", root_folder: str = "/", custom_args: str = "", volname: str = "") -> Optional[subprocess.Popen]:
        self.last_stderr = ""
        drive_path = f"{drive_letter.upper()}:"
        self.unmount(drive_letter)
        
        remote_path = f"{remote}:" if root_folder == "/" else f"{remote}:{root_folder.lstrip('/')}"
        volume_label = volname if volname else f"L-Drive ({remote})"
        
        # Windows 마운트 가독성 및 세션 격리 방지를 위한 고급 옵션
        # 1. --network-mode: 네트워크 드라이브로 인식시켜 모든 세션에서 보일 확률을 높임
        # 2. --winfsp-mount-as : 관리자 권한 실행 시 강제로 소유권 설정
        cmd = [
            self.rclone_path, "mount",
            remote_path, drive_path,
            "--vfs-cache-mode", vfs_mode,
            "--volname", volume_label,
            "--network-mode",
            "--no-console"
        ]

        if self.is_admin():
            # 관리자 권한으로 실행 중일 때 rclone이 explorer에 나타나지 않는 문제를 해결
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
            
            # 프로세스가 즉시 죽는지 확인 (3초)
            time.sleep(3)
            if process.poll() is not None:
                self.last_stderr = process.stderr.read().strip()
                logger.error(f"Rclone 마운트 실패: {self.last_stderr}")
                return None
            
            self._active_mounts[drive_letter] = process
            return process
            
        except Exception as e:
            self.last_stderr = str(e)
            logger.error(f"마운트 도중 예외: {e}")
            return None

    def is_process_alive(self, drive_letter: str) -> bool:
        if drive_letter not in self._active_mounts:
            return False
        proc = self._active_mounts[drive_letter]
        if proc.poll() is not None:
            try:
                err = proc.stderr.read().strip()
                if err: self.last_stderr = err
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

    def kill_all_mounts(self):
        for drive in list(self._active_mounts.keys()):
            self.unmount(drive)
