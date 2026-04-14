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
from PyQt6.QtGui import QIcon, QAction, QFont

class DriveSettingsDialog(QDialog):
    def __init__(self, remotes, parent=None, profile=None):
        super().__init__(parent)
        self.profile = profile or {}
        self.remotes = remotes
        self.setWindowTitle("Drive Settings" if profile else "Add New Drive")
        self.setFixedWidth(360)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
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
        self.vol_edit.setPlaceholderText("Explorer Display Name")

        self.root_edit = QLineEdit(self.profile.get("root_folder", "/"))
        self.vfs_combo = QComboBox()
        self.vfs_combo.addItems(["full", "writes", "off", "minimal"])
        
        form.addRow("Remote:", self.remote_combo)
        form.addRow("Letter:", self.letter_combo)
        form.addRow("Name:", self.vol_edit)
        form.addRow("Root:", self.root_edit)
        form.addRow("VFS:", self.vfs_combo)
        
        layout.addLayout(form)
        
        btns = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("MountButton")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(save_btn)
        btns.addWidget(cancel_btn)
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
        self.setMinimumHeight(80)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)

        # 1. Circle Icon Box
        self.icon_circle = QLabel(self.profile['letter'])
        self.icon_circle.setObjectName("LetterCircle")
        self.icon_circle.setFixedSize(44, 44)
        self.icon_circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_circle)

        # 2. Info Block
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        display_name = self.profile.get('volname') or self.profile['remote']
        if not display_name: display_name = "Unnamed Drive"
            
        self.title_label = QLabel(display_name)
        self.title_label.setObjectName("DriveTitle")
        
        self.status_label = QLabel("Disconnected")
        self.status_label.setObjectName("StatusDisconnected")
        
        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.status_label)
        layout.addLayout(info_layout)
        
        layout.addStretch()

        # 3. Mount/Unmount Button
        self.toggle_btn = QPushButton("▶ Mount")
        self.toggle_btn.setObjectName("MountButton") # Will dynamic toggle color in CSS
        self.toggle_btn.setFixedSize(100, 36)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._on_toggle)
        layout.addWidget(self.toggle_btn)

        # 4. Settings/Delete Small Buttons (Text-based Ghost)
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setObjectName("GhostButton")
        self.edit_btn.setFixedSize(50, 36)
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.profile["id"]))
        
        self.delete_btn = QPushButton("Del")
        self.delete_btn.setObjectName("GhostButton")
        self.delete_btn.setFixedSize(45, 36)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.profile["id"]))

        layout.addWidget(self.edit_btn)
        layout.addWidget(self.delete_btn)

    def _on_toggle(self):
        self.toggle_requested.emit(self.profile["id"], not self.is_running)

    def set_status(self, status):
        self.status_label.setText(status)
        if status == "Connected":
            self.toggle_btn.setText("⏹ Unmount")
            self.toggle_btn.setProperty("isUnmount", "true")
            self.status_label.setObjectName("StatusConnected")
            self.is_running = True
        elif "Error" in status:
            self.status_label.setObjectName("StatusDisconnected") # Actually could be red
            self.toggle_btn.setText("▶ Mount")
            self.toggle_btn.setProperty("isUnmount", "false")
            self.is_running = False
        else:
            self.toggle_btn.setText("▶ Mount")
            self.toggle_btn.setProperty("isUnmount", "false")
            self.status_label.setObjectName("StatusDisconnected")
            self.is_running = False
        
        # Style refresh
        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

class LDriveMainWindow(QMainWindow):
    add_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    theme_toggle_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedSize(420, 580)
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
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # Header Row
        header = QHBoxLayout()
        header.setContentsMargins(5, 5, 5, 10)
        self.logo = QLabel("L-Drive Pro")
        self.logo.setObjectName("AppLogo")
        header.addWidget(self.logo)
        header.addStretch()
        
        self.theme_btn = QPushButton("Theme")
        self.theme_btn.setFixedHeight(30)
        self.theme_btn.setObjectName("GhostButton")
        self.theme_btn.clicked.connect(self.theme_toggle_requested.emit)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setFixedHeight(30)
        self.settings_btn.setObjectName("GhostButton")
        self.settings_btn.clicked.connect(self.settings_requested.emit)

        self.add_btn = QPushButton("+ Add")
        self.add_btn.setFixedSize(70, 30)
        self.add_btn.setObjectName("MountButton")
        self.add_btn.clicked.connect(self.add_requested.emit)
        
        header.addWidget(self.theme_btn)
        header.addWidget(self.settings_btn)
        header.addWidget(self.add_btn)
        main_layout.addLayout(header)

        # Drive Scroll List
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

        # Compact Logs (Mini bar)
        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setFixedHeight(90)
        self.log_viewer.setObjectName("CompactLog")
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
        self.log_viewer.appendPlainText(f"[{timestamp}] {message}")
        self.log_viewer.verticalScrollBar().setValue(self.log_viewer.verticalScrollBar().maximum())

class GlobalSettingsDialog(QDialog):
    def __init__(self, config_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Global Options")
        self.setFixedWidth(340)
        self.config_dict = config_dict
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        form = QFormLayout()
        self.rclone_edit = QLineEdit(self.config_dict.get("rclone_path", "rclone.exe"))
        self.conf_edit = QLineEdit(self.config_dict.get("rclone_conf_path", ""))
        self.auto_start = QCheckBox("Start on Windows Boot")
        self.auto_start.setChecked(self.config_dict.get("auto_start", False))
        self.minimized = QCheckBox("Start Minimized (Tray Only)")
        self.minimized.setChecked(self.config_dict.get("start_minimized", False))
        
        form.addRow("Binary:", self.rclone_edit)
        form.addRow("Config:", self.conf_edit)
        layout.addLayout(form)
        layout.addWidget(self.auto_start)
        layout.addWidget(self.minimized)
        
        btns = QHBoxLayout()
        save = QPushButton("Save Config")
        save.setObjectName("MountButton")
        save.clicked.connect(self.accept)
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
        show = QAction("Open Dashboard", self); show.triggered.connect(self.show_requested.emit)
        ex = QAction("Exit App", self); ex.triggered.connect(self.exit_requested.emit)
        menu.addAction(show); menu.addSeparator(); menu.addAction(ex)
        self.setContextMenu(menu)
