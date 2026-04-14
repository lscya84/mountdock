import json
import os
import logging
import winreg
import sys

# 로그 설정
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("logs/app.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ConfigManager")

class ConfigManager:
    """
    L-Drive Pro의 설정 및 Windows 시스템 통합을 관리하는 클래스입니다.
    애플리케이션 설정 저장/로드 및 부팅 시 자동 실행 등록 기능을 담당합니다.
    """
    
    CONFIG_FILE = "config.json"
    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "L-DrivePro"

    def __init__(self):
        self.config = {
            "theme": "dark",
            "auto_start": False,
            "last_mount_remote": "",
            "last_drive_letter": "Z",
            "vfs_mode": "full",  # 'full' (Media) or 'writes' (Work)
            "rclone_path": "rclone.exe"
        }
        self.load_config()

    def load_config(self):
        """
        config.json 파일에서 설정값을 로드합니다. 파일이 없으면 기본값을 사용합니다.
        """
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                    self.config.update(loaded_data)
                logger.info("설정 파일을 성공적으로 로드했습니다.")
            else:
                logger.info("설정 파일이 없어 기본 설정을 사용합니다.")
                self.save_config()
        except Exception as e:
            logger.error(f"설정 로드 중 오류 발생: {e}")

    def save_config(self):
        """
        현재 설정값을 config.json 파일로 저장합니다.
        """
        try:
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            logger.info("설정 값을 파일에 저장했습니다.")
        except Exception as e:
            logger.error(f"설정 저장 중 오류 발생: {e}")

    def get(self, key, default=None):
        """설정 값을 가져옵니다."""
        return self.config.get(key, default)

    def set(self, key, value):
        """설정 값을 변경하고 바로 저장합니다."""
        self.config[key] = value
        self.save_config()

    def set_auto_start(self, enabled: bool):
        """
        Windows 레지스트리에 '부팅 시 자동 실행'을 등록하거나 해제합니다.
        
        Args:
            enabled (bool): True이면 등록, False이면 해제
        """
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_SET_VALUE)
            
            if enabled:
                # 현재 실행 파일 경로 가져오기 (스크립트인 경우 python 경로 + 스크립트 경로)
                if getattr(sys, 'frozen', False):
                    app_path = sys.executable
                else:
                    app_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
                
                winreg.SetValueEx(key, self.APP_NAME, 0, winreg.REG_SZ, app_path)
                logger.info("부팅 시 자동 실행이 레지스트리에 등록되었습니다.")
            else:
                try:
                    winreg.DeleteValue(key, self.APP_NAME)
                    logger.info("부팅 시 자동 실행이 레지스트리에서 해제되었습니다.")
                except FileNotFoundError:
                    pass # 이미 없음
            
            winreg.CloseKey(key)
            self.config["auto_start"] = enabled
            self.save_config()
            return True
        except Exception as e:
            logger.error(f"자동 실행 레지스트리 작업 중 오류 발생: {e}")
            return False

if __name__ == "__main__":
    # 간단한 테스트
    cm = ConfigManager()
    print(f"Current Theme: {cm.get('theme')}")
    # cm.set_auto_start(True) # 실제 테스트 시 주의
