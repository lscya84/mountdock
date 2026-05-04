# MountDock

## 소개 / Introduction

**KR**  
MountDock은 rclone 마운트를 위한 가벼운 Windows GUI입니다.  
터미널 중심의 rclone 작업을 더 쉽게 다룰 수 있도록, 연결/해제/프로필 관리를 데스크톱 UI로 제공하는 독립형 앱입니다.

**EN**  
MountDock is a lightweight Windows GUI for rclone mounts.  
It is an independent desktop app that makes terminal-heavy rclone workflows easier to manage with a practical Windows interface.

---

## 주요 기능 / Key Features

**KR**
- 여러 rclone 마운트 프로필 관리
- Windows UI에서 연결 / 해제
- 드라이브 카드 호버 강조 및 더블클릭으로 Windows 탐색기 열기
- 트레이 시작, 트레이 최소화, 트레이 복원
- 앱 시작 시 자동 마운트
- 모두 연결 / 모두 해제 지원
- 포터블 환경 친화적인 config / log / rclone 경로 처리
- `rclone.conf` 및 `rclone listremotes` 기반 리모트 감지
- 진행률이 보이는 내장 rclone 업데이트 기능
- 마운트 중 rclone 업데이트 시 자동 해제 / 업데이트 / 재마운트 또는 다음 실행 시 지연 적용
- rclone / MountDock 업데이트가 있을 때 설정 버튼 배지 표시
- Google Drive 기반 암호화 `rclone.conf` 백업 / 복원
- 내장 rclone config 실행 UI
- 한국어 / English UI 지원

**EN**
- Manage multiple rclone mount profiles
- Mount and unmount from a Windows desktop UI
- Hover-highlight drive cards and open mounted drives in Windows Explorer on double-click
- Start to tray, minimize to tray, restore from tray
- Auto-mount on app launch
- Bulk mount / bulk unmount actions
- Portable-friendly config / log / rclone path handling
- Remote discovery via `rclone.conf` and `rclone listremotes`
- Built-in rclone updater with progress dialog
- While drives are mounted, rclone updates can unmount, update, and remount automatically, or be deferred until the next app start
- Show a badge on the Settings button when an rclone or MountDock update is available
- Encrypted `rclone.conf` backup / restore via Google Drive
- Built-in UI for interactive rclone config
- Korean / English UI support

---

## 다운로드 / Download

**KR**
- 최신 릴리즈: <https://github.com/lscya84/mountdock/releases/latest>
- 설치형 EXE: GitHub Releases의 `MountDock-Setup-vX.Y.Z.exe`
- 포터블 ZIP: GitHub Releases의 `MountDock_Portable.zip`

**EN**
- Latest release: <https://github.com/lscya84/mountdock/releases/latest>
- Installer EXE: `MountDock-Setup-vX.Y.Z.exe` from GitHub Releases
- Portable ZIP: `MountDock_Portable.zip` from GitHub Releases

---

## 프로젝트 성격 / Project Status

**KR**  
MountDock은 **rclone 기반의 독립적인 Windows GUI**입니다.  
공식 rclone 앱은 아니며, Windows에서 rclone 마운트를 더 편하게 쓰기 위한 데스크톱 프론트엔드를 목표로 합니다.

**EN**  
MountDock is an **independent Windows GUI built on top of rclone**.  
It is not an official rclone application; it is a desktop-focused front-end intended to make rclone mounts easier to use on Windows.

---

## 시스템 요구사항 / System Requirements

**KR**
- Windows 환경 전용 앱입니다.
- 마운트 기능은 내부적으로 `rclone mount`를 사용합니다.
- 따라서 **Windows에서 실제 마운트를 사용하려면 WinFsp가 필요합니다.**
- WinFsp가 없으면 마운트 시 `cannot find winfsp`, `failed to mount FUSE fs` 같은 오류가 발생할 수 있습니다.
- 단순히 문서를 읽거나 빌드 스크립트를 보는 것은 가능하지만, **실제 드라이브 마운트 기능은 WinFsp 없이 동작하지 않습니다.**

**EN**
- This app targets Windows.
- Its mount workflow uses `rclone mount` internally.
- Therefore, **WinFsp is required on Windows for actual mount operations.**
- Without WinFsp, mounting may fail with errors such as `cannot find winfsp` or `failed to mount FUSE fs`.
- You can still inspect the app or build scripts without it, but **the actual drive-mount feature will not work on Windows without WinFsp.**

WinFsp:
- <https://winfsp.dev/>
- <https://winfsp.dev/rel/>

---

## 포터블 배포 / Portable Distribution

**KR**  
Windows 배포에는 PyInstaller `onedir` 구성을 권장합니다.
포터블 ZIP도 **WinFsp를 포함하지 않으며**, 사용자는 먼저 WinFsp를 설치해야 실제 마운트를 사용할 수 있습니다.

**EN**  
For Windows distribution, a PyInstaller `onedir` build is recommended.
The portable ZIP **does not bundle WinFsp**, so users must install WinFsp first to use actual mount operations.

예시 구조 / Example layout:

```text
dist/MountDock/
  MountDock.exe
  _internal/
  rclone.exe
  rclone.conf
  config.json
  logs/
```

빌드 명령 / Build commands:

```bash
python build.py --mode onedir
python release_portable.py
python release_installer.py
release_windows.bat vX.Y.Z
```

출력물 / Release outputs:

```text
dist/release/MountDock_Portable.zip
dist/release/MountDock-Setup-vX.Y.Z.exe
```

권장 릴리즈 구성 / Recommended release set:

- `MountDock-Setup-vX.Y.Z.exe` → 일반 사용자용 설치형
- `MountDock_Portable.zip` → 고급 사용자/테스트용 포터블 onedir (WinFsp 선설치 필요)

---

## 포터블 동작 / Portable Behavior

**KR**
- 포터블 구조에서는 설정과 로그를 앱 기준 상대 경로에 저장합니다.
- 앱 폴더에 `rclone.exe`가 있으면 우선 사용합니다.
- 앱 폴더에 `rclone.conf`가 있으면 우선 사용합니다.
- `rclone.conf`를 명시하지 않은 경우 다음 경로도 확인합니다:
  - 번들 앱 디렉터리
  - `%APPDATA%\rclone\rclone.conf`
  - `%USERPROFILE%\.config\rclone\rclone.conf`

**EN**
- In portable layout, config and logs are stored relative to the app.
- If `rclone.exe` exists next to the app, MountDock prefers it.
- If `rclone.conf` exists next to the app, MountDock prefers it.
- If `rclone.conf` is not explicitly configured, MountDock also checks:
  - bundled app directory
  - `%APPDATA%\rclone\rclone.conf`
  - `%USERPROFILE%\.config\rclone\rclone.conf`

---

## 앱 내 업데이트 동작 / In-App Update Behavior

**KR**
- MountDock은 GitHub Releases를 기준으로 **MountDock 업데이트**를 확인할 수 있습니다.
- `rclone.exe`는 앱 안에서 직접 업데이트할 수 있습니다.
- 이미 드라이브가 마운트된 상태에서 rclone 업데이트를 누르면, 안내 후 다음 두 가지 흐름 중 하나를 선택할 수 있습니다:
  - 지금 마운트를 해제하고 업데이트한 뒤 자동으로 다시 마운트
  - 업데이트를 미루고 다음에 앱을 다시 실행할 때 자동 적용
- 보류된 rclone 업데이트가 있거나 새 앱/rclone 업데이트가 감지되면 상단 **설정 버튼에 배지**가 표시됩니다.

**EN**
- MountDock can check for **MountDock updates** from GitHub Releases.
- `rclone.exe` can be updated directly inside the app.
- If you trigger an rclone update while drives are already mounted, MountDock lets you choose between:
  - unmount now, update, and remount automatically
  - defer the update and apply it automatically on the next app start
- When a deferred rclone update exists, or when a new app/rclone update is available, a **badge is shown on the Settings button**.

---

## Google Drive 암호화 동기화 / Google Drive Encrypted Sync

**KR**  
MountDock은 Google Drive `appDataFolder`를 이용해 `rclone.conf`를 **암호화된 형태로 백업/복원**할 수 있습니다.

동작 방식:
- Google 계정으로 로그인
- 사용자가 입력한 패스프레이즈로 `rclone.conf`를 암호화
- 암호화된 JSON payload만 Google Drive에 저장
- 다른 기기에서 같은 계정으로 로그인 후 복원
- 원하면 이 기기에서만 패스프레이즈를 안전하게 기억

준비물:
- Google OAuth client JSON 파일
- Google Drive API 사용 가능 프로젝트
- 앱에서 접근 가능한 `rclone.conf`

기본 흐름:
1. 설정에서 **OAuth client JSON** 파일 선택
2. MountDock이 해당 JSON을 앱 내부 관리 폴더로 복사
3. **Google 로그인** 클릭
4. **암호화된 rclone.conf 백업** 클릭
5. 패스프레이즈 입력 및 필요 시 “이 기기에서 기억” 선택
6. 다른 기기에서는 **Google Drive에서 복원** 클릭

보안 주의:
- Google 로그인 자체는 복호화 키가 아닙니다
- 복호화는 패스프레이즈가 있어야 가능합니다
- Drive에는 평문 `rclone.conf`를 저장하지 않습니다
- 기존 로컬 `rclone.conf`가 있으면 복원 전에 `.bak-YYYYMMDD-HHMMSS` 백업을 만듭니다
- OAuth client JSON과 `rclone.conf`는 앱 내부 관리 폴더(`.mountdock/`)에 복사되어 관리될 수 있습니다

Google OAuth 설정 메모:
- Google Cloud에서 **Desktop app** 유형 OAuth client를 생성하는 것이 가장 간단합니다
- Google Drive API를 활성화해야 합니다
- MountDock 설정에서 해당 **client secret JSON** 파일을 선택해야 합니다
- 선택한 JSON은 MountDock 내부 관리 경로에 복사되어 이후 로그인 지속성에 사용됩니다
- 토큰은 앱 로컬 경로에 캐시되며, 설정창에서 토큰 캐시 경로를 확인할 수 있습니다

문제 해결:
- 로그인 버튼을 눌렀는데 바로 실패하면 client JSON 경로가 실제로 존재하는지 먼저 확인하세요
- 백업 전에는 **백업 확인** 버튼으로 현재 계정의 암호화 백업 존재 여부를 확인할 수 있습니다
- 복원 시 기존 `rclone.conf`가 있으면 자동 백업 파일이 생성됩니다

**EN**  
MountDock can back up and restore `rclone.conf` in **encrypted form** using Google Drive `appDataFolder`.

How it works:
- sign in with your Google account
- encrypt `rclone.conf` with a user-provided passphrase
- store only the encrypted JSON payload in Google Drive
- restore it on another device after signing into the same Google account
- optionally remember the passphrase securely on the current device only

Requirements:
- a Google OAuth client JSON file
- a project with Google Drive API enabled
- an accessible local `rclone.conf`

Basic flow:
1. choose the **OAuth client JSON** file in Settings
2. click **Sign in with Google**
3. click **Back up encrypted rclone.conf**
4. enter a passphrase and optionally choose “Remember on this device”
5. on another device, click **Restore from Google Drive**

Security notes:
- Google sign-in itself is not the decryption key
- decryption still requires the passphrase
- plaintext `rclone.conf` is not stored in Drive
- if a local `rclone.conf` already exists, MountDock creates a `.bak-YYYYMMDD-HHMMSS` backup before restoring

Google OAuth setup notes:
- the simplest option is to create a **Desktop app** OAuth client in Google Cloud
- the Google Drive API must be enabled for that project
- in MountDock Settings, select the downloaded **client secret JSON** file
- tokens are cached locally by the app, and the token cache path is shown in Settings

Troubleshooting:
- if sign-in fails immediately, first check that the selected client JSON was imported correctly into the app-managed folder
- before restoring, you can use **Check backup** to see whether an encrypted backup exists for the current Google account
- when restoring over an existing `rclone.conf`, MountDock creates a local backup automatically
- restoring now targets the app-managed `rclone.conf` path by default so the app keeps using the restored file consistently

---

## 빌드 / Build

### Windows 환경 / Windows environment

**KR**  
먼저 가상환경에 의존성을 설치하세요.

추가로, **앱의 실제 마운트 동작을 테스트하려면 WinFsp가 설치되어 있어야 합니다.**
코드상 MountDock은 `rclone mount`를 직접 호출합니다.

**EN**  
Install dependencies into the virtual environment first.

Also, **WinFsp must be installed if you want to test actual mount behavior.**
In code, MountDock directly invokes `rclone mount`.

```powershell
.venv\Scripts\pip install -r requirements.txt
```

그 다음 빌드 / Then build:

```powershell
python build.py --mode onedir
python release_portable.py
python release_installer.py
```

설치형 빌드 메모 / Installer build notes:

- `release_installer.py`는 **Windows에서** 실행해야 합니다.
- 사전에 **Inno Setup 6**가 설치되어 있어야 합니다.
- 기본 설치 경로는 사용자 기준 `LocalAppData\Programs\MountDock` 입니다.
- 설치형은 내부적으로 onedir 결과물을 감싼 형태이므로, 실행 안정성과 배포 편의성을 함께 가져갑니다.
- Windows에서는 `release_windows.bat vX.Y.Z`로 onedir + portable ZIP + installer EXE를 한 번에 만들 수 있습니다.
- 빌드 버전은 `MOUNTDOCK_VERSION` 환경변수 또는 최신 git tag에서 자동으로 주입됩니다.

---

## 릴리즈 체크리스트 / Release Checklist

- [ ] **KR** Windows에서 빌드 확인 / **EN** Confirm build on Windows
- [ ] **KR** 테스트 PC에 WinFsp 설치 여부 확인 / **EN** Confirm WinFsp is installed on the Windows test machine
- [ ] **KR** 설치형 EXE 생성 확인 / **EN** Verify installer EXE generation
- [ ] **KR** 앱 내 MountDock 업데이트 확인/설치 버튼 동작 확인 / **EN** Verify in-app MountDock update check/install flow
- [ ] **KR** 트레이 동작 확인 / **EN** Verify tray behavior
- [ ] **KR** 시작 시 자동 마운트 확인 / **EN** Verify auto-mount on launch
- [ ] **KR** 모두 연결 / 모두 해제 동작 확인 / **EN** Verify bulk mount / unmount actions
- [ ] **KR** 언어 전환 확인 / **EN** Verify language switching
- [ ] **KR** rclone 업데이트 모달 확인 / **EN** Verify rclone updater behavior
- [ ] **KR** 마운트 중 rclone 업데이트 시 해제 → 업데이트 → 재마운트 흐름 확인 / **EN** Verify mounted-drive rclone update flow: unmount → update → remount
- [ ] **KR** rclone 업데이트 보류 후 다음 실행 시 자동 적용 확인 / **EN** Verify deferred rclone update is applied on the next app start
- [ ] **KR** 앱/rclone 업데이트 감지 시 설정 버튼 배지 표시 확인 / **EN** Verify the Settings button badge appears when app/rclone updates are available
- [ ] **KR** 포터블 경로 동작 확인 / **EN** Verify portable path behavior
- [ ] **KR** Google OAuth client JSON 선택 시 `.mountdock/google_client_secret.json`로 가져오는지 확인 / **EN** Verify selected Google OAuth client JSON is imported into `.mountdock/google_client_secret.json`
- [ ] **KR** Google OAuth client JSON 선택 후 로그인 확인 / **EN** Verify Google sign-in after selecting OAuth client JSON
- [ ] **KR** 암호화 백업 업로드 확인 / **EN** Verify encrypted backup upload
- [ ] **KR** `rclone.conf` 선택 또는 복원 시 `.mountdock/rclone.conf`를 사용하도록 고정되는지 확인 / **EN** Verify selected/restored `rclone.conf` is managed via `.mountdock/rclone.conf`
- [ ] **KR** 다른 경로에 기존 `rclone.conf`가 있을 때 백업 후 복원 확인 / **EN** Verify restore creates a backup when local `rclone.conf` already exists
- [ ] **KR** “이 기기에서 기억” 체크 후 재복원 시 저장된 패스프레이즈 사용 확인 / **EN** Verify remembered-on-device passphrase is reused on later restore
- [ ] **KR** 로그아웃 시 로컬 저장 패스프레이즈 정리 확인 / **EN** Verify sign-out clears the locally saved passphrase
- [ ] **KR** 설치형 제거 후 재설치 흐름 확인 / **EN** Verify uninstall and reinstall flow for installer build

---

## 라이선스 / License

**KR**  
이 프로젝트는 MIT License를 따릅니다.

**EN**  
This project is licensed under the MIT License.
