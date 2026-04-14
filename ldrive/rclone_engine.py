import subprocess
import os
import logging
import psutil
import time
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
        
        # [사용자 강제 지침] CMD에서 성공한 방식을 그대로 복제 (단일 문자열 + shell=True)
        cmd_str = f'"{self.rclone_path}" mount "{remote_path}" {drive_path} ' \
                  f'--vfs-cache-mode {vfs_mode} ' \
                  f'--volname "{volume_label}" --network-mode ' \
                  f'--config "{self.rclone_conf_path}" --no-console'
        
        if custom_args:
            cmd_str += f" {custom_args}"

        try:
            logger.info(f"마운트 실행 (Shell Mode): {cmd_str}")
            
            # shell=True를 사용하여 CMD 직접 입력과 동일한 환경 제공
            process = subprocess.Popen(
                cmd_str,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
                encoding='utf-8',
                errors='replace',
                shell=True
            )
            
            # 조기 종료 시 0.5초 안에 에러 메시지 캡처
            time.sleep(0.5)
            if process.poll() is not None:
                self.last_err = process.stderr.read().strip()
                logger.error(f"마운트 즉시 실패: {self.last_err}")
                return None
            
            self._active_mounts[drive_letter] = process
            return process
            
        except Exception as e:
            self.last_err = str(e)
            logger.error(f"프로세스 시작 에러: {e}")
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

    def get_remotes(self) -> List[str]:
        try:
            cmd = f'"{self.rclone_path}" listremotes'
            if self.rclone_conf_path:
                cmd += f' --config "{self.rclone_conf_path}"'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                return [line.strip().replace(":", "") for line in result.stdout.splitlines() if line.strip()]
            return []
        except: return []
