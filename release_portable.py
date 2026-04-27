import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
APP_DIR = DIST_DIR / "L-Drive_Pro"
RELEASE_DIR = DIST_DIR / "release"


def build_onedir():
    subprocess.run([sys.executable, "build.py", "onedir"], cwd=ROOT, check=True)


def copy_if_exists(src: Path, dst: Path):
    if src.exists():
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def package_release():
    if RELEASE_DIR.exists():
        shutil.rmtree(RELEASE_DIR)
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    portable_dir = RELEASE_DIR / "L-Drive_Portable"
    shutil.copytree(APP_DIR, portable_dir)

    copy_if_exists(ROOT / "README.md", portable_dir / "README.md")
    copy_if_exists(ROOT / "requirements.txt", portable_dir / "requirements.txt")

    notes = portable_dir / "PORTABLE.txt"
    notes.write_text(
        "L-Drive Portable\n"
        "=================\n\n"
        "Recommended contents in this folder:\n"
        "- L-Drive_Pro.exe\n"
        "- rclone.exe\n"
        "- rclone.conf (optional)\n\n"
        "If rclone.exe and rclone.conf are placed next to the app, L-Drive will prefer them.\n",
        encoding="utf-8",
    )

    archive_base = RELEASE_DIR / "L-Drive_Portable"
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=RELEASE_DIR, base_dir="L-Drive_Portable")
    print(f"Created portable archive: {archive_path}")


if __name__ == "__main__":
    build_onedir()
    package_release()
