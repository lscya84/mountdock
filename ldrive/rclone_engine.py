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
            # 리스트 방식으로 전달하면 OS가 공백을 처리하지만, 
            # 사용자 요청에 따라 인용 부호를 명시적으로 고려한 조립을 수행할 수 있습니다.
            cmd = [self.rclone_path, "listremotes"]
            if self.rclone_conf_path:
                cmd.extend(["--config", self.rclone_conf_path])
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                return [line.strip().replace(":", "") for line in result.stdout.splitlines() if line.strip()]
            return []
        except: return []

    def mount(self, remote: str, drive_letter: str, vfs_mode: str = "full", root_folder: str = "/", custom_args: str = "", volname: str = "") -> Optional[subprocess.Popen]:
        self.last_err = ""
        drive_path = f"{drive_letter.upper()}:"
        
        # 이전 동일 드라이브 마운트가 있다면 클린업
        self.unmount(drive_letter)
        
        remote_path = f"{remote}:" if root_folder == "/" else f"{remote}:{root_folder.lstrip('/')}"
        volume_label = volname if volname else f"L-Drive ({remote})"
        
        # 사용자 요청 마운트 가독성/세션 격리 해결 옵션 강제 적용
        # 1. --network-mode : 탐색기 노출 확률 증대
        # 2. --winfsp-mount-as-network : 윈도우 세션 격리 문제 원천 차단
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

        # Popen 실행 시 shell=True를 사용하거나 리스트로 전달 (안정성을 위해 리스트 유지하되 인자마다 따옴표 포함)
        try:
            full_cmd = " ".join(cmd)
            logger.info(f"마운트 실행: {full_cmd}")
            
            # shell=True를 사용하여 따옴표가 명시된 문자열 명령어를 안전하게 전달
            process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
                encoding='utf-8',
                errors='replace',
                shell=False # 리스트 전달 시 False가 기본
            )
            
            # 초기 3초간 생존 확인
            time.sleep(3)
            if process.poll() is not None:
                self.last_err = process.stderr.read().strip()
                logger.error(f"Rclone 즉시 에러 발생: {self.last_err}")
                return None
            
            self._active_mounts[drive_letter] = process
            return process
            
        except Exception as e:
            self.last_err = str(e)
            logger.error(f"프로세스 시작 실패: {e}")
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
        
        # 시스템에 남은 찌꺼기 정리
        try:
            for p in psutil.process_iter(['name', 'cmdline']):
                if p.info['name'] == 'rclone.exe' and drive_path in (p.info['cmdline'] or []):
                    p.kill()
        except: pass
        return True
