# MountDock

MountDock is a lightweight Windows GUI for rclone mounts. It gives you a practical desktop front-end for managing rclone remotes like a portable drive manager, with tray behavior, startup options, and portable deployment support.

## What it does

- Manage multiple mount profiles for rclone remotes
- Mount/unmount drives from a compact Windows desktop UI
- Start to tray, minimize to tray, and restore from tray
- Mount drives automatically on app launch
- Bulk mount and bulk unmount actions
- Portable-friendly config/log/rclone path resolution
- Detect remotes from `rclone.conf` and `rclone listremotes`
- Built-in rclone updater with progress dialog
- English / Korean UI support

## Positioning

MountDock is an independent Windows GUI built on top of rclone.
It is not an official rclone application, but a desktop-focused front-end for easier mount management on Windows.

## Portable deployment recommendation

For Windows release distribution, prefer a PyInstaller `onedir` build.

Example layout:

```text
dist/MountDock/
  MountDock.exe
  _internal/
  rclone.exe          # optional, preferred when bundled
  rclone.conf         # optional, preferred when bundled
  config.json         # created on first run for portable mode
  logs/
```

Build commands:

```bash
python build.py --mode onedir
python release_portable.py
```

Portable zip output:

```text
dist/release/MountDock_Portable.zip
```

## Portable behavior notes

- Config and logs are stored relative to the app when running in portable layout
- If `rclone.exe` exists in the app folder, MountDock prefers it
- If `rclone.conf` exists in the app folder, MountDock prefers it
- If `rclone.conf` is not explicitly configured, MountDock also checks:
  - bundled app directory
  - `%APPDATA%\rclone\rclone.conf`
  - `%USERPROFILE%\.config\rclone\rclone.conf`

## Build checklist

### Windows environment

Install dependencies in the virtual environment first:

```powershell
.venv\Scripts\pip install -r requirements.txt
```

Then build:

```powershell
python build.py --mode onedir
python release_portable.py
```

## Release checklist

- [ ] Build on Windows
- [ ] Confirm app launches without console flash during background rclone operations
- [ ] Verify tray behavior (start to tray / minimize to tray / close to tray)
- [ ] Verify auto-mount on launch
- [ ] Verify bulk mount / bulk unmount actions
- [ ] Verify language switching in main window and dialogs
- [ ] Verify rclone update dialog and locked-file fallback behavior
- [ ] Confirm portable config/log/rclone path behavior
- [ ] Upload `MountDock_Portable.zip` to GitHub Releases

## Notes

- Windows release artifacts should be built on Windows, not Linux
- `onedir` is recommended over `onefile` for portable reliability
- The app hides already-used drive letters and already-added remotes where possible
- The rclone updater is intentionally separated into its own modal dialog

## Portable behavior

When distributed as a portable bundle, MountDock can work with app-local:
- `rclone.exe`
- `rclone.conf`
- `config.json`
- `logs/app.log`

This makes it suitable for GitHub Releases style distribution without requiring a formal installer.
