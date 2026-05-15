import ctypes
import logging
import os
import subprocess

import psutil
from PyQt6.QtCore import QThread, pyqtSignal

from mountdock.i18n import tr
from mountdock.rclone_engine import RcloneEngine

logger = logging.getLogger("Watcher")

DRIVE_UNKNOWN = 0
DRIVE_NO_ROOT_DIR = 1
ACCESS_PROBE_TIMEOUT_SECONDS = 3


def _hidden_subprocess_kwargs():
    if os.name != "nt":
        return {}
    startupinfo_class = getattr(subprocess, "STARTUPINFO", None)
    if startupinfo_class is None:
        return {}
    startupinfo = startupinfo_class()
    startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        "startupinfo": startupinfo,
    }


class LDriveWatcher(QThread):
    status_changed = pyqtSignal(str)
    log_emitted = pyqtSignal(str)

    def __init__(
        self,
        engine: RcloneEngine,
        remote: str,
        drive_letter: str,
        vfs_mode: str,
        root_folder: str = "/",
        custom_args: str = "",
        volname: str = "",
        cache_dir: str = "",
        lang: str = "en",
    ):
        super().__init__()
        self.engine = engine
        self.remote = remote
        self.drive_letter = drive_letter.upper().replace(":", "")
        self.vfs_mode = vfs_mode
        self.root_folder = root_folder
        self.custom_args = custom_args
        self.volname = volname
        self.cache_dir = cache_dir
        self.lang = lang
        self.is_running = True
        self.drive_path = f"{self.drive_letter}:\\"

    def run(self):
        logger.info("Watcher Starting: %s", self.remote)
        self.status_changed.emit("Starting")

        if not self._strict_wait_for_mount(timeout=45):
            self.status_changed.emit("Disconnected")
            return

        while self.is_running:
            if self._check_connection():
                self.status_changed.emit("Connected")
                self.msleep(5000)
            else:
                self.log_emitted.emit(tr(self.lang, "log_watcher_connection_lost", drive=self.drive_letter))
                self._handle_reconnect()

    def _strict_wait_for_mount(self, timeout: int = 45) -> bool:
        for attempt in range(timeout):
            if not self.is_running:
                return False

            if not self.engine.is_process_alive(self.drive_letter):
                err = self.engine.last_error
                message = (
                    tr(self.lang, "log_mount_failed", message=err[:500])
                    if err
                    else tr(self.lang, "log_rclone_exited")
                )
                self.log_emitted.emit(message)
                return False

            if self._check_drive_ready():
                self.log_emitted.emit(tr(self.lang, "log_drive_mounted", drive=self.drive_letter))
                self.status_changed.emit("Connected")
                return True

            self.status_changed.emit("Mounting")
            self.msleep(1000)

        self.log_emitted.emit(
            tr(
                self.lang,
                "log_mount_timeout",
                drive=self.drive_letter,
                drive_type=self._get_drive_type(),
                exists=self._check_drive_exists(),
            )
        )
        return False

    def _check_connection(self) -> bool:
        return self.engine.is_process_alive(self.drive_letter) and self._check_drive_ready()

    def _check_drive_ready(self) -> bool:
        if not self._check_drive_exists():
            return False

        drive_type = self._get_drive_type()
        if drive_type in (DRIVE_UNKNOWN, DRIVE_NO_ROOT_DIR):
            try:
                return os.path.isdir(self.drive_path)
            except OSError:
                return False

        return self._probe_drive_access()

    def _check_drive_exists(self) -> bool:
        if os.path.exists(self.drive_path):
            return True
        try:
            for partition in psutil.disk_partitions():
                if partition.mountpoint.upper().startswith(f"{self.drive_letter}:"):
                    return True
        except Exception:
            pass
        return False

    def _get_drive_type(self) -> int:
        try:
            return ctypes.windll.kernel32.GetDriveTypeW(self.drive_path)
        except Exception:
            return DRIVE_UNKNOWN

    def _probe_drive_access(self) -> bool:
        if os.name != "nt":
            try:
                return os.path.isdir(self.drive_path)
            except OSError:
                return False

        try:
            subprocess.run(
                ["cmd", "/d", "/c", f"dir {self.drive_path} >nul 2>nul"],
                capture_output=True,
                text=True,
                timeout=ACCESS_PROBE_TIMEOUT_SECONDS,
                check=True,
                **_hidden_subprocess_kwargs(),
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return False

    def _handle_reconnect(self):
        backoff = 2
        self.engine.unmount(self.drive_letter)

        while self.is_running:
            self.status_changed.emit("Retry")
            process = self.engine.mount(
                self.remote,
                self.drive_letter,
                self.vfs_mode,
                self.root_folder,
                self.custom_args,
                self.volname,
                self.cache_dir,
            )

            if process and self._strict_wait_for_mount(timeout=45):
                return

            self.msleep(backoff * 1000)
            backoff = min(backoff * 2, 30)

    def stop(self):
        self.is_running = False
        self.wait()
