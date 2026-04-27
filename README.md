# MountDock

## 소개 / Introduction

**KR**  
MountDock은 rclone 마운트를 위한 가벼운 Windows GUI입니다.  
복잡한 명령어 대신 데스크톱 UI로 rclone 리모트를 연결하고, 해제하고, 관리할 수 있도록 만든 실용적인 앱입니다.

**EN**  
MountDock is a lightweight Windows GUI for rclone mounts.  
It gives you a practical desktop interface for mounting, unmounting, and managing rclone remotes without living in the terminal.

---

## 포지셔닝 / Positioning

**KR**  
MountDock은 rclone 위에서 동작하는 독립적인 Windows 프론트엔드입니다.  
공식 rclone 앱은 아니지만, Windows에서 rclone 마운트를 더 쉽고 빠르게 다루기 위한 데스크톱 도구를 지향합니다.

**EN**  
MountDock is an independent Windows front-end built on top of rclone.  
It is not an official rclone application, but a desktop-focused tool designed to make rclone mounts easier to manage on Windows.

---

## 주요 기능 / Key Features

**KR**
- 여러 rclone 마운트 프로필 관리
- 간결한 Windows UI에서 연결 / 해제
- 트레이 시작, 트레이 최소화, 트레이 복원
- 앱 시작 시 자동 마운트
- 모두 연결 / 모두 해제 지원
- 포터블 환경 친화적인 config / log / rclone 경로 처리
- `rclone.conf` + `rclone listremotes` 기반 리모트 감지
- 진행률이 보이는 내장 rclone 업데이트 기능
- 한국어 / English UI 지원

**EN**
- Manage multiple rclone mount profiles
- Mount and unmount from a compact Windows UI
- Start to tray, minimize to tray, restore from tray
- Auto-mount on app launch
- Bulk mount / bulk unmount actions
- Portable-friendly config / log / rclone path handling
- Remote discovery via `rclone.conf` and `rclone listremotes`
- Built-in rclone updater with progress dialog
- Korean / English UI support

---

## 저장소 이름 검토 / Repository Name Review

**KR**  
현재 저장소 이름은 아직 `ldrive`입니다.  
브랜드 일관성을 위해 장기적으로는 `mountdock` 또는 `mountdock-win` 같은 이름으로 바꾸는 것이 좋습니다.

추천:
- `mountdock` → 가장 깔끔함
- `mountdock-win` → Windows 앱임이 더 분명함
- `mountdock-rclone` → 검색성은 좋지만 이름이 조금 김

권장 방향:
- GitHub star / issue / release 링크가 크게 중요하지 않은 지금 시점이라면 **`mountdock`으로 repo rename** 하는 편이 좋습니다.

**EN**  
The repository name is still `ldrive` for now.  
For brand consistency, it would be better to eventually rename it to something like `mountdock` or `mountdock-win`.

Recommended candidates:
- `mountdock` → cleanest option
- `mountdock-win` → makes the Windows focus explicit
- `mountdock-rclone` → better for search, but a bit longer

Recommended direction:
- If preserving the old repo name is not important, renaming the repository to **`mountdock`** is the best long-term choice.

---

## 디자인 방향 / Design Direction

**KR**  
MountDock의 디자인은 “화려한 앱”보다는 “정돈된 Windows 유틸리티” 쪽이 잘 어울립니다.

브랜드 방향:
- 네이비 / 블루 기반 포인트 컬러
- 평평하고 단정한 리스트 중심 UI
- 과한 카드감보다 생산성 위주 레이아웃
- rclone을 쉽게 다루는 실무형 도구 느낌

아이콘 방향 제안:
- 드라이브 + 도킹 심볼
- 마운트된 볼륨 느낌의 단순 아이콘
- `M` / `D` 모노그램 기반 아이콘

현재 저장소에는 1차 아이콘 시안이 포함되어 있습니다:
- `assets/branding/mountdock-icon.svg`
- `assets/branding/MountDock_branding.md`

**EN**  
MountDock fits better as a clean Windows utility than as a flashy consumer app.

Brand direction:
- navy / blue accent palette
- flat, tidy list-oriented UI
- productivity-first layout over heavy card styling
- practical desktop tool feel for easier rclone workflows

Icon direction ideas:
- drive + docking symbol
- simplified mounted-volume icon
- `M` / `D` monogram concept

A first branding draft is now included in the repository:
- `assets/branding/mountdock-icon.svg`
- `assets/branding/MountDock_branding.md`

---

## 포터블 배포 권장 / Portable Deployment Recommendation

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

## 빌드 체크리스트 / Build Checklist

### Windows 환경 / Windows Environment

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
- [ ] **KR** 백그라운드 rclone 동작 시 콘솔 플래시 없음 확인 / **EN** Confirm no console flash during background rclone operations
- [ ] **KR** 트레이 동작 확인 / **EN** Verify tray behavior
- [ ] **KR** 시작 시 자동 마운트 확인 / **EN** Verify auto-mount on launch
- [ ] **KR** 모두 연결 / 모두 해제 동작 확인 / **EN** Verify bulk mount / unmount actions
- [ ] **KR** 언어 전환 확인 / **EN** Verify language switching
- [ ] **KR** rclone 업데이트 모달 확인 / **EN** Verify rclone updater dialog behavior
- [ ] **KR** 포터블 경로 동작 확인 / **EN** Verify portable path behavior
- [ ] **KR** `MountDock_Portable.zip` 업로드 / **EN** Upload `MountDock_Portable.zip`

---

## 다음 릴리즈 계획 / Next Release Plan

### MountDock v0.1.1

**KR**
예정 반영 항목:
- MountDock 리브랜딩 정리
- README / 소개 문구 한영 병기
- 리스트 UI 및 상단 액션 정리 후속 반영
- 색상 / 아이콘 / 앱 인상 정리

**EN**
Planned highlights:
- MountDock rebrand cleanup
- Bilingual README and product copy
- Follow-up polish for list UI and top actions
- Color, icon, and app identity refinement

---

## 참고 / Notes

**KR**
- Windows 릴리즈는 Linux가 아니라 Windows에서 빌드하는 것이 좋습니다.
- 포터블 안정성을 위해 `onefile`보다 `onedir`를 권장합니다.
- 이 앱은 가능한 범위에서 이미 사용 중인 드라이브 문자와 중복 리모트를 숨깁니다.
- rclone 업데이트는 별도 모달로 분리되어 있습니다.

**EN**
- Windows release artifacts should be built on Windows, not Linux.
- `onedir` is recommended over `onefile` for portable reliability.
- The app hides already-used drive letters and duplicate remotes where possible.
- The rclone updater is intentionally separated into its own modal dialog.
