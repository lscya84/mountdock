from __future__ import annotations

import ctypes
import os
from pathlib import Path

import winreg

from mountdock.drive_icons import ensure_drive_icon_file


PER_USER_ICON_ROOTS = [
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\DriveIcons",
    r"Software\Classes\Applications\Explorer.exe\Drives",
]

SHCNE_UPDATEITEM = 0x00002000
SHCNE_ASSOCCHANGED = 0x08000000
SHCNF_IDLIST = 0x0000
SHCNF_PATHW = 0x0005


def _normalize_letter(letter: str) -> str:
    return str(letter or "").replace(":", "").strip().upper()


def _delete_tree(root, subkey: str):
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE) as handle:
            while True:
                try:
                    child = winreg.EnumKey(handle, 0)
                except OSError:
                    break
                _delete_tree(root, f"{subkey}\\{child}")
    except FileNotFoundError:
        return
    except OSError:
        return

    try:
        winreg.DeleteKey(root, subkey)
    except OSError:
        pass


def _set_default_icon_value(base_path: str, letter: str, icon_location: str):
    default_icon_path = f"{base_path}\\{letter}\\DefaultIcon"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, default_icon_path) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, icon_location)


def refresh_shell(drive_letter: str | None = None):
    drive_root = None
    if drive_letter:
        drive_root = f"{_normalize_letter(drive_letter)}:\\"

    try:
        shell32 = ctypes.windll.shell32
        if drive_root:
            shell32.SHChangeNotify(SHCNE_UPDATEITEM, SHCNF_PATHW, ctypes.c_wchar_p(drive_root), None)
        shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
    except Exception:
        pass


def apply_drive_icon(app_dir: str | Path, letter: str, profile_or_key, remote_type: str | None = None, remote_name: str | None = None) -> str:
    if os.name != "nt":
        return ""

    normalized = _normalize_letter(letter)
    if not normalized:
        return ""

    icon_path = ensure_drive_icon_file(app_dir, profile_or_key, remote_type=remote_type, remote_name=remote_name)
    if not icon_path:
        return ""

    icon_location = f"{icon_path},0"
    for root in PER_USER_ICON_ROOTS:
        _set_default_icon_value(root, normalized, icon_location)
    refresh_shell(normalized)
    return icon_path


def clear_drive_icon(letter: str):
    if os.name != "nt":
        return

    normalized = _normalize_letter(letter)
    if not normalized:
        return

    for root in PER_USER_ICON_ROOTS:
        _delete_tree(winreg.HKEY_CURRENT_USER, f"{root}\\{normalized}")
    refresh_shell(normalized)
