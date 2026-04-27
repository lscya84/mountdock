import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

import requests


GITHUB_LATEST = "https://api.github.com/repos/rclone/rclone/releases/latest"


class RcloneUpdater:
    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    def get_latest_version(self) -> str:
        response = requests.get(GITHUB_LATEST, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        return str(data.get("tag_name", "")).lstrip("v")

    def get_installed_version(self, rclone_path: str | Path) -> str:
        path = Path(rclone_path)
        if not path.exists():
            return ""
        try:
            result = subprocess.run(
                [str(path), "version"],
                capture_output=True,
                text=True,
                timeout=15,
                errors="replace",
            )
            output = (result.stdout or result.stderr or "").strip()
            match = re.search(r"rclone v([0-9][^\s]*)", output)
            return match.group(1) if match else ""
        except Exception:
            return ""

    def is_update_available(self, installed: str, latest: str) -> bool:
        if not installed or not latest:
            return False
        return self._ver_tuple(installed) < self._ver_tuple(latest)

    def download_and_install(self, target_dir: str | Path, version: str | None = None, progress_cb=None) -> dict:
        target = Path(target_dir)
        target.mkdir(parents=True, exist_ok=True)

        version = version or self.get_latest_version()
        url = f"https://github.com/rclone/rclone/releases/download/v{version}/rclone-v{version}-windows-amd64.zip"

        with requests.get(url, stream=True, timeout=self.timeout) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            downloaded = 0
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                for chunk in response.iter_content(65536):
                    if chunk:
                        tmp.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb and total:
                            progress_cb(min(100, int(downloaded * 100 / total)))
                tmp_path = Path(tmp.name)

        try:
            with zipfile.ZipFile(tmp_path, "r") as archive:
                exe_name = next((name for name in archive.namelist() if name.endswith("rclone.exe")), None)
                if not exe_name:
                    raise RuntimeError("rclone.exe not found in downloaded archive")
                extracted = archive.read(exe_name)

            out_path = target / "rclone.exe"
            locked_fallback = False
            try:
                out_path.write_bytes(extracted)
                final_path = out_path
            except PermissionError:
                final_path = target / "rclone_new.exe"
                final_path.write_bytes(extracted)
                locked_fallback = True

            if progress_cb:
                progress_cb(100)
            return {
                "path": final_path,
                "version": version,
                "locked_fallback": locked_fallback,
            }
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _ver_tuple(self, value: str):
        try:
            return tuple(int(x) for x in re.findall(r"\d+", value))
        except Exception:
            return (0,)
