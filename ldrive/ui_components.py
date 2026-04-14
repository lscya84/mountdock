import os
import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QComboBox, QPushButton, QRadioButton, 
    QCheckBox, QGroupBox, QPlainTextEdit, QFormLayout,
    QSystemTrayIcon, QMenu, QScrollArea, QDialog, QLineEdit,
    QFrame, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QEvent
from PyQt6.QtGui import QIcon, QAction, QFont, QPixmap

class DriveSettingsDialog(QDialog):
    """
    드라이브 추가 및 설정을 위한 고해상도 다이얼로그입니다.
    """
    def __init__(self, remotes, parent=None, profile=None):
        super().__init__(parent)
        self.profile = profile or {}
        self.remotes = remotes
        self.setWindowTitle("Drive Settings" if profile else "Add New Drive")
        self.setFixedWidth(450)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        form = QFormLayout()
        form.setVerticalSpacing(15)
        
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
        self.vol_edit.setPlaceholderText("탐색기 표시 이름 (예: 작업용 드라이브)")

        # 4. 루트 폴더
        self.root_edit = QLineEdit(self.profile.get("root_folder", "/"))
        
        # 5. VFS 모드
        self.vfs_combo = QComboBox()
        self.vfs_combo.addItems(["full (Media Optimization)", "writes (General Work)", "off", "minimal"])
        vfs_val = self.profile.get("vfs_mode", "full")
        index = self.vfs_combo.findText(vfs_val, Qt.MatchFlag.MatchContains)
        if index >= 0: self.vfs_combo.setCurrentIndex(index)
        
        # 6. 커스텀 인자
        self.args_edit = QLineEdit(self.profile.get("custom_args", ""))
        self.args_edit.setPlaceholderText("--dir-cache-time 72h 등")

        form.addRow("Remote Target", self.remote_combo)
        form.addRow("Drive Letter", self.letter_combo)
        form.addRow("Volume Label", self.vol_edit)
        form.addRow("Root Folder", self.root_edit)
        form.addRow("VFS Cache Mode", self.vfs_combo)
        form.addRow("Custom Arguments", self.args_edit)
        
        layout.addLayout(form)
        
        # 버튼 영역
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("MountButton")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
    SaaS 스타일의 고해상도 드라이브 카드 위젯입니다.
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
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 1. 드라이브 문자 (강조)
        self.letter_label = QLabel(f"{self.profile['letter']}")
        self.letter_label.setObjectName("DriveCardLetter")
        self.letter_label.setFixedWidth(50)
        self.letter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.letter_label)

        # 2. 정보 텍스트 레이아웃
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        display_name = self.profile.get('volname') or self.profile['remote']
        if not display_name: display_name = "Untitled Drive"
            
        self.vol_label = QLabel(display_name)
        self.vol_label.setObjectName("DriveCardTitle")
        
        self.remote_label = QLabel(f"Remote: {self.profile['remote']}")
        self.remote_label.setObjectName("DriveCardRemote")
        
        self.status_label = QLabel("Disconnected")
        self.status_label.setObjectName("StatusDisconnected")
        
        info_layout.addWidget(self.vol_label)
        info_layout.addWidget(self.remote_label)
        info_layout.addWidget(self.status_label)
        layout.addLayout(info_layout)
        
        layout.addStretch()

        # 3. 액션 버튼 영역
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        # 시작/중지 버튼 (알약 모양)
        self.toggle_btn = QPushButton("Start")
        self.toggle_btn.setObjectName("MountButton")
        self.toggle_btn.setFixedSize(90, 42)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._on_toggle)
        
        # 수정 버튼 (아이콘)
        self.edit_btn = QPushButton()
        self.edit_btn.setObjectName("IconButton")
        self.edit_btn.setFixedSize(38, 38)
        self.edit_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogDetailedView))
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.profile["id"]))
        
        # 삭제 버튼 (아이콘)
        self.delete_btn = QPushButton()
        self.delete_btn.setObjectName("IconButton")
        self.delete_btn.setFixedSize(38, 38)
        self.delete_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_TrashIcon))
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.profile["id"]))

        action_layout.addWidget(self.toggle_btn)
        action_layout.addWidget(self.edit_btn)
        action_layout.addWidget(self.delete_btn)
        layout.addLayout(action_layout)

    def _on_toggle(self):
        self.toggle_requested.emit(self.profile["id"], not self.is_running)

    def set_status(self, status):
        self.status_label.setText(status)
        if status == "Connected":
            self.status_label.setObjectName("StatusConnected")
            self.toggle_btn.setText("Stop")
            self.toggle_btn.setObjectName("UnmountButton")
            self.is_running = True
        elif "Reconnecting" in status:
            self.status_label.setObjectName("StatusReconnecting")
        else:
            self.status_label.setObjectName("StatusDisconnected")
            self.toggle_btn.setText("Start")
            self.toggle_btn.setObjectName("MountButton")
            self.is_running = False
        
        # 스타일 리프레시
        for widget in [self.status_label, self.toggle_btn]:
            widget.style().unpolish(widget)
            widget.style().polish(widget)

class GlobalSettingsDialog(QDialog):
    """
    전역 Rclone 및 시스템 설정을 위한 현대적인 다이얼로그입니다.
    """
    def __init__(self, config_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Global Settings")
        self.setFixedWidth(520)
        self.config_dict = config_dict
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(25)
        
        # 1. 경로 설정 섹션
        path_group = QGroupBox("Rclone Environment")
        path_layout = QFormLayout()
        path_layout.setVerticalSpacing(15)
        
        self.rclone_edit = QLineEdit(self.config_dict.get("rclone_path", "rclone.exe"))
        rclone_btn = QPushButton("Browse")
        rclone_btn.setFixedWidth(80)
        rclone_btn.clicked.connect(lambda: self._browse_file(self.rclone_edit, "Rclone Executable"))
        h1 = QHBoxLayout()
        h1.addWidget(self.rclone_edit)
        h1.addWidget(rclone_btn)
        
        self.conf_edit = QLineEdit(self.config_dict.get("rclone_conf_path", ""))
        conf_btn = QPushButton("Browse")
        conf_btn.setFixedWidth(80)
        conf_btn.clicked.connect(lambda: self._browse_file(self.conf_edit, "Rclone Config"))
        h2 = QHBoxLayout()
        h2.addWidget(self.conf_edit)
        h2.addWidget(conf_btn)
        
        path_layout.addRow("Rclone Binary", h1)
        path_layout.addRow("Config File", h2)
        path_group.setLayout(path_layout)
        layout.addWidget(path_group)
        
        # 2. 시스템 환경 설정 섹션
        sys_group = QGroupBox("General Options")
        sys_layout = QVBoxLayout()
        sys_layout.setSpacing(12)
        
        self.auto_start_check = QCheckBox("Launch L-Drive Pro on Windows startup")
        self.auto_start_check.setChecked(self.config_dict.get("auto_start", False))
        
        self.tray_start_check = QCheckBox("Start minimized in the system tray")
        self.tray_start_check.setChecked(self.config_dict.get("start_minimized", False))
        
        sys_layout.addWidget(self.auto_start_check)
        sys_layout.addWidget(self.tray_start_check)
        sys_group.setLayout(sys_layout)
        layout.addWidget(sys_group)
        
        # 하단 버튼
        btns = QHBoxLayout()
        btns.setSpacing(10)
        save = QPushButton("Save All Settings")
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
    모던 SaaS 스타일의 메인 대시보드 인터페이스입니다.
    """
    add_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    theme_toggle_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("L-Drive Pro")
        self.setFixedSize(650, 850)
        self._init_ui()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                self.hide()
                event.ignore()
        super().changeEvent(event)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(35, 40, 35, 40)
        main_layout.setSpacing(25)
        
        # --- 헤더 영역 ---
        header = QHBoxLayout()
        title = QLabel("L-Drive Pro")
        title.setObjectName("AppTitle")
        
        header.addWidget(title)
        header.addStretch()
        
        # 테마 & 설정 버튼
        self.theme_btn = QPushButton("🌙 Dark")
        self.theme_btn.setFixedWidth(90)
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.clicked.connect(self.theme_toggle_requested.emit)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setFixedWidth(100)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        
        header.addWidget(self.theme_btn)
        header.addWidget(self.settings_btn)
        main_layout.addLayout(header)

        # --- 드라이브 관리 섹션 ---
        drive_section_header = QHBoxLayout()
        drive_title = QLabel("Mounted Drives")
        drive_title.setStyleSheet("font-size: 13pt; font-weight: 700; color: #374151;")
        
        self.add_btn = QPushButton("New Drive")
        self.add_btn.setObjectName("MountButton")
        self.add_btn.setFixedWidth(110)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self.add_requested.emit)
        
        drive_section_header.addWidget(drive_title)
        drive_section_header.addStretch()
        drive_section_header.addWidget(self.add_btn)
        main_layout.addLayout(drive_section_header)

        # 스크롤 영역
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        
        self.container = QWidget()
        self.card_layout = QVBoxLayout(self.container)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.card_layout.setSpacing(15)
        self.card_layout.setContentsMargins(0, 0, 5, 0)
        
        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll)

        # --- 로그 영역 ---
        log_group = QGroupBox("Activity Logs")
        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(0, 15, 0, 0)
        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setFixedHeight(120)
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
        filename = f"{theme_name}_theme.qss"
        qss_path = self.resource_path(os.path.join("assets", "styles", filename))
        
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
            
            if theme_name == "dark":
                self.theme_btn.setText("☀️ Light")
            else:
                self.theme_btn.setText("🌙 Dark")

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
