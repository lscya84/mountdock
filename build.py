import os
import shutil
import sys
import argparse
from pathlib import Path


DATA_SEPARATOR = ";" if os.name == "nt" else ":"
ROOT = Path(__file__).resolve().parent


def build_exe(mode: str = "onedir"):
    import PyInstaller.__main__

    print(f"빌드를 시작합니다. mode={mode}")

    entry_point = str(ROOT / "main.py")
    icon_path = ROOT / "assets" / "icon.ico"
    manifest_path = ROOT / "assets" / "app.manifest"

    params = [
        entry_point,
        "--noconsole",
        "--hide-console",
        "hide-early",
        "--name=MountDock",
        f"--manifest={manifest_path}",
        f"--add-data={ROOT / 'assets'}{DATA_SEPARATOR}assets",
        "--clean",
        f"--workpath={ROOT / 'build'}",
        f"--distpath={ROOT / 'dist'}",
    ]

    if mode == "onefile":
        params.append("--onefile")
    else:
        params.append("--onedir")

    if icon_path.exists():
        params.append(f"--icon={icon_path}")

    try:
        PyInstaller.__main__.run(params)
        print("\n" + "=" * 50)
        print("빌드가 완료되었습니다.")
        if mode == "onefile":
            print("결과 파일: dist/MountDock.exe")
        else:
            print("결과 폴더: dist/MountDock/")
            print("포터블 권장 구성: dist/MountDock/ 안에 rclone.exe, rclone.conf 함께 배치")
        print("=" * 50)
    except Exception as exc:
        print(f"빌드 중 오류가 발생했습니다: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build MountDock with PyInstaller")
    parser.add_argument("mode_arg", nargs="?", choices=["onefile", "onedir"], help="build mode")
    parser.add_argument("--mode", dest="mode_flag", choices=["onefile", "onedir"], help="build mode")
    args = parser.parse_args()

    mode = args.mode_flag or args.mode_arg or "onedir"

    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
            except Exception:
                pass

    build_exe(mode)
