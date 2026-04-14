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
        self.last_err = ""

    def set_paths(self, rclone_path: str, rclone_conf_path: str):
        self.rclone_path = rclone_path
        self.rclone_conf_path = rclone_conf_path

    def mount(self, remote: str, drive_letter: str, vfs_mode: str = "full", root_folder: str = "/", custom_args: str = "", volname: str = "") -> Optional[subprocess.Popen]:
        self.last_err = ""
        drive_path = f"{drive_letter.upper()}:"
        self.unmount(drive_letter)
        
        remote_path = f"{remote}:" if root_folder == "/" else f"{remote}:{root_folder.lstrip('/')}"
        volume_label = volname if volname else f"L-Drive ({remote})"
        
        # [사용자 강제 지침] CMD 환경과 완벽히 동일한 실행을 위해 단일 문자열 커맨드 조립
        # 따옴표 핸들링을 수동으로 수행하여 shell=True 환경에서의 호환성 극대화
        cmd_str = f'"{self.rclone_path}" mount "{remote_path}" {drive_path} ' \
                  f'--vfs-cache-mode {vfs_mode} ' \
                  f'--volname "{volume_label}" ' \
                  f'--config "{self.rclone_conf_path}" ' \
                  f'--no-console --network-mode'
        
        if custom_args:
            cmd_str += f" {custom_args}"

        try:
            logger.info(f"Rclone 단일 문자열 실행: {cmd_str}")
            
            # shell=True 및 CREATE_NEW_CONSOLE 적용
            process = subprocess.Popen(
                cmd_str,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP,
                encoding='utf-8',
                errors='replace',
                shell=True
            )
            
            # 프로세스 안정화 대기 및 조기 종료 체크 (3초)
            time.sleep(3)
            if process.poll() is not None:
                self.last_err = process.stderr.read().strip()
                logger.error(f"마운트 즉시 에러: {self.last_err}")
                return None
            
            self._active_mounts[drive_letter] = process
            return process
            
        except Exception as e:
            self.last_err = str(e)
            logger.error(f"Popen 예외 발생: {e}")
            return None

    def is_process_alive(self, drive_letter: str) -> bool:
        if drive_letter not in self._active_mounts: return False
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
        
        # 시스템에 남은 rclone.exe 정리 (정확한 드라이브 문자 대조)
        try:
            for p in psutil.process_iter(['name', 'cmdline']):
                if p.info['name'] == 'rclone.exe' and drive_path in (p.info['cmdline'] or []):
                    p.kill()
        except: pass
        return True
    
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
