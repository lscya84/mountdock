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

    def download_and_install(self, target_dir: str | Path, version: str | None = None) -> Path:
        target = Path(target_dir)
        target.mkdir(parents=True, exist_ok=True)

        version = version or self.get_latest_version()
        url = f"https://github.com/rclone/rclone/releases/download/v{version}/rclone-v{version}-windows-amd64.zip"

        with requests.get(url, stream=True, timeout=self.timeout) as response:
            response.raise_for_status()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                for chunk in response.iter_content(65536):
                    if chunk:
                        tmp.write(chunk)
                tmp_path = Path(tmp.name)

        try:
            with zipfile.ZipFile(tmp_path, "r") as archive:
                exe_name = next((name for name in archive.namelist() if name.endswith("rclone.exe")), None)
                if not exe_name:
                    raise RuntimeError("rclone.exe not found in downloaded archive")
                extracted = archive.read(exe_name)

            out_path = target / "rclone.exe"
            out_path.write_bytes(extracted)
            return out_path
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
