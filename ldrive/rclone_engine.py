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
            # 경로는 따옴표 없이 리스트로 전달하면 OS가 공백을 처리하지만, 
            # 사용자 요청에 따라 인자 처리를 정교하게 검토합니다.
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
        Rclone 마운트를 실행하고 초기 생존 상태를 3초간 집중 검증합니다.
        """
        self.last_err = ""
        drive_path = f"{drive_letter.upper()}:"
        
        # 기실행 중인 마운트 정리
        self.unmount(drive_letter)
        
        remote_path = f"{remote}:" if root_folder == "/" else f"{remote}:{root_folder.lstrip('/')}"
        volume_label = volname if volname else f"L-Drive ({remote})"
        
        # Windows 탐색기 노출을 위한 최적화 옵션 (세션 격리 대응)
        # --winfsp-mount-as-network 를 사용하여 일반 사용자 권한에서도 보이도록 유도
        cmd = [
            self.rclone_path, "mount",
            remote_path, drive_path,
            "--vfs-cache-mode", vfs_mode,
            "--volname", volume_label,
            "--network-mode",
            "--winfsp-mount-as-network",
            "--no-console"
        ]

        if self.rclone_conf_path:
            cmd.extend(["--config", self.rclone_conf_path])

        if custom_args:
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
            
            # 프로세스 초기 상태 진단 (3초 대기)
            time.sleep(3)
            if process.poll() is not None:
                self.last_err = process.stderr.read().strip()
                logger.error(f"마운트 즉시 실패: {self.last_err}")
                return None
            
            self._active_mounts[drive_letter] = process
            return process
            
        except Exception as e:
            self.last_err = str(e)
            logger.error(f"명령 실행 실패: {e}")
            return None

    def is_process_alive(self, drive_letter: str) -> bool:
        if drive_letter not in self._active_mounts: return False
        proc = self._active_mounts[drive_letter]
        if proc.poll() is not None:
            try:
                err_msg = proc.stderr.read().strip()
                if err_msg: self.last_err = err_msg
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
        
        # 시스템에 남은 찌꺼기 정리
        try:
            for p in psutil.process_iter(['name', 'cmdline']):
                if p.info['name'] == 'rclone.exe' and drive_path in (p.info['cmdline'] or []):
                    p.kill()
        except: pass
        return True
