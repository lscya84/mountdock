from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def resolve_version(default: str = "0.0.0") -> str:
    env_version = os.environ.get("MOUNTDOCK_VERSION", "").strip()
    if env_version:
        return env_version.removeprefix("v")

    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        tag = result.stdout.strip()
        if tag:
            return tag.removeprefix("v")
    except Exception:
        pass

    return default

