import subprocess
import os
import logging
import psutil
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("RcloneEngine")

class RcloneEngine:
    def __init__(self, rclone_path: str = "rclone.exe", rclone_conf_path: str = ""):
        self.rclone_path = rclone_path
        self.rclone_conf_path = rclone_conf_path
        self._active_mounts: Dict[str, subprocess.Popen] = {}
        self.last_error = "" # 마지막 에러 메시지 저장용

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
        리모트 마운트 실행 및 즉시 실패 여부 검증
        """
        self.last_error = ""
        drive_path = f"{drive_letter.upper()}:"
        
        if drive_letter in self._active_mounts:
            if self.is_process_alive(drive_letter):
                return self._active_mounts[drive_letter]
        
        # remote_path 조립
        remote_path = f"{remote}:" if root_folder == "/" else f"{remote}:{root_folder.lstrip('/')}"
        volume_label = volname if volname else f"L-Drive ({remote})"
        
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
            
            # 즉시 종료 여부 확인 (1초 대기)
            time.sleep(1.5)
            if process.poll() is not None:
                self.last_error = process.stderr.read().strip()
                logger.error(f"Rclone 즉시 종료됨 (Code {process.returncode}): {self.last_error}")
                return None
            
            self._active_mounts[drive_letter] = process
            return process
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"마운트 실행 중 예외 발생: {e}")
            return None

    def is_process_alive(self, drive_letter: str) -> bool:
        if drive_letter not in self._active_mounts:
            return False
        proc = self._active_mounts[drive_letter]
        if proc.poll() is not None:
            # 죽어있는 걸 발견하면 로그 확인 후 제거
            try:
                err = proc.stderr.read().strip()
                if err: self.last_error = err
            except: pass
            return False
        return True

    def unmount(self, drive_letter: str) -> bool:
        drive_path = f"{drive_letter.upper()}:"
        
        # 1. 추적 중인 프로세스 종료
        if drive_letter in self._active_mounts:
            proc = self._active_mounts[drive_letter]
            try:
                parent = psutil.Process(proc.pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
            except: pass
            del self._active_mounts[drive_letter]
        
        # 2. 잔류 rclone.exe 강제 정리 (명령어 대조)
        try:
            for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                if p.info['name'] == 'rclone.exe' and drive_path in (p.info['cmdline'] or []):
                    psutil.Process(p.info['pid']).kill()
        except: pass
        
        logger.info(f"{drive_path} 마운트 해제 완료")
        return True

    def kill_all_mounts(self):
        for drive in list(self._active_mounts.keys()):
            self.unmount(drive)
