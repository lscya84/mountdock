from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
APP_DIR = DIST_DIR / "MountDock"
RELEASE_DIR = DIST_DIR / "release"
INSTALLER_DIR = ROOT / "installer"
ISS_FILE = INSTALLER_DIR / "MountDock.iss"


def detect_version() -> str:
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

    return "0.0.0"


def locate_iscc() -> str:
    candidates = []

    env_path = os.environ.get("INNO_SETUP_COMPILER", "").strip()
    if env_path:
        candidates.append(env_path)

    candidates.extend(
        [
            shutil.which("iscc"),
            shutil.which("ISCC.exe"),
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            r"C:\Program Files\Inno Setup 6\ISCC.exe",
        ]
    )

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)

    raise SystemExit(
        "Inno Setup compiler(ISCC.exe)를 찾지 못했습니다. "
        "Windows에서 Inno Setup 6를 설치한 뒤 다시 실행하세요."
    )


def main() -> None:
    if not APP_DIR.exists():
        raise SystemExit("dist/MountDock 폴더가 없습니다. 먼저 Windows에서 onedir 빌드를 실행하세요.")

    if not ISS_FILE.exists():
        raise SystemExit(f"인스톨러 스크립트를 찾을 수 없습니다: {ISS_FILE}")

    version = sys.argv[1].removeprefix("v") if len(sys.argv) > 1 else detect_version()
    iscc = locate_iscc()

    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    output_name = f"MountDock-Setup-v{version}"

    cmd = [
        iscc,
        f"/DMyAppVersion={version}",
        f"/DSourceDir={APP_DIR}",
        f"/DOutputDir={RELEASE_DIR}",
        f"/DOutputBaseFilename={output_name}",
        str(ISS_FILE),
    ]

    print("Inno Setup 빌드를 시작합니다.")
    print(" ".join(f'"{part}"' if " " in part else part for part in cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)

    output_path = RELEASE_DIR / f"{output_name}.exe"
    print(f"설치형 EXE: {output_path}")


if __name__ == "__main__":
    main()
