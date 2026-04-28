from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
RELEASE_DIR = DIST_DIR / "release"
APP_DIR = DIST_DIR / "MountDock"


README_TEMPLATE = ROOT / "README.md"


def ensure_clean_dir(path: Path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_if_exists(src: Path, dst: Path):
    if src.exists():
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def main():
    if not APP_DIR.exists():
        raise SystemExit("dist/MountDock 폴더가 없습니다. 먼저 Windows에서 onedir 빌드를 실행하세요.")

    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    portable_dir = RELEASE_DIR / "MountDock_Portable"
    ensure_clean_dir(portable_dir)

    shutil.copytree(APP_DIR, portable_dir / "MountDock", dirs_exist_ok=True)

    branding_dir = portable_dir / "MountDock" / "_internal" / "assets" / "branding"
    if branding_dir.exists():
        shutil.rmtree(branding_dir)

    copy_if_exists(README_TEMPLATE, portable_dir / "README.md")

    (portable_dir / "PORTABLE.txt").write_text(
        "MountDock Portable\n"
        "===================\n\n"
        "Recommended contents:\n"
        "- MountDock.exe\n"
        "- _internal/\n"
        "- rclone.exe (optional)\n"
        "- rclone.conf (optional)\n\n"
        "If rclone.exe and rclone.conf are placed next to the app, MountDock will prefer them.\n",
        encoding="utf-8",
    )

    archive_base = RELEASE_DIR / "MountDock_Portable"
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=RELEASE_DIR, base_dir="MountDock_Portable")

    print(f"포터블 폴더: {portable_dir}")
    print(f"포터블 ZIP: {archive_path}")


if __name__ == "__main__":
    main()
