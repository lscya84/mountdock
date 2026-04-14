import subprocess
import os
import logging
import psutil
import signal
from typing import Dict, List, Optional

logger = logging.getLogger("RcloneEngine")

class RcloneEngine:
    """
    Rclone 바이너리 제어 및 마운트 프로세스의 생명주기를 관리하는 엔진 클래스입니다.
    프로세스 실행, 모니터링, 안전한 종료 기능을 제공합니다.
    """

    def __init__(self, rclone_path: str = "rclone.exe", rclone_conf_path: str = ""):
        self.rclone_path = rclone_path
        self.rclone_conf_path = rclone_conf_path
        self._active_mounts: Dict[str, subprocess.Popen] = {}
        
        self.check_binary()

    def set_paths(self, rclone_path: str, rclone_conf_path: str):
        """전역 Rclone 바이너리 및 설정 파일 경로를 업데이트합니다."""
        self.rclone_path = rclone_path
        self.rclone_conf_path = rclone_conf_path
        self.check_binary()

    def check_binary(self) -> bool:
        """
        rclone.exe 바이너리가 지정된 경로 또는 시스템 PATH 상에 존재하는지 확인합니다.
        
        Returns:
            bool: 존재 여부
        """
        try:
            # 1. 명시적 경로 확인
            if os.path.exists(self.rclone_path):
                logger.info(f"Rclone 바이너리 발견: {os.path.abspath(self.rclone_path)}")
                return True
            
            # 2. 시스템 PATH 확인 (where 명령어 사용)
            result = subprocess.run(["where", "rclone"], capture_output=True, text=True)
            if result.returncode == 0:
                self.rclone_path = result.stdout.splitlines()[0].strip()
                logger.info(f"시스템 PATH에서 Rclone 바이너리 발견: {self.rclone_path}")
                return True
            
            logger.warning("Rclone 바이너리를 찾을 수 없습니다.")
            return False
        except Exception as e:
            logger.error(f"바이너리 체크 중 오류 발생: {e}")
            return False

    def get_remotes(self) -> List[str]:
        """
        rclone config에 등록된 리모트 목록을 가져옵니다.
        """
        try:
            cmd = [self.rclone_path, "listremotes"]
            if self.rclone_conf_path and os.path.exists(self.rclone_conf_path):
                cmd.extend(["--config", self.rclone_conf_path])
            
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                remotes = [line.strip().replace(":", "") for line in result.stdout.splitlines() if line.strip()]
                return remotes
            return []
        except Exception as e:
            logger.error(f"리모트 목록 로드 실패: {e}")
            return []

    def mount(self, remote: str, drive_letter: str, vfs_mode: str = "full", root_folder: str = "/", custom_args: str = "", volname: str = "") -> subprocess.Popen:
        """
        지정된 리모트를 특정 드라이브 문자로 마운트합니다.
        프로세스 객체를 반환하여 외부에서 상태를 모니터링할 수 있게 합니다.
        """
        if drive_letter in self._active_mounts:
            logger.warning(f"{drive_letter}: 이미 마운트 중입니다.")
            return None

        drive_path = f"{drive_letter.upper()}:"
        
        # remote_path 조립
        if root_folder == "/":
            remote_path = f"{remote}:"
        else:
            clean_root = root_folder.lstrip("/")
            remote_path = f"{remote}:{clean_root}"
        
        volume_label = volname if volname else f"L-Drive ({remote})"
        
        # 윈도우에서 가장 안정적인 기본형 명령어로 원복
        cmd = [
            self.rclone_path, "mount",
            remote_path, drive_path,
            "--vfs-cache-mode", vfs_mode,
            "--volname", volume_label,
            "--no-console"
        ]

        if self.rclone_conf_path and os.path.exists(self.rclone_conf_path):
            cmd.extend(["--config", self.rclone_conf_path])

        # 커스텀 인자 추가 (공백으로 분리)
        if custom_args:
            import shlex
            try:
                extra_args = shlex.split(custom_args)
                cmd.extend(extra_args)
            except Exception as e:
                logger.error(f"커스텀 인자 파싱 오류: {e}")

        logger.info(f"마운트 시도: {' '.join(cmd)}")

        try:
            # Windows에서 콘솔 창이 뜨지 않도록 실행
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
                encoding='utf-8',
                errors='replace'
            )
            
            self._active_mounts[drive_letter] = process
            logger.info(f"마운트 프로세스 시작됨 (PID: {process.pid})")
            return True
        except Exception as e:
            logger.error(f"마운트 실행 중 오류 발생: {e}")
            return False

    def unmount(self, drive_letter: str) -> bool:
        """
        지정된 드라이브의 마운트를 해제하고 관련 프로세스를 종료합니다.
        
        Args:
            drive_letter (str): 해제할 드라이브 문자
        """
        if drive_letter not in self._active_mounts:
            # 추적 중인 프로세스가 없더라도 시스템에서 rclone.exe가 마운트 중일 수 있으므로 강제 검색 시도
            return self._kill_rclone_by_mount_path(drive_letter)

        process = self._active_mounts[drive_letter]
        success = self._terminate_process_tree(process.pid)
        
        if success:
            del self._active_mounts[drive_letter]
            logger.info(f"{drive_letter}: 드라이브 마운트가 해제되었습니다.")
        
        return success

    def _terminate_process_tree(self, pid: int) -> bool:
        """
        psutil을 사용하여 특정 PID와 그 자식 프로세스까지 모두 종료합니다.
        """
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            
            # 자식 프로세스 먼저 종료
            for child in children:
                child.terminate()
            
            # 부모 프로세스 종료
            parent.terminate()
            
            # 잠시 대기 후 살아있으면 강제 종료
            gone, alive = psutil.wait_procs(children + [parent], timeout=3)
            for survivor in alive:
                survivor.kill()
                
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return True # 이미 없거나 권한 없음 (종료된 것으로 간주)
        except Exception as e:
            logger.error(f"프로세스 트리 종료 중 오류 발생: {e}")
            return False

    def _kill_rclone_by_mount_path(self, drive_letter: str) -> bool:
        """
        추적되지 않는 rclone.exe 프로세스를 명령어 인자(드라이브 경로)를 보고 찾아 종료합니다.
        """
        drive_path = f"{drive_letter.upper()}:"
        found = False
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['name'] == 'rclone.exe':
                    cmdline = proc.info['cmdline']
                    if cmdline and drive_path in cmdline:
                        logger.info(f"좀비 rclone 프로세스 발견 및 종료 (PID: {proc.info['pid']}, Path: {drive_path})")
                        self._terminate_process_tree(proc.info['pid'])
                        found = True
            return found
        except Exception as e:
            logger.error(f"좀비 프로세스 정리 중 오류 발생: {e}")
            return False

    def kill_all_mounts(self):
        """프로그램 종료 시 모든 마운트 프로세스를 정리합니다."""
        for drive in list(self._active_mounts.keys()):
            self.unmount(drive)
        
        # 남은 모든 rclone.exe 강제 종료 (선택 사항 - 다른 rclone 사용 시 주의)
        # self._kill_all_rclone_processes()

    def _kill_all_rclone_processes(self):
        """시스템의 모든 rclone.exe 프로세스를 강제 종료합니다."""
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] == 'rclone.exe':
                proc.kill()

if __name__ == "__main__":
    # 테스트 코드
    engine = RcloneEngine()
    print(f"Remotes: {engine.get_remotes()}")
