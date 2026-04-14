import json
import os
import logging
import winreg
import sys
import uuid

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
    L-Drive Pro의 다중 프로필 설정 및 Windows 시스템 통합을 관리하는 클래스입니다.
    여러 개의 마운트 정보를 리스트 형태로 저장하고 관리합니다.
    """
    
    CONFIG_FILE = "config.json"
    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "L-DrivePro"

    def __init__(self):
        self.config = {
            "theme": "light",
            "auto_start": False,
            "start_minimized": False, # 트레이 모드 시작 옵션 추가
            "profiles": [],
            "rclone_path": "rclone.exe",
            "rclone_conf_path": ""
        }
        self.load_config()

    def load_config(self):
        """config.json 파일에서 다중 프로필 설정을 로드합니다."""
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                    self.config.update(loaded_data)
                logger.info("다중 프로필 설정 파일을 로드했습니다.")
            else:
                logger.info("설정 파일이 없어 기본 설정을 생성합니다.")
                self.save_config()
        except Exception as e:
            logger.error(f"설정 로드 중 오류 발생: {e}")

    def save_config(self):
        """현재 설정값을 config.json 파일로 저장합니다."""
        try:
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"설정 저장 중 오류 발생: {e}")

    def get_profiles(self):
        """모든 드라이브 프로필 목록을 반환합니다."""
        return self.config.get("profiles", [])

    def add_profile(self, profile_data):
        """새 드라이브 프로필을 추가합니다."""
        if "id" not in profile_data:
            profile_data["id"] = str(uuid.uuid4())
        self.config["profiles"].append(profile_data)
        self.save_config()
        return profile_data["id"]

    def update_profile(self, profile_id, updated_data):
        """기존 프로필 정보를 수정합니다."""
        for i, profile in enumerate(self.config["profiles"]):
            if profile["id"] == profile_id:
                self.config["profiles"][i].update(updated_data)
                self.save_config()
                return True
        return False

    def delete_profile(self, profile_id):
        """지정된 프로필을 삭제합니다."""
        original_count = len(self.config["profiles"])
        self.config["profiles"] = [p for p in self.config["profiles"] if p["id"] != profile_id]
        if len(self.config["profiles"]) < original_count:
            self.save_config()
            return True
        return False

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()

    def set_auto_start(self, enabled: bool):
        """Windows 레지스트리에 자동 실행을 등록/해제합니다."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_SET_VALUE)
            if enabled:
                if getattr(sys, 'frozen', False):
                    app_path = sys.executable
                else:
                    app_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
                winreg.SetValueEx(key, self.APP_NAME, 0, winreg.REG_SZ, app_path)
            else:
                try:
                    winreg.DeleteValue(key, self.APP_NAME)
                except FileNotFoundError:
                    pass
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
