import PyInstaller.__main__
import os
import shutil

def build_exe():
    """
    PyInstaller를 사용하여 L-Drive Pro를 단일 실행 파일(.exe)로 빌드합니다.
    """
    print("빌드 프로세스를 시작합니다...")

    # 1. 빌드 관련 경로 설정
    entry_point = "main.py"
    icon_path = os.path.join("assets", "icon.ico")
    
    # 2. PyInstaller 옵션 구성
    # --noconsole: 콘솔 창 숨기기
    # --onefile: 단일 파일로 패킹
    # --add-data: 리소스 파일 포함 (윈도우 형식: "원본경로;대상폴더")
    # --name: 실행 파일 이름 설정
    
    params = [
        entry_point,
        "--noconsole",
        "--hide-console", "hide-early", # 최신 PyInstaller 추천 옵션
        "--onefile",
        f"--name=L-Drive_Pro",
        # assets 폴더 전체를 포함 (아이콘, 스타일 등)
        f"--add-data=assets;assets",
        "--clean",
        "--workpath=build",
        "--distpath=dist",
    ]

    # 아이콘 파일이 실제로 존재하는지 확인 후 추가
    if os.path.exists(icon_path):
        params.append(f"--icon={icon_path}")
    else:
        print(f"경고: 아이콘 파일({icon_path})을 찾을 수 없습니다. 기본 아이콘으로 빌드됩니다.")

    # 3. PyInstaller 실행
    try:
        PyInstaller.__main__.run(params)
        print("\n" + "="*50)
        print("빌드가 성공적으로 완료되었습니다!")
        print("결과 파일: dist/L-Drive_Pro.exe")
        print("="*50)
    except Exception as e:
        print(f"빌드 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    # 이전 빌드 찌꺼기 정리
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
            except Exception:
                pass
                
    build_exe()
