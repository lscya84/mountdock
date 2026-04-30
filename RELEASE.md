# MountDock Release Flow

## Target release artifacts

MountDock now ships in two Windows-friendly forms:

1. **Installer build**
   - File: `dist/release/MountDock-Setup-vX.Y.Z.exe`
   - Target: 일반 사용자 배포본
2. **Portable onedir build**
   - File: `dist/release/MountDock_Portable.zip`
   - Target: 고급 사용자 / 테스트 / 무설치 실행

---

## Recommended Windows release steps

### One-command flow

```powershell
release_windows.bat v0.1.4
```

### Manual flow

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe build.py --mode onedir
.venv\Scripts\python.exe release_portable.py
.venv\Scripts\python.exe release_installer.py v0.1.4
```

---

## Notes

- `release_installer.py` requires **Inno Setup 6** on Windows.
- Installer packaging wraps the stable `onedir` output rather than replacing it.
- If needed, set a custom Inno Setup compiler path with `INNO_SETUP_COMPILER`.
- If no version is passed explicitly, version resolution uses `MOUNTDOCK_VERSION`, then the latest git tag, then falls back to `0.0.0`.
- `build.py` also injects that resolved version into the packaged app, so the in-app update checker reports the same release version.

---

## GitHub release asset recommendation

Upload both:

- `MountDock-Setup-vX.Y.Z.exe`
- `MountDock_Portable.zip`

Optional:

- SHA256 checksum file(s)

---

## Final Windows verification

- In-app MountDock update check works
- In-app installer download/launch works
- Installer launches correctly
- Portable ZIP extracts and runs correctly
- Tray behavior works
- Settings dialog works
- Google sign-in / backup / restore works
- Existing `rclone.conf` backup/restore behavior works
- Uninstall/reinstall path works for installer build
