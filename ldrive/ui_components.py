import os
import sys
import string
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QComboBox, QPushButton, QCheckBox, 
    QScrollArea, QDialog, QLineEdit, QFrame, 
    QPlainTextEdit, QProgressBar, QFormLayout,
    QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QEvent
from PyQt6.QtGui import QIcon, QAction, QFont, QCursor

# --- Designer Quality UI Components ---

class DriveCardWidget(QFrame):
    toggle_requested = pyqtSignal(str, bool)
    edit_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, profile):
        super().__init__()
        self.profile = profile
        self.is_running = False
        self.setObjectName("DriveCard")
        self.setFixedHeight(115) # cards with more vertical space for progress bar
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(18)

        # 1. Square Badge for Letter
        self.badge = QLabel(self.profile['letter'])
        self.badge.setObjectName("LetterBadge")
        self.badge.setFixedSize(50, 50)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.badge)

        # 2. Information Area
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        name_val = self.profile.get('volname') or self.profile['remote']
        self.name_label = QLabel(name_val)
        self.name_label.setObjectName("DriveName")
        
        self.status_label = QLabel("Disconnected")
        self.status_label.setObjectName("StatusLabel")
        
        # Micro Progress Bar for high visual density
        self.progress = QProgressBar()
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setObjectName("SlimProgress")
        
        info_layout.addWidget(self.name_label)
        info_layout.addWidget(self.status_label)
        info_layout.addWidget(self.progress)
        layout.addLayout(info_layout)
        
        layout.addStretch()

        # 3. Connect/Action Section
        self.toggle_btn = QPushButton("Connect")
        self.toggle_btn.setObjectName("ConnectBtn") # Blue background in QSS
        self.toggle_btn.setFixedSize(100, 38)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._on_toggle)
        
        self.edit_btn = QPushButton("⚙") # Fluent style icon sim
        self.edit_btn.setObjectName("SubBtn")
        self.edit_btn.setFixedSize(40, 38)
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.profile["id"]))
        
        self.delete_btn = QPushButton("🗑")
        self.delete_btn.setObjectName("SubBtn")
        self.delete_btn.setFixedSize(40, 38)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.profile["id"]))

        layout.addWidget(self.toggle_btn)
        layout.addWidget(self.edit_btn)
        layout.addWidget(self.delete_btn)

    def _on_toggle(self):
        self.toggle_requested.emit(self.profile["id"], not self.is_running)

    def set_status(self, status):
        self.status_label.setText(status)
        if status == "Connected":
            self.toggle_btn.setText("Disconnect")
            self.toggle_btn.setProperty("isUnmount", "true")
            self.progress.setValue(100)
            self.is_running = True
        else:
            self.toggle_btn.setText("Connect")
            self.toggle_btn.setProperty("isUnmount", "false")
            self.progress.setValue(0)
            self.is_running = False
        
        # Refresh for isUnmount property in QSS
        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)

class LDriveMainWindow(QMainWindow):
    add_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    theme_toggle_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("L-Drive Pro")
        self.setFixedSize(450, 620) 
        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header Area
        header = QWidget()
        header.setFixedHeight(70)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(25, 10, 25, 10)
        
        self.title_label = QLabel("L-Drive Pro")
        self.title_label.setObjectName("AppHeader")
        h_layout.addWidget(self.title_label)
        h_layout.addStretch()
        
        # Tools
        self.theme_btn = QPushButton("◑")
        self.theme_btn.setObjectName("IconicBtn")
        self.theme_btn.setFixedSize(36, 36)
        
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setObjectName("IconicBtn")
        self.settings_btn.setFixedSize(36, 36)
        
        self.add_btn = QPushButton("+ Add")
        self.add_btn.setObjectName("ConnectBtn") # Use same style but maybe padding different
        self.add_btn.setFixedHeight(34)
        
        self.theme_btn.clicked.connect(self.theme_toggle_requested.emit)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        self.add_btn.clicked.connect(self.add_requested.emit)
        
        h_layout.addWidget(self.theme_btn)
        h_layout.addWidget(self.settings_btn)
        h_layout.addSpacing(5)
        h_layout.addWidget(self.add_btn)
        main_layout.addWidget(header)

        # Main Body - Scrolling
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.card_layout = QVBoxLayout(self.container)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.card_layout.setSpacing(14)
        self.card_layout.setContentsMargins(25, 10, 25, 20)
        
        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll)

        # Minimal Log
        self.log_container = QFrame()
        self.log_container.setObjectName("LogSection")
        self.log_container.setFixedHeight(85) # Minimized as requested
        log_layout = QVBoxLayout(self.log_container)
        log_layout.setContentsMargins(20, 10, 20, 5)
        
        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setObjectName("LogViewer")
        log_layout.addWidget(self.log_viewer)
        
        main_layout.addWidget(self.log_container)

    def clear_cards(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def add_card(self, card_widget):
        self.card_layout.addWidget(card_widget)

    def _apply_styles(self, theme_name="light"):
        qss_path = self.resource_path(os.path.join("assets", "styles", f"{theme_name}_theme.qss"))
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    @staticmethod
    def resource_path(relative_path):
        try: base_path = sys._MEIPASS
        except: base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def append_log(self, message: str):
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        if "[Error]" in message or "실패" in message:
            self.log_viewer.appendHtml(f'<span style="color: #E81123;">[{timestamp}] {message}</span>')
        else:
            self.log_viewer.appendPlainText(f"[{timestamp}] {message}")
        self.log_viewer.verticalScrollBar().setValue(self.log_viewer.verticalScrollBar().maximum())

# --- Dialogs & Trays ---

class DriveSettingsDialog(QDialog):
    def __init__(self, remotes, parent=None, profile=None):
        super().__init__(parent)
        self.profile = profile or {}
        self.remotes = remotes
        self.setWindowTitle("Mount Configuration")
        self.setFixedWidth(380)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(25, 25, 25, 25)
        
        form = QFormLayout()
        self.remote_combo = QComboBox()
        self.remote_combo.addItems(self.remotes)
        if "remote" in self.profile: self.remote_combo.setCurrentText(self.profile["remote"])
        
        self.letter_combo = QComboBox()
        for char in reversed(string.ascii_uppercase):
            if char not in ['C', 'D']: self.letter_combo.addItem(f"{char}:")
        if "letter" in self.profile: self.letter_combo.setCurrentText(f"{self.profile['letter']}:")
        
        self.vol_edit = QLineEdit(self.profile.get("volname", ""))
        self.vol_edit.setPlaceholderText("Drive Display Name")

        self.root_edit = QLineEdit(self.profile.get("root_folder", "/"))
        self.vfs_combo = QComboBox()
        self.vfs_combo.addItems(["full", "writes", "off", "minimal"])
        
        form.addRow("Remote:", self.remote_combo)
        form.addRow("Letter:", self.letter_combo)
        form.addRow("Volume Name:", self.vol_edit)
        form.addRow("Root Folder:", self.root_edit)
        form.addRow("VFS Cache:", self.vfs_combo)
        layout.addLayout(form)
        
        btns = QHBoxLayout()
        btns.addStretch()
        sv = QPushButton("Save Drive")
        sv.setObjectName("ConnectBtn")
        cl = QPushButton("Cancel")
        cl.setObjectName("SubBtn")
        sv.clicked.connect(self.accept)
        cl.clicked.connect(self.reject)
        btns.addWidget(cl); btns.addWidget(sv)
        layout.addLayout(btns)

    def get_data(self):
        return {
            "remote": self.remote_combo.currentText(),
            "letter": self.letter_combo.currentText().replace(":", ""),
            "volname": self.vol_edit.text(),
            "root_folder": self.root_edit.text(),
            "vfs_mode": self.vfs_combo.currentText(),
            "custom_args": ""
        }

class GlobalSettingsDialog(QDialog):
    def __init__(self, config_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Application Options")
        self.setFixedWidth(360)
        self.config_dict = config_dict
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        form = QFormLayout()
        self.rclone_edit = QLineEdit(self.config_dict.get("rclone_path", "rclone.exe"))
        self.conf_edit = QLineEdit(self.config_dict.get("rclone_conf_path", ""))
        self.auto_start = QCheckBox("Automatically start with Windows")
        self.auto_start.setChecked(self.config_dict.get("auto_start", False))
        self.minimized = QCheckBox("Launch minimized to system tray")
        self.minimized.setChecked(self.config_dict.get("start_minimized", False))
        
        form.addRow("Rclone Path:", self.rclone_edit)
        form.addRow("Config Path:", self.conf_edit)
        layout.addLayout(form)
        layout.addWidget(self.auto_start)
        layout.addWidget(self.minimized)
        
        btns = QHBoxLayout()
        btns.addStretch()
        sv = QPushButton("Apply All")
        sv.setObjectName("ConnectBtn")
        sv.clicked.connect(self.accept)
        btns.addWidget(sv)
        layout.addLayout(btns)

    def get_data(self):
        return {
            "rclone_path": self.rclone_edit.text(),
            "rclone_conf_path": self.conf_edit.text(),
            "auto_start": self.auto_start.isChecked(),
            "start_minimized": self.minimized.isChecked()
        }

class LDriveTrayIcon(QSystemTrayIcon):
    show_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, icon, parent=None):
        super().__init__(icon, parent)
        menu = QMenu()
        show = QAction("Open Dashboard", self); show.triggered.connect(self.show_requested.emit)
        ex = QAction("Exit L-Drive", self); ex.triggered.connect(self.exit_requested.emit)
        menu.addAction(show); menu.addSeparator(); menu.addAction(ex)
        self.setContextMenu(menu)
