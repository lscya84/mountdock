import os
import sys
import string
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QComboBox, QPushButton, QCheckBox, 
    QGroupBox, QPlainTextEdit, QFormLayout,
    QSystemTrayIcon, QMenu, QScrollArea, QDialog, QLineEdit,
    QFrame, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QEvent
from PyQt6.QtGui import QIcon, QAction, QFont, QCursor

class DriveSettingsDialog(QDialog):
    def __init__(self, remotes, parent=None, profile=None):
        super().__init__(parent)
        self.profile = profile or {}
        self.remotes = remotes
        self.setWindowTitle("Drive Settings" if profile else "Connect New Drive")
        self.setFixedWidth(380)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
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
        if "vfs_mode" in self.profile: self.vfs_combo.setCurrentText(self.profile["vfs_mode"])
        
        form.addRow("Remote Target:", self.remote_combo)
        form.addRow("Drive Letter:", self.letter_combo)
        form.addRow("Volume Label:", self.vol_edit)
        form.addRow("Root Path:", self.root_edit)
        form.addRow("VFS Cache:", self.vfs_combo)
        layout.addLayout(form)
        
        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("GhostBtn")
        save_btn = QPushButton("Save & Close")
        save_btn.setObjectName("AccentBtn")
        
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
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

class DriveCardWidget(QFrame):
    toggle_requested = pyqtSignal(str, bool)
    edit_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, profile):
        super().__init__()
        self.profile = profile
        self.is_running = False
        self.setObjectName("DriveCard")
        self.setFixedHeight(82)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(15)

        # 1. Circular Badge
        self.badge = QLabel(self.profile['letter'])
        self.badge.setObjectName("LetterBadge")
        self.badge.setFixedSize(44, 44)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.badge)

        # 2. Text Content (Title & Remote)
        info_layout = QVBoxLayout()
        info_layout.setSpacing(1)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        name = self.profile.get('volname') or self.profile['remote']
        self.title_label = QLabel(name)
        self.title_label.setObjectName("CardTitle")
        
        self.status_label = QLabel("Disconnected") # Status text + Remote
        self.status_label.setObjectName("CardStatus")
        
        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.status_label)
        layout.addLayout(info_layout)
        
        layout.addStretch()

        # 3. Mount/Unmount Button
        self.toggle_btn = QPushButton("Mount")
        self.toggle_btn.setObjectName("MountBtn_Solid")
        self.toggle_btn.setFixedSize(94, 34)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._on_toggle)
        layout.addWidget(self.toggle_btn)

        # 4. Tiny Tools
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setObjectName("GhostBtn")
        self.edit_btn.setFixedSize(50, 34)
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.profile["id"]))
        
        self.delete_btn = QPushButton("Del")
        self.delete_btn.setObjectName("GhostBtn")
        self.delete_btn.setFixedSize(45, 34)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.profile["id"]))

        layout.addWidget(self.edit_btn)
        layout.addWidget(self.delete_btn)

    def _on_toggle(self):
        self.toggle_requested.emit(self.profile["id"], not self.is_running)

    def set_status(self, status):
        self.status_label.setText(status)
        if status == "Connected":
            self.toggle_btn.setText("Unmount")
            self.toggle_btn.setObjectName("UnmountBtn_Solid")
            self.is_running = True
        else:
            self.toggle_btn.setText("Mount")
            self.toggle_btn.setObjectName("MountBtn_Solid")
            self.is_running = False
            if "Wait" in status: self.status_label.setText("Mounting...")
        
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

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            self.hide()
            event.ignore()
        super().changeEvent(event)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)
        
        # Header Area
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 5)
        self.app_logo = QLabel("L-Drive Pro")
        self.app_logo.setObjectName("MainLogo")
        header.addWidget(self.app_logo)
        header.addStretch()
        
        # Pill Shape Action Buttons
        self.theme_btn = QPushButton("Theme")
        self.theme_btn.setObjectName("GhostBtn")
        self.theme_btn.setFixedSize(70, 32)
        
        self.settings_btn = QPushButton("Options")
        self.settings_btn.setObjectName("GhostBtn")
        self.settings_btn.setFixedSize(75, 32)

        self.add_btn = QPushButton("+ Add")
        self.add_btn.setObjectName("AccentBtn")
        self.add_btn.setFixedSize(75, 32)
        
        self.theme_btn.clicked.connect(self.theme_toggle_requested.emit)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        self.add_btn.clicked.connect(self.add_requested.emit)
        
        header.addWidget(self.theme_btn)
        header.addWidget(self.settings_btn)
        header.addWidget(self.add_btn)
        main_layout.addLayout(header)

        # Scrollable Area (No Horizontal Scroll)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.card_layout = QVBoxLayout(self.container)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.card_layout.setSpacing(12)
        self.card_layout.setContentsMargins(0, 5, 0, 5)
        
        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll)

        # Compact Activity Monitor
        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setFixedHeight(120)
        self.log_viewer.setObjectName("ActivityLogBox")
        main_layout.addWidget(self.log_viewer)

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
            self.log_viewer.appendHtml(f'<span style="color: #C42B1C; font-weight: 600;">[{timestamp}] {message}</span>')
        else:
            self.log_viewer.appendPlainText(f"[{timestamp}] {message}")
        self.log_viewer.verticalScrollBar().setValue(self.log_viewer.verticalScrollBar().maximum())

class GlobalSettingsDialog(QDialog):
    def __init__(self, config_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("System Preferences")
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
        self.minimized = QCheckBox("Start hidden in System Tray")
        
        self.auto_start.setChecked(self.config_dict.get("auto_start", False))
        self.minimized.setChecked(self.config_dict.get("start_minimized", False))
        
        form.addRow("Binary Path:", self.rclone_edit)
        form.addRow("Config Path:", self.conf_edit)
        layout.addLayout(form)
        layout.addWidget(self.auto_start)
        layout.addWidget(self.minimized)
        
        btns = QHBoxLayout()
        save = QPushButton("Apply Settings")
        save.setObjectName("AccentBtn")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self.accept)
        btns.addStretch()
        btns.addWidget(save)
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
        ex = QAction("Quit L-Drive", self); ex.triggered.connect(self.exit_requested.emit)
        menu.addAction(show); menu.addSeparator(); menu.addAction(ex)
        self.setContextMenu(menu)
