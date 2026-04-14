import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QComboBox, QPushButton, QRadioButton, 
    QCheckBox, QGroupBox, QPlainTextEdit, QFormLayout,
    QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QAction

class LDriveTrayIcon(QSystemTrayIcon):
    """
    시스템 트레이 아이콘을 관리하는 클래스입니다.
    """
    show_requested = pyqtSignal()
    unmount_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, icon, parent=None):
        super().__init__(icon, parent)
        self.setToolTip("L-Drive Pro")
        self._setup_menu()

    def _setup_menu(self):
        menu = QMenu()
        
        show_action = QAction("열기 (Show)", self)
        show_action.triggered.connect(self.show_requested.emit)
        
        unmount_action = QAction("마운트 해제 (Unmount)", self)
        unmount_action.triggered.connect(self.unmount_requested.emit)
        
        exit_action = QAction("종료 (Exit)", self)
        exit_action.triggered.connect(self.exit_requested.emit)
        
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(unmount_action)
        menu.addSeparator()
        menu.addAction(exit_action)
        
        self.setContextMenu(menu)


class LDriveMainWindow(QMainWindow):
    """
    L-Drive Pro의 메인 GUI 창 클래스입니다.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("L-Drive Pro")
        self.setFixedSize(500, 650)
        
        self._init_ui()
        self._apply_styles()

    def _init_ui(self):
        # 메인 위젯 및 레이아웃
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 1. 상단 제목
        title_label = QLabel("L-Drive (Live-Drive) Pro")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 18pt; font-weight: bold; color: #4a9eff; margin-bottom: 10px;")
        main_layout.addWidget(title_label)

        # 2. 설정 그룹 (리모트, 드라이브 선택)
        config_group = QGroupBox("Mount Configuration")
        config_layout = QFormLayout()
        config_layout.setSpacing(10)

        self.remote_combo = QComboBox()
        self.remote_combo.setPlaceholderText("리모트를 선택하세요...")
        
        self.drive_combo = QComboBox()
        # Z부터 A까지 드라이브 문자 추가
        import string
        for char in reversed(string.ascii_uppercase):
            if char not in ['C', 'D']: # 시스템 기본 제외
                self.drive_combo.addItem(f"{char}:")

        config_layout.addRow("Remote Target:", self.remote_combo)
        config_layout.addRow("Drive Letter:", self.drive_combo)
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)

        # 3. VFS 모드 선택
        vfs_group = QGroupBox("VFS Cache Mode")
        vfs_layout = QHBoxLayout()
        self.radio_media = QRadioButton("Media Mode (Full)")
        self.radio_work = QRadioButton("Work Mode (Writes)")
        self.radio_media.setChecked(True)
        vfs_layout.addWidget(self.radio_media)
        vfs_layout.addWidget(self.radio_work)
        vfs_group.setLayout(vfs_layout)
        main_layout.addWidget(vfs_group)

        # 4. 버튼 영역
        btn_layout = QHBoxLayout()
        self.mount_btn = QPushButton("Mount")
        self.mount_btn.setObjectName("MountButton")
        self.mount_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.unmount_btn = QPushButton("Unmount")
        self.unmount_btn.setObjectName("UnmountButton")
        self.unmount_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        btn_layout.addWidget(self.mount_btn)
        btn_layout.addWidget(self.unmount_btn)
        main_layout.addLayout(btn_layout)

        # 5. 상태 표시 레이블
        status_container = QHBoxLayout()
        status_container.addWidget(QLabel("Current Status:"))
        self.status_label = QLabel("Disconnected")
        self.status_label.setObjectName("StatusLabel")
        status_container.addWidget(self.status_label)
        status_container.addStretch()
        
        self.auto_start_check = QCheckBox("Start automatically with Windows")
        status_container.addWidget(self.auto_start_check)
        main_layout.addLayout(status_container)

        # 6. 로그 뷰어
        log_group = QGroupBox("Activity Logs")
        log_layout = QVBoxLayout()
        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setPlaceholderText("Application logs will be displayed here...")
        log_layout.addWidget(self.log_viewer)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

    def _apply_styles(self):
        """작성된 QSS 파일을 로드하여 테마를 적용합니다."""
        qss_path = os.path.join(os.getcwd(), "assets", "styles", "dark_theme.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        else:
            print(f"Warning: Stylesheet not found at {qss_path}")

    def append_log(self, message: str):
        """로그 뷰어에 텍스트를 추가합니다."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_viewer.appendPlainText(f"[{timestamp}] {message}")
        # 자동 스크롤
        self.log_viewer.verticalScrollBar().setValue(
            self.log_viewer.verticalScrollBar().maximum()
        )

    def set_status(self, status: str, color: str = None):
        """상태 레이블 문구와 색상을 변경합니다."""
        self.status_label.setText(status)
        if color:
            self.status_label.setStyleSheet(f"color: {color};")
        elif status == "Connected":
            self.status_label.setStyleSheet("color: #4caf50;")
        elif "Reconnecting" in status:
            self.status_label.setStyleSheet("color: #ffc107;")
        else:
            self.status_label.setStyleSheet("color: #ff9800;")
