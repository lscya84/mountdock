import os
import re
import subprocess
import tempfile
from pathlib import Path

import requests

from mountdock import __version__


GITHUB_LATEST = "https://api.github.com/repos/lscya84/mountdock/releases/latest"
GITHUB_RELEASES_URL = "https://github.com/lscya84/mountdock/releases"


def _hidden_subprocess_kwargs() -> dict:
    if os.name != "nt":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {
        "startupinfo": startupinfo,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


class AppUpdater:
    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def get_current_version(self) -> str:
        return __version__

    def get_latest_release(self) -> dict:
        response = requests.get(GITHUB_LATEST, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        version = str(data.get("tag_name", "")).lstrip("v")
        assets = data.get("assets") or []
        installer_asset = next(
            (
                asset
                for asset in assets
                if str(asset.get("name", "")).startswith("MountDock-Setup-v")
                and str(asset.get("name", "")).lower().endswith(".exe")
            ),
            None,
        )
        return {
            "version": version,
            "url": data.get("html_url") or GITHUB_RELEASES_URL,
            "name": data.get("name", ""),
            "installer_url": (installer_asset or {}).get("browser_download_url", ""),
            "installer_name": (installer_asset or {}).get("name", ""),
        }

    def download_installer(self, url: str, filename: str | None = None, progress_cb=None) -> Path:
        if not url:
            raise RuntimeError("Installer download URL is missing.")

        target_dir = Path(tempfile.gettempdir()) / "MountDockUpdates"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / (filename or Path(url).name or "MountDock-Setup.exe")

        with requests.get(url, stream=True, timeout=self.timeout) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            downloaded = 0
            with open(target_path, "wb") as handle:
                for chunk in response.iter_content(65536):
                    if chunk:
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb and total:
                            progress_cb(min(100, int(downloaded * 100 / total)))

        if progress_cb:
            progress_cb(100)
        return target_path

    def launch_installer(self, installer_path: str | Path) -> None:
        path = Path(installer_path)
        if not path.exists():
            raise FileNotFoundError(f"Installer not found: {path}")
        subprocess.Popen([str(path)])

    def schedule_installer_after_pid_exits(self, installer_path: str | Path, pid: int) -> None:
        path = Path(installer_path)
        if not path.exists():
            raise FileNotFoundError(f"Installer not found: {path}")

        if os.name != "nt":
            subprocess.Popen([str(path)])
            return

        helper_dir = Path(tempfile.gettempdir()) / "MountDockUpdates"
        helper_dir.mkdir(parents=True, exist_ok=True)
        helper_path = helper_dir / f"run_installer_after_exit_{pid}.bat"
        helper_path.write_text(
            "\r\n".join(
                [
                    "@echo off",
                    "setlocal",
                    f'set "TARGET_PID={int(pid)}"',
                    f'set "INSTALLER={path}"',
                    ":wait_loop",
                    'tasklist /FI "PID eq %TARGET_PID%" | find "%TARGET_PID%" >nul',
                    "if not errorlevel 1 (",
                    "  timeout /t 1 /nobreak >nul",
                    "  goto wait_loop",
                    ")",
                    'start "" "%INSTALLER%"',
                    'del "%~f0"',
                    "exit /b 0",
                ]
            ),
            encoding="utf-8",
        )
        subprocess.Popen(
            ["cmd.exe", "/c", str(helper_path)],
            **_hidden_subprocess_kwargs(),
        )

    def get_releases_url(self) -> str:
        return GITHUB_RELEASES_URL

    def is_update_available(self, installed: str, latest: str) -> bool:
        if not installed or not latest:
            return False
        return self._ver_tuple(installed) < self._ver_tuple(latest)

    def _ver_tuple(self, value: str):
        try:
            return tuple(int(x) for x in re.findall(r"\d+", value))
        except Exception:
            return (0,)
