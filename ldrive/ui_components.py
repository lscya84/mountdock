import os
import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QComboBox, QPushButton, QRadioButton, 
    QCheckBox, QGroupBox, QPlainTextEdit, QFormLayout,
    QSystemTrayIcon, QMenu, QScrollArea, QDialog, QLineEdit,
    QFrame, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QAction, QFont

class DriveSettingsDialog(QDialog):
    """
    드라이브 추가 및 설정을 위한 팝업 다이얼로그입니다.
    """
    def __init__(self, remotes, parent=None, profile=None):
        super().__init__(parent)
        self.profile = profile or {}
        self.remotes = remotes
        self.setWindowTitle("Drive Settings" if profile else "Add New Drive")
        self.setFixedWidth(400)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        # 1. 원격지 선택
        self.remote_combo = QComboBox()
        self.remote_combo.addItems(self.remotes)
        if "remote" in self.profile:
            self.remote_combo.setCurrentText(self.profile["remote"])
        
        # 2. 드라이브 문자
        self.letter_combo = QComboBox()
        import string
        for char in reversed(string.ascii_uppercase):
            if char not in ['C', 'D']:
                self.letter_combo.addItem(f"{char}:")
        if "letter" in self.profile:
            self.letter_combo.setCurrentText(f"{self.profile['letter']}:")
        
        # 3. 드라이브 이름 (Volume Label)
        self.vol_edit = QLineEdit(self.profile.get("volname", ""))
        self.vol_edit.setPlaceholderText("탐색기에 표시될 이름 (비워두면 리모트명)")

        # 4. 루트 폴더
        self.root_edit = QLineEdit(self.profile.get("root_folder", "/"))
        
        # 5. VFS 모드
        self.vfs_combo = QComboBox()
        self.vfs_combo.addItems(["full (Media)", "writes (Work)", "off", "minimal"])
        vfs_val = self.profile.get("vfs_mode", "full")
        index = self.vfs_combo.findText(vfs_val, Qt.MatchFlag.MatchContains)
        if index >= 0: self.vfs_combo.setCurrentIndex(index)
        
        # 6. 커스텀 인자
        self.args_edit = QLineEdit(self.profile.get("custom_args", ""))
        self.args_edit.setPlaceholderText("--dir-cache-time 72h 등")

        form.addRow("Remote Target:", self.remote_combo)
        form.addRow("Drive Letter:", self.letter_combo)
        form.addRow("Volume Label:", self.vol_edit)
        form.addRow("Root Folder:", self.root_edit)
        form.addRow("VFS Cache Mode:", self.vfs_combo)
        form.addRow("Custom Arguments:", self.args_edit)
        
        layout.addLayout(form)
        
        # 버튼
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("MountButton")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_data(self):
        return {
            "remote": self.remote_combo.currentText(),
            "letter": self.letter_combo.currentText().replace(":", ""),
            "volname": self.vol_edit.text(),
            "root_folder": self.root_edit.text(),
            "vfs_mode": self.vfs_combo.currentText().split(" ")[0],
            "custom_args": self.args_edit.text()
        }

class DriveCardWidget(QFrame):
    """
    대시보드에 표시되는 개별 드라이브 카드 항목입니다.
    """
    toggle_requested = pyqtSignal(str, bool)
    edit_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, profile):
        super().__init__()
        self.profile = profile
        self.is_running = False
        self.setObjectName("DriveCard")
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)

        # 왼쪽: 드라이브 아이콘/문자
        self.letter_label = QLabel(f"{self.profile['letter']}:")
        self.letter_label.setObjectName("DriveCardLetter")
        layout.addWidget(self.letter_label)

        # 중앙: 리모트 정보
        info_layout = QVBoxLayout()
        display_name = self.profile.get('volname') or self.profile['remote']
        self.remote_label = QLabel(display_name)
        self.remote_label.setObjectName("DriveCardTitle")
        self.status_label = QLabel("Disconnected")
        self.status_label.setObjectName("StatusDisconnected")
        info_layout.addWidget(self.remote_label)
        info_layout.addWidget(self.status_label)
        layout.addLayout(info_layout)
        
        layout.addStretch()

        # 오른쪽: 버튼들
        self.toggle_btn = QPushButton("▶ 시작 (Start)")
        self.toggle_btn.setObjectName("MountButton")
        self.toggle_btn.setFixedSize(110, 40)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._on_toggle)
        
        self.edit_btn = QPushButton("⚙")
        self.edit_btn.setObjectName("IconButton")
        self.edit_btn.setFixedSize(35, 35)
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.profile["id"]))
        
        self.delete_btn = QPushButton("🗑")
        self.delete_btn.setObjectName("IconButton")
        self.delete_btn.setFixedSize(35, 35)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.profile["id"]))

        layout.addWidget(self.toggle_btn)
        layout.addWidget(self.edit_btn)
        layout.addWidget(self.delete_btn)

    def _on_toggle(self):
        self.toggle_requested.emit(self.profile["id"], not self.is_running)

    def set_status(self, status):
        self.status_label.setText(status)
        if status == "Connected":
            self.status_label.setObjectName("StatusConnected")
            self.toggle_btn.setText("⏹ 정지 (Stop)")
            self.toggle_btn.setObjectName("UnmountButton")
            self.is_running = True
        elif "Reconnecting" in status:
            self.status_label.setObjectName("StatusReconnecting")
        else:
            self.status_label.setObjectName("StatusDisconnected")
            self.toggle_btn.setText("▶ 시작 (Start)")
            self.toggle_btn.setObjectName("MountButton")
            self.is_running = False
        
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)

class GlobalSettingsDialog(QDialog):
    """전역 Rclone 및 시스템 설정을 위한 다이얼로그입니다."""
    def __init__(self, config_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Global Settings")
        self.setFixedWidth(500)
        self.config_dict = config_dict
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. 경로 설정 그룹
        path_group = QGroupBox("Rclone Paths")
        path_layout = QFormLayout()
        
        self.rclone_edit = QLineEdit(self.config_dict.get("rclone_path", "rclone.exe"))
        rclone_btn = QPushButton("Browse...")
        rclone_btn.clicked.connect(lambda: self._browse_file(self.rclone_edit, "Rclone Executable"))
        h1 = QHBoxLayout()
        h1.addWidget(self.rclone_edit)
        h1.addWidget(rclone_btn)
        
        self.conf_edit = QLineEdit(self.config_dict.get("rclone_conf_path", ""))
        conf_btn = QPushButton("Browse...")
        conf_btn.clicked.connect(lambda: self._browse_file(self.conf_edit, "Rclone Config"))
        h2 = QHBoxLayout()
        h2.addWidget(self.conf_edit)
        h2.addWidget(conf_btn)
        
        path_layout.addRow("Rclone.exe:", h1)
        path_layout.addRow("Rclone.conf:", h2)
        path_group.setLayout(path_layout)
        layout.addWidget(path_group)
        
        # 2. 시스템 설정 그룹
        sys_group = QGroupBox("System Settings")
        sys_layout = QVBoxLayout()
        self.auto_start_check = QCheckBox("윈도우 시작 시 자동 실행 (Auto Start)")
        self.auto_start_check.setChecked(self.config_dict.get("auto_start", False))
        
        self.tray_start_check = QCheckBox("앱 실행 시 트레이로 시작 (Start minimized to Tray)")
        self.tray_start_check.setChecked(self.config_dict.get("start_minimized", False))
        
        sys_layout.addWidget(self.auto_start_check)
        sys_layout.addWidget(self.tray_start_check)
        sys_group.setLayout(sys_layout)
        layout.addWidget(sys_group)
        
        # 저장 / 취소
        btns = QHBoxLayout()
        save = QPushButton("Save Settings")
        save.setObjectName("MountButton")
        save.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(save)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def _browse_file(self, edit_widget, file_type):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, f"Select {file_type}", "", "All Files (*)")
        if path:
            edit_widget.setText(path)

    def get_data(self):
        return {
            "rclone_path": self.rclone_edit.text(),
            "rclone_conf_path": self.conf_edit.text(),
            "auto_start": self.auto_start_check.isChecked(),
            "start_minimized": self.tray_start_check.isChecked()
        }

class LDriveMainWindow(QMainWindow):
    """
    다중 마운트 대시보드 스타일의 메인 윈도우입니다.
    """
    add_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    theme_toggle_requested = pyqtSignal() # 테마 토글 시그널 추가

    def __init__(self):
        super().__init__()
        self.setWindowTitle("L-Drive Pro - Dashboard")
        self.setFixedSize(600, 750)
        self._init_ui()

    def changeEvent(self, event):
        """창 상태 변경 이벤트: 최소화 시 트레이로 숨깁니다."""
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                self.hide()
                event.ignore()
        super().changeEvent(event)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        
        # 헤더
        header = QHBoxLayout()
        title = QLabel("L-Drive Pro")
        title.setObjectName("AppTitle")
        title.setStyleSheet("font-size: 20pt; font-weight: bold; color: #3498db;")
        
        self.theme_btn = QPushButton("🌙 Dark") # 초기값 (main에서 갱신됨)
        self.theme_btn.setFixedWidth(80)
        self.theme_btn.clicked.connect(self.theme_toggle_requested.emit)

        self.settings_btn = QPushButton("⚙ Settings")
        self.settings_btn.setFixedWidth(100)
        self.settings_btn.clicked.connect(self.settings_requested.emit)

        self.add_btn = QPushButton("➕ Add Drive")
        self.add_btn.setObjectName("MountButton")
        self.add_btn.setFixedWidth(120)
        self.add_btn.clicked.connect(self.add_requested.emit)
        
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.theme_btn)
        header.addWidget(self.settings_btn)
        header.addWidget(self.add_btn)
        main_layout.addLayout(header)

        # 중앙 카드 영역 (Scroll Area)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        
        self.container = QWidget()
        self.card_layout = QVBoxLayout(self.container)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.card_layout.setSpacing(10)
        
        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll)

        # 로그 영역
        log_group = QGroupBox("Activity Logs")
        log_layout = QVBoxLayout()
        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        log_layout.addWidget(self.log_viewer)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

    def clear_cards(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def add_card(self, card_widget):
        self.card_layout.addWidget(card_widget)

    def _apply_styles(self, theme_name="light"):
        """지정된 테마 파일(.qss)을 로드하여 적용합니다."""
        filename = f"{theme_name}_theme.qss"
        qss_path = self.resource_path(os.path.join("assets", "styles", filename))
        
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
            
            # 버튼 텍스트 변경
            if theme_name == "dark":
                self.theme_btn.setText("☀️ Light")
            else:
                self.theme_btn.setText("🌙 Dark")
        else:
            print(f"Warning: Stylesheet not found at {qss_path}")

    @staticmethod
    def resource_path(relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def append_log(self, message: str):
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_viewer.appendPlainText(f"[{timestamp}] {message}")
        self.log_viewer.verticalScrollBar().setValue(self.log_viewer.verticalScrollBar().maximum())

class LDriveTrayIcon(QSystemTrayIcon):
    show_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, icon, parent=None):
        super().__init__(icon, parent)
        self.setToolTip("L-Drive Pro")
        self._setup_menu()

    def _setup_menu(self):
        menu = QMenu()
        show_action = QAction("Open Dashboard", self)
        show_action.triggered.connect(self.show_requested.emit)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.exit_requested.emit)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(exit_action)
        self.setContextMenu(menu)
