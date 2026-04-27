# L-Drive

L-Drive is a Windows desktop app for mounting rclone remotes like a portable drive manager. It is being shaped toward a RaiDrive-like workflow with tray behavior, startup options, and portable deployment support.

## Current capabilities

- Mount multiple rclone remotes to drive letters
- Portable-friendly config/log/rclone path resolution
- Optional startup registration in Windows
- Optional start-to-tray behavior
- Optional minimize/close-to-tray behavior
- Optional mount-on-launch behavior
- Per-drive auto-mount on app launch
- Tray menu with per-drive mount/unmount actions
- Single-instance guard
- Watcher-based reconnect flow after disconnects
- Custom extra rclone arguments
- Optional cache directory per profile

## Portable deployment recommendation

For portable use, prefer **onedir** builds instead of onefile.

### Recommended folder layout

```text
dist/L-Drive_Pro/
  L-Drive_Pro.exe
  rclone.exe
  rclone.conf
  assets/
```

### Build

```bash
python build.py onedir
```

Optional onefile build:

```bash
python build.py onefile
```

### Create a portable release zip

```bash
python release_portable.py
```

This builds the onedir app and creates:

```text
dist/release/L-Drive_Portable.zip
```

### Portable behavior notes

- `config.json` is stored next to the app
- `logs/app.log` is stored next to the app
- If `rclone.exe` exists in the app folder, L-Drive prefers it
- If `rclone.conf` exists in the app folder, L-Drive prefers it
- If `rclone.conf` is not explicitly configured, L-Drive also checks:
  - `%APPDATA%/rclone/rclone.conf`
  - `~/.config/rclone/rclone.conf`

## Startup and tray behavior

### Global settings

- **Auto start**: register the app in Windows startup
- **Mount on launch**: mount all profiles that have per-drive auto-mount enabled
- **Start to tray**: start hidden instead of showing the main window
- **Minimize/close to tray**: keep the app running in the system tray when minimized or closed

### Per-drive settings

- **Auto mount this drive on app launch**
- **Drive letter**
- **Volume name**
- **Root path**
- **VFS cache mode**
- **Cache directory**
- **Extra args**

## Release checklist

Before publishing a release:

- [ ] Run `python build.py onedir`
- [ ] Run `python release_portable.py`
- [ ] Put `rclone.exe` into the portable folder if bundling it
- [ ] Put `rclone.conf` into the portable folder if shipping a ready-to-use config
- [ ] Test startup/tray/mount on a real Windows machine
- [ ] Test a clean unzip-and-run flow from a different folder
- [ ] Upload `L-Drive_Portable.zip` to GitHub Releases

## Recommended Windows test checklist

Use this checklist after each Windows build.

### Tray / lifecycle

- [ ] App starts normally when launched directly
- [ ] With **Start to tray** enabled, app starts hidden
- [ ] Clicking the tray icon restores the window
- [ ] Closing the window keeps the app alive in tray
- [ ] Exiting from tray fully shuts down the app
- [ ] Launching the app twice does not create duplicate instances

### Startup

- [ ] **Auto start** writes a valid registry command
- [ ] After moving the portable folder, startup entry is corrected on next run
- [ ] Startup launch with `--startup` stays hidden as expected

### Mounting

- [ ] Manual mount works for a normal remote
- [ ] Manual unmount works from main window
- [ ] Manual unmount works from tray menu
- [ ] Tray menu mount/unmount reflects real state
- [ ] Mount survives short disconnects and reconnect watcher behaves correctly
- [ ] Per-drive **Auto mount** + global **Mount on launch** works together

### Portable behavior

- [ ] App uses bundled `rclone.exe` when present
- [ ] App uses bundled `rclone.conf` when present
- [ ] `config.json` is created in app folder
- [ ] `logs/app.log` is created in app folder
- [ ] Relative paths still work after moving the portable folder

### Option handling

- [ ] `Root path` mounts a subfolder correctly
- [ ] `Cache directory` is passed to rclone correctly
- [ ] `Extra args` are passed to rclone correctly
- [ ] `VFS cache mode` changes are reflected in actual mount command

## Known next improvements

- Surface parsed remotes from `rclone.conf` more directly in the UI
- Improve tray state refresh timing further
- Add richer validation for cache/extra-args fields
- Add Windows CI or release packaging flow
- Add screenshots and usage examples
