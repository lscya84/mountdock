import os
import shutil
import sys

import PyInstaller.__main__


DATA_SEPARATOR = ";" if os.name == "nt" else ":"


def build_exe(mode: str = "onedir"):
    print(f"빌드를 시작합니다. mode={mode}")

    entry_point = "main.py"
    icon_path = os.path.join("assets", "icon.ico")
    manifest_path = os.path.join("assets", "app.manifest")

    params = [
        entry_point,
        "--noconsole",
        "--hide-console",
        "hide-early",
        "--name=L-Drive_Pro",
        f"--manifest={manifest_path}",
        f"--add-data=assets{DATA_SEPARATOR}assets",
        "--clean",
        "--workpath=build",
        "--distpath=dist",
    ]

    if mode == "onefile":
        params.append("--onefile")
    else:
        params.append("--onedir")

    if os.path.exists(icon_path):
        params.append(f"--icon={icon_path}")

    try:
        PyInstaller.__main__.run(params)
        print("\n" + "=" * 50)
        print("빌드가 완료되었습니다.")
        if mode == "onefile":
            print("결과 파일: dist/L-Drive_Pro.exe")
        else:
            print("결과 폴더: dist/L-Drive_Pro/")
            print("포터블 권장 구성: dist/L-Drive_Pro/ 안에 rclone.exe, rclone.conf 함께 배치")
        print("=" * 50)
    except Exception as exc:
        print(f"빌드 중 오류가 발생했습니다: {exc}")


if __name__ == "__main__":
    mode = "onedir"
    if len(sys.argv) > 1 and sys.argv[1] in {"onefile", "onedir"}:
        mode = sys.argv[1]

    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
            except Exception:
                pass

    build_exe(mode)
