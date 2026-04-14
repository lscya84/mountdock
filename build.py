import os
import shutil

import PyInstaller.__main__


def build_exe():
    print("빌드를 시작합니다.")

    entry_point = "main.py"
    icon_path = os.path.join("assets", "icon.ico")
    manifest_path = os.path.join("assets", "app.manifest")

    params = [
        entry_point,
        "--noconsole",
        "--hide-console",
        "hide-early",
        "--onefile",
        "--name=L-Drive_Pro",
        f"--manifest={manifest_path}",
        "--add-data=assets;assets",
        "--clean",
        "--workpath=build",
        "--distpath=dist",
    ]

    if os.path.exists(icon_path):
        params.append(f"--icon={icon_path}")

    try:
        PyInstaller.__main__.run(params)
        print("\n" + "=" * 50)
        print("빌드가 완료되었습니다.")
        print("결과 파일: dist/L-Drive_Pro.exe")
        print("=" * 50)
    except Exception as exc:
        print(f"빌드 중 오류가 발생했습니다: {exc}")


if __name__ == "__main__":
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
            except Exception:
                pass

    build_exe()
