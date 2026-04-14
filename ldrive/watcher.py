import logging
import os

import psutil
from PyQt6.QtCore import QThread, pyqtSignal

from ldrive.rclone_engine import RcloneEngine

logger = logging.getLogger("Watcher")


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
    ):
        super().__init__()
        self.engine = engine
        self.remote = remote
        self.drive_letter = drive_letter.upper().replace(":", "")
        self.vfs_mode = vfs_mode
        self.root_folder = root_folder
        self.custom_args = custom_args
        self.volname = volname
        self.is_running = True
        self.drive_path = f"{self.drive_letter}:\\"

    def run(self):
        logger.info("Watcher Starting: %s", self.remote)
        self.status_changed.emit("Starting")

        if not self._strict_wait_for_mount(timeout=15):
            self.status_changed.emit("Disconnected")
            return

        while self.is_running:
            if self._check_connection():
                self.status_changed.emit("Connected")
                self.msleep(5000)
            else:
                self.log_emitted.emit(f"[Watcher] Drive {self.drive_letter}: connection lost. Retrying.")
                self._handle_reconnect()

    def _strict_wait_for_mount(self, timeout: int = 15) -> bool:
        for attempt in range(timeout):
            if not self.is_running:
                return False

            if not self.engine.is_process_alive(self.drive_letter):
                err = self.engine.last_error
                message = f"[Error] Mount failed: {err[:500]}" if err else "[Error] Rclone process exited unexpectedly."
                self.log_emitted.emit(message)
                return False

            if self._check_drive_ready():
                self.log_emitted.emit(f"[Success] Drive {self.drive_letter}: mounted and accessible.")
                self.status_changed.emit("Connected")
                return True

            self.status_changed.emit(f"Mounting {attempt + 1}/{timeout}")
            self.msleep(1000)

        self.log_emitted.emit(f"[Timeout] Drive {self.drive_letter}: mount point did not become accessible.")
        return False

    def _check_connection(self) -> bool:
        return self.engine.is_process_alive(self.drive_letter) and self._check_drive_ready()

    def _check_drive_ready(self) -> bool:
        if not self._check_drive_exists():
            return False

        try:
            os.listdir(self.drive_path)
            return True
        except PermissionError:
            return True
        except OSError:
            return False

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

    def _handle_reconnect(self):
        backoff = 2
        self.engine.unmount(self.drive_letter)

        while self.is_running:
            self.status_changed.emit(f"Retrying in {backoff}s")
            process = self.engine.mount(
                self.remote,
                self.drive_letter,
                self.vfs_mode,
                self.root_folder,
                self.custom_args,
                self.volname,
            )

            if process and self._strict_wait_for_mount(timeout=15):
                return

            self.msleep(backoff * 1000)
            backoff = min(backoff * 2, 30)

    def stop(self):
        self.is_running = False
        self.wait()
