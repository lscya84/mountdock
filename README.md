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

---

## 라이선스 / License

**KR**  
이 프로젝트는 MIT License를 따릅니다.

**EN**  
This project is licensed under the MIT License.
