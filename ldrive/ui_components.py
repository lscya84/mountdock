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
        self.setWindowTitle("Drive Settings" if profile else "Add New Remote")
        self.setFixedWidth(380)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
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
        
        form.addRow("Remote:", self.remote_combo)
        form.addRow("Letter:", self.letter_combo)
        form.addRow("Name:", self.vol_edit)
        form.addRow("Root Path:", self.root_edit)
        form.addRow("VFS Cache:", self.vfs_combo)
        
        layout.addLayout(form)
        
        btns = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        
        btns.addStretch()
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
        self.setMinimumHeight(70)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(12)

        # Left: Letter Box
        self.icon_box = QLabel(self.profile['letter'])
        self.icon_box.setObjectName("LetterIcon")
        self.icon_box.setFixedSize(40, 40)
        self.icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_box)

        # Middle: Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(0)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        name = self.profile.get('volname') or self.profile['remote']
        self.title_label = QLabel(name)
        self.title_label.setObjectName("DriveTitle")
        self.status_label = QLabel("Disconnected")
        self.status_label.setObjectName("StatusLabel")
        
        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.status_label)
        layout.addLayout(info_layout)
        
        layout.addStretch()

        # Right: Buttons
        self.toggle_btn = QPushButton("Mount")
        self.toggle_btn.setObjectName("MountBtn")
        self.toggle_btn.setFixedSize(90, 32)
        self.toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle_btn.clicked.connect(self._on_toggle)
        layout.addWidget(self.toggle_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setObjectName("SecondaryBtn")
        self.edit_btn.setFixedSize(50, 32)
        self.edit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.profile["id"]))
        
        self.delete_btn = QPushButton("Del")
        self.delete_btn.setObjectName("SecondaryBtn")
        self.delete_btn.setFixedSize(50, 32)
        self.delete_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.profile["id"]))

        layout.addWidget(self.edit_btn)
        layout.addWidget(self.delete_btn)

    def _on_toggle(self):
        self.toggle_requested.emit(self.profile["id"], not self.is_running)

    def set_status(self, status):
        self.status_label.setText(status)
        if status == "Connected":
            self.toggle_btn.setText("Unmount")
            self.toggle_btn.setProperty("isUnmount", "true")
            self.is_running = True
        else:
            self.toggle_btn.setText("Mount")
            self.toggle_btn.setProperty("isUnmount", "false")
            self.is_running = False
        
        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)

class LDriveMainWindow(QMainWindow):
    add_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    theme_toggle_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("L-Drive Pro")
        self.setFixedSize(450, 600)
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
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Header Row
        header = QHBoxLayout()
        header.setContentsMargins(0, 5, 0, 10)
        self.logo = QLabel("L-Drive Pro")
        self.logo.setObjectName("AppLogo")
        header.addWidget(self.logo)
        header.addStretch()
        
        self.theme_btn = QPushButton("Theme")
        self.theme_btn.setFixedHeight(30)
        self.theme_btn.setObjectName("SecondaryBtn")
        self.theme_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.theme_btn.clicked.connect(self.theme_toggle_requested.emit)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setFixedHeight(30)
        self.settings_btn.setObjectName("SecondaryBtn")
        self.settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.settings_btn.clicked.connect(self.settings_requested.emit)

        self.add_btn = QPushButton("+ Add")
        self.add_btn.setFixedSize(70, 30)
        self.add_btn.setObjectName("PrimaryBtn")
        self.add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_btn.clicked.connect(self.add_requested.emit)
        
        header.addWidget(self.theme_btn)
        header.addWidget(self.settings_btn)
        header.addWidget(self.add_btn)
        main_layout.addLayout(header)

        # Drive Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        
        self.container = QWidget()
        self.card_layout = QVBoxLayout(self.container)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.card_layout.setSpacing(10)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll)

        # Log Activity Bar
        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setFixedHeight(120)
        self.log_viewer.setObjectName("ActivityLog")
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
        if "[Error]" in message or "치명적" in message:
            self.log_viewer.appendHtml(f'<span style="color: #C42B1C;">[{timestamp}] {message}</span>')
        else:
            self.log_viewer.appendPlainText(f"[{timestamp}] {message}")
        
        self.log_viewer.verticalScrollBar().setValue(self.log_viewer.verticalScrollBar().maximum())

class GlobalSettingsDialog(QDialog):
    def __init__(self, config_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("System Settings")
        self.setFixedWidth(360)
        self.config_dict = config_dict
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(25, 25, 25, 25)
        
        form = QFormLayout()
        self.rclone_edit = QLineEdit(self.config_dict.get("rclone_path", "rclone.exe"))
        self.conf_edit = QLineEdit(self.config_dict.get("rclone_conf_path", ""))
        self.auto_start = QCheckBox("Start with Windows")
        self.auto_start.setChecked(self.config_dict.get("auto_start", False))
        self.minimized = QCheckBox("Start Minimized in Tray")
        self.minimized.setChecked(self.config_dict.get("start_minimized", False))
        
        form.addRow("Binary Path:", self.rclone_edit)
        form.addRow("Config Path:", self.conf_edit)
        layout.addLayout(form)
        layout.addWidget(self.auto_start)
        layout.addWidget(self.minimized)
        
        btns = QHBoxLayout()
        save = QPushButton("Save Config")
        save.setObjectName("PrimaryBtn")
        save.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
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
        self._setup_menu()

    def _setup_menu(self):
        menu = QMenu()
        show = QAction("Open L-Drive", self); show.triggered.connect(self.show_requested.emit)
        ex = QAction("Quit Application", self); ex.triggered.connect(self.exit_requested.emit)
        menu.addAction(show); menu.addSeparator(); menu.addAction(ex)
        self.setContextMenu(menu)
