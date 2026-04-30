import re

import requests

from mountdock import __version__


GITHUB_LATEST = "https://api.github.com/repos/lscya84/mountdock/releases/latest"
GITHUB_RELEASES_URL = "https://github.com/lscya84/mountdock/releases"


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
        return {
            "version": version,
            "url": data.get("html_url") or GITHUB_RELEASES_URL,
            "name": data.get("name", ""),
        }

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

