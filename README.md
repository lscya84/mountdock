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
- 트레이 시작, 트레이 최소화, 트레이 복원
- 앱 시작 시 자동 마운트
- 모두 연결 / 모두 해제 지원
- 포터블 환경 친화적인 config / log / rclone 경로 처리
- `rclone.conf` 및 `rclone listremotes` 기반 리모트 감지
- 진행률이 보이는 내장 rclone 업데이트 기능
- 한국어 / English UI 지원

**EN**
- Manage multiple rclone mount profiles
- Mount and unmount from a Windows desktop UI
- Start to tray, minimize to tray, restore from tray
- Auto-mount on app launch
- Bulk mount / bulk unmount actions
- Portable-friendly config / log / rclone path handling
- Remote discovery via `rclone.conf` and `rclone listremotes`
- Built-in rclone updater with progress dialog
- Korean / English UI support

---

## 프로젝트 성격 / Project Status

**KR**  
MountDock은 **rclone 기반의 독립적인 Windows GUI**입니다.  
공식 rclone 앱은 아니며, Windows에서 rclone 마운트를 더 편하게 쓰기 위한 데스크톱 프론트엔드를 목표로 합니다.

**EN**  
MountDock is an **independent Windows GUI built on top of rclone**.  
It is not an official rclone application; it is a desktop-focused front-end intended to make rclone mounts easier to use on Windows.

---

## 포터블 배포 / Portable Distribution

**KR**  
Windows 배포에는 PyInstaller `onedir` 구성을 권장합니다.

**EN**  
For Windows distribution, a PyInstaller `onedir` build is recommended.

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
```

포터블 출력 / Portable output:

```text
dist/release/MountDock_Portable.zip
```

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

**EN**  
Install dependencies into the virtual environment first.

```powershell
.venv\Scripts\pip install -r requirements.txt
```

그 다음 빌드 / Then build:

```powershell
python build.py --mode onedir
python release_portable.py
```

---

## 릴리즈 체크리스트 / Release Checklist

- [ ] **KR** Windows에서 빌드 확인 / **EN** Confirm build on Windows
- [ ] **KR** 트레이 동작 확인 / **EN** Verify tray behavior
- [ ] **KR** 시작 시 자동 마운트 확인 / **EN** Verify auto-mount on launch
- [ ] **KR** 모두 연결 / 모두 해제 동작 확인 / **EN** Verify bulk mount / unmount actions
- [ ] **KR** 언어 전환 확인 / **EN** Verify language switching
- [ ] **KR** rclone 업데이트 모달 확인 / **EN** Verify rclone updater behavior
- [ ] **KR** 포터블 경로 동작 확인 / **EN** Verify portable path behavior
- [ ] **KR** Google OAuth client JSON 선택 시 `.mountdock/google_client_secret.json`로 가져오는지 확인 / **EN** Verify selected Google OAuth client JSON is imported into `.mountdock/google_client_secret.json`
- [ ] **KR** Google OAuth client JSON 선택 후 로그인 확인 / **EN** Verify Google sign-in after selecting OAuth client JSON
- [ ] **KR** 암호화 백업 업로드 확인 / **EN** Verify encrypted backup upload
- [ ] **KR** `rclone.conf` 선택 또는 복원 시 `.mountdock/rclone.conf`를 사용하도록 고정되는지 확인 / **EN** Verify selected/restored `rclone.conf` is managed via `.mountdock/rclone.conf`
- [ ] **KR** 다른 경로에 기존 `rclone.conf`가 있을 때 백업 후 복원 확인 / **EN** Verify restore creates a backup when local `rclone.conf` already exists
- [ ] **KR** “이 기기에서 기억” 체크 후 재복원 시 저장된 패스프레이즈 사용 확인 / **EN** Verify remembered-on-device passphrase is reused on later restore
- [ ] **KR** 로그아웃 시 로컬 저장 패스프레이즈 정리 확인 / **EN** Verify sign-out clears the locally saved passphrase

---

## 라이선스 / License

**KR**  
이 프로젝트는 MIT License를 따릅니다.

**EN**  
This project is licensed under the MIT License.
