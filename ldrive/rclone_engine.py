import logging
import os
import subprocess
import time
from typing import Dict, List, Optional

import psutil

logger = logging.getLogger("RcloneEngine")


class RcloneEngine:
    def __init__(self, rclone_path: str = "rclone.exe", rclone_conf_path: str = ""):
        self.rclone_path = rclone_path
        self.rclone_conf_path = rclone_conf_path
        self._active_mounts: Dict[str, subprocess.Popen] = {}
        self.last_err = ""

    @property
    def last_error(self) -> str:
        return self.last_err

    def set_paths(self, rclone_path: str, rclone_conf_path: str):
        self.rclone_path = rclone_path
        self.rclone_conf_path = rclone_conf_path

    def mount(
        self,
        remote: str,
        drive_letter: str,
        vfs_mode: str = "full",
        root_folder: str = "/",
        custom_args: str = "",
        volname: str = "",
    ) -> Optional[subprocess.Popen]:
        self.last_err = ""
        letter = drive_letter.upper().replace(":", "")
        drive_path = f"{letter}:"
        self.unmount(letter)

        remote_name = remote[:-1] if remote.endswith(":") else remote
        remote_path = f"{remote_name}:" if root_folder == "/" else f"{remote_name}:{root_folder.lstrip('/')}"
        volume_label = volname.strip() if volname.strip() else f"L-Drive ({remote_name})"

        cmd = [
            self.rclone_path,
            "mount",
            remote_path,
            drive_path,
            "--vfs-cache-mode",
            vfs_mode,
            "--volname",
            volume_label,
        ]

        if self.rclone_conf_path:
            cmd.extend(["--config", self.rclone_conf_path])

        if custom_args.strip():
            cmd.extend(self._split_custom_args(custom_args))

        logger.info("마운트 실행: %s", subprocess.list2cmdline(cmd))

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
                shell=False,
            )

            time.sleep(1.2)
            if process.poll() is not None:
                stdout, stderr = process.communicate(timeout=1)
                self.last_err = (stderr or stdout or "rclone mount exited immediately").strip()
                logger.error("마운트 즉시 실패: %s", self.last_err)
                return None

            self._active_mounts[letter] = process
            return process
        except Exception as exc:
            self.last_err = str(exc)
            logger.error("마운트 프로세스 시작 실패: %s", exc)
            return None

    def is_process_alive(self, drive_letter: str) -> bool:
        letter = drive_letter.upper().replace(":", "")
        proc = self._active_mounts.get(letter)
        if not proc:
            return False

        if proc.poll() is not None:
            try:
                stdout, stderr = proc.communicate(timeout=1)
                self.last_err = (stderr or stdout or "").strip()
            except Exception:
                pass
            self._active_mounts.pop(letter, None)
            return False
        return True

    def unmount(self, drive_letter: str) -> bool:
        letter = drive_letter.upper().replace(":", "")
        drive_path = f"{letter}:"

        proc = self._active_mounts.pop(letter, None)
        if proc is not None:
            self._kill_process_tree(proc.pid)

        try:
            for process in psutil.process_iter(["name", "cmdline"]):
                cmdline = process.info.get("cmdline") or []
                if process.info.get("name", "").lower() == "rclone.exe" and drive_path in cmdline:
                    self._kill_process_tree(process.pid)
        except Exception:
            pass
        return True

    def get_remotes(self) -> List[str]:
        cmd = [self.rclone_path, "listremotes"]
        if self.rclone_conf_path:
            cmd.extend(["--config", self.rclone_conf_path])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False)
            if result.returncode == 0:
                return [line.strip().rstrip(":") for line in result.stdout.splitlines() if line.strip()]
            self.last_err = (result.stderr or result.stdout or "failed to list remotes").strip()
            logger.error("리모트 목록 로드 실패: %s", self.last_err)
            return []
        except Exception as exc:
            self.last_err = str(exc)
            logger.error("리모트 목록 로드 실패: %s", exc)
            return []

    def kill_all_mounts(self):
        for drive_letter in list(self._active_mounts.keys()):
            self.unmount(drive_letter)

    def _kill_process_tree(self, pid: int):
        try:
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
        except Exception:
            pass

    def _split_custom_args(self, custom_args: str) -> List[str]:
        import shlex

        try:
            return shlex.split(custom_args, posix=False)
        except ValueError:
            return custom_args.split()
