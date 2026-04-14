import os
import sys
import string
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QComboBox, QPushButton, QCheckBox, 
    QScrollArea, QDialog, QLineEdit, QFrame, 
    QPlainTextEdit, QFormLayout, QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QEvent
from PyQt6.QtGui import QIcon, QAction, QFont, QCursor

# --- Designer Utilities ---

class EmptyStateWidget(QWidget):
    add_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(15)

        icon = QLabel("☁️") # In a real app, use a nice SVG
        icon.setStyleSheet("font-size: 48pt;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title = QLabel("Add your first drive")
        title.setObjectName("EmptyStateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        desc = QLabel("Connect your cloud storage as a local network drive.\nSupports GDrive, OneDrive, Dropbox and more.")
        desc.setObjectName("EmptyStateDesc")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        add_btn = QPushButton("+ Add Drive")
        add_btn.setObjectName("PrimaryAddBtn")
        add_btn.setFixedSize(140, 40)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self.add_requested.emit)
        
        layout.addStretch()
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addSpacing(10)
        layout.addWidget(add_btn, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

class DriveCardWidget(QFrame):
    toggle_requested = pyqtSignal(str, bool)
    edit_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, profile):
        super().__init__()
        self.profile = profile
        self.is_running = False
        self.setObjectName("DriveCard")
        self.setFixedHeight(100) # Slightly taller for better spacing
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(18)

        # 1. Drive Letter Badge (Fluent Style)
        self.badge = QLabel(self.profile['letter'])
        self.badge.setObjectName("DriveLetterBadge")
        self.badge.setFixedSize(48, 48)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.badge)

        # 2. Main Identity area
        id_layout = QVBoxLayout()
        id_layout.setSpacing(2)
        id_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        name_val = self.profile.get('volname') or self.profile['remote']
        self.name_label = QLabel(name_val)
        self.name_label.setObjectName("DriveName")
        
        status_inner = QHBoxLayout()
        status_inner.setSpacing(6)
        self.status_dot = QFrame()
        self.status_dot.setFixedSize(8, 8)
        self.status_dot.setObjectName("StatusDot_Disconnected")
        
        self.status_text = QLabel("Disconnected")
        self.status_text.setObjectName("StatusLabel")
        status_inner.addWidget(self.status_dot)
        status_inner.addWidget(self.status_text)
        status_inner.addStretch()
        
        id_layout.addWidget(self.name_label)
        id_layout.addLayout(status_inner)
        layout.addLayout(id_layout)
        
        layout.addStretch()

        # 3. Action Buttons (Modern Pill Style)
        self.toggle_btn = QPushButton("Connect")
        self.toggle_btn.setObjectName("CardAccentBtn")
        self.toggle_btn.setFixedSize(100, 36)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._on_toggle)
        
        self.edit_btn = QPushButton("🔧") # Gear icon simulation
        self.edit_btn.setText("Settings")
        self.edit_btn.setObjectName("CardActionBtn")
        self.edit_btn.setFixedSize(85, 36)
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.profile["id"]))
        
        self.delete_btn = QPushButton("🗑")
        self.delete_btn.setObjectName("CardActionBtn")
        self.delete_btn.setFixedSize(40, 36)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.profile["id"]))

        layout.addWidget(self.toggle_btn)
        layout.addWidget(self.edit_btn)
        layout.addWidget(self.delete_btn)

    def _on_toggle(self):
        self.toggle_requested.emit(self.profile["id"], not self.is_running)

    def set_status(self, status):
        self.status_text.setText(status)
        if status == "Connected":
            self.status_dot.setObjectName("StatusDot_Connected")
            self.toggle_btn.setText("Disconnect")
            self.toggle_btn.setProperty("isUnmount", "true")
            self.is_running = True
        else:
            self.status_dot.setObjectName("StatusDot_Disconnected")
            self.toggle_btn.setText("Connect")
            self.toggle_btn.setProperty("isUnmount", "false")
            self.is_running = False
        
        # Refresh styles
        self.status_dot.style().unpolish(self.status_dot); self.status_dot.style().polish(self.status_dot)
        self.toggle_btn.style().unpolish(self.toggle_btn); self.toggle_btn.style().polish(self.toggle_btn)

# --- Main Window Reconstruction ---

class LDriveMainWindow(QMainWindow):
    add_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    theme_toggle_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("L-Drive Pro")
        self.setFixedSize(450, 650) # Taller for modern spacing
        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top App Bar (Sleek Header)
        header_widget = QWidget()
        header_widget.setFixedHeight(70)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(25, 0, 25, 0)
        
        self.app_title = QLabel("L-Drive Pro")
        self.app_title.setObjectName("AppLogo")
        header_layout.addWidget(self.app_title)
        header_layout.addStretch()
        
        self.theme_btn = QPushButton("☀")
        self.theme_btn.setObjectName("HeaderIconBtn")
        self.theme_btn.setFixedSize(36, 36)
        self.theme_btn.clicked.connect(self.theme_toggle_requested.emit)
        
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setObjectName("HeaderIconBtn")
        self.settings_btn.setFixedSize(36, 36)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        
        self.add_btn = QPushButton("+ Add")
        self.add_btn.setObjectName("PrimaryAddBtn")
        self.add_btn.setFixedHeight(34)
        self.add_btn.clicked.connect(self.add_requested.emit)
        
        header_layout.addWidget(self.theme_btn)
        header_layout.addWidget(self.settings_btn)
        header_layout.addSpacing(5)
        header_layout.addWidget(self.add_btn)
        main_layout.addWidget(header_widget)

        # 2. Card Content Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.card_layout = QVBoxLayout(self.container)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.card_layout.setSpacing(12)
        self.card_layout.setContentsMargins(25, 5, 25, 15)
        
        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll)

        # 3. Bottom Activity Section (Collapsible Simulation)
        self.activity_container = QFrame()
        self.activity_container.setObjectName("ActivityContainer")
        self.activity_container.setFixedHeight(120)
        act_layout = QVBoxLayout(self.activity_container)
        act_layout.setContentsMargins(20, 15, 20, 10)
        
        act_header = QHBoxLayout()
        act_title = QLabel("Activity / System Status")
        act_title.setStyleSheet("font-weight: 700; color: #5D5D5D; font-size: 9pt;")
        act_header.addWidget(act_title)
        act_header.addStretch()
        act_layout.addLayout(act_header)

        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setObjectName("ActivityLog")
        act_layout.addWidget(self.log_viewer)
        
        main_layout.addWidget(self.activity_container)

    def clear_cards(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def show_empty_state(self):
        self.clear_cards()
        empty = EmptyStateWidget()
        empty.add_requested.connect(self.add_requested.emit)
        self.card_layout.addWidget(empty)

    def add_card(self, card_widget):
        # Remove empty state if any
        if self.card_layout.count() == 1 and isinstance(self.card_layout.itemAt(0).widget(), EmptyStateWidget):
            self.card_layout.itemAt(0).widget().deleteLater()
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
        self.setWindowTitle("Connection Properties")
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
        self.vol_edit.setPlaceholderText("Virtual Volume Name")

        self.root_edit = QLineEdit(self.profile.get("root_folder", "/"))
        self.vfs_combo = QComboBox()
        self.vfs_combo.addItems(["full", "writes", "off", "minimal"])
        
        form.addRow("Target Remote:", self.remote_combo)
        form.addRow("Assign Letter:", self.letter_combo)
        form.addRow("Mount Label:", self.vol_edit)
        form.addRow("Remote Path:", self.root_edit)
        form.addRow("VFS Mode:", self.vfs_combo)
        layout.addLayout(form)
        
        btns = QHBoxLayout()
        btns.addStretch()
        sv = QPushButton("Save Drive")
        sv.setObjectName("PrimaryAddBtn") # Use same style
        cl = QPushButton("Cancel")
        cl.setObjectName("CardActionBtn")
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
        self.auto_start = QCheckBox("Start L-Drive with Windows")
        self.auto_start.setChecked(self.config_dict.get("auto_start", False))
        self.minimized = QCheckBox("Hide to System Tray on launch")
        self.minimized.setChecked(self.config_dict.get("start_minimized", False))
        
        form.addRow("Rclone Path:", self.rclone_edit)
        form.addRow("Conf Path:", self.conf_edit)
        layout.addLayout(form)
        layout.addWidget(self.auto_start)
        layout.addWidget(self.minimized)
        
        btns = QHBoxLayout()
        btns.addStretch()
        sv = QPushButton("Apply All")
        sv.setObjectName("PrimaryAddBtn")
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
        show = QAction("Restore Dashboard", self); show.triggered.connect(self.show_requested.emit)
        ex = QAction("Shut Down L-Drive", self); ex.triggered.connect(self.exit_requested.emit)
        menu.addAction(show); menu.addSeparator(); menu.addAction(ex)
        self.setContextMenu(menu)
