import os
import sys
import string
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QComboBox, QPushButton, QCheckBox, 
    QScrollArea, QDialog, QLineEdit, QFrame, 
    QPlainTextEdit, QFormLayout, QSystemTrayIcon, QMenu,
    QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction

class DriveSettingsDialog(QDialog):
    def __init__(self, remotes, parent=None, profile=None):
        super().__init__(parent)
        self.profile = profile or {}
        self.remotes = remotes
        self.setObjectName("SheetDialog")
        self.setWindowTitle("Drive Configuration")
        self.setFixedWidth(440)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Drive Profile")
        title.setObjectName("DialogTitle")
        subtitle = QLabel("Configure the remote, drive letter, mount label, and VFS mode.")
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(14)

        self.remote_combo = QComboBox()
        self.remote_combo.addItems(self.remotes)
        if "remote" in self.profile: self.remote_combo.setCurrentText(self.profile["remote"])
        
        self.letter_combo = QComboBox()
        for char in reversed(string.ascii_uppercase):
            if char not in ['C', 'D']: self.letter_combo.addItem(f"{char}:")
        if "letter" in self.profile: self.letter_combo.setCurrentText(f"{self.profile['letter']}:")
        
        self.vol_edit = QLineEdit(self.profile.get("volname", ""))
        self.root_edit = QLineEdit(self.profile.get("root_folder", "/"))
        self.vfs_combo = QComboBox()
        self.vfs_combo.addItems(["full", "writes", "off", "minimal"])
        if "vfs_mode" in self.profile:
            self.vfs_combo.setCurrentText(self.profile["vfs_mode"])
        
        form.addRow("Remote:", self.remote_combo)
        form.addRow("Letter:", self.letter_combo)
        form.addRow("Label:", self.vol_edit)
        form.addRow("Folder:", self.root_edit)
        form.addRow("VFS:", self.vfs_combo)
        layout.addLayout(form)

        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("GhostBtn")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save Changes")
        save.setObjectName("AccentBtn")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self.accept)
        btns.addStretch()
        btns.addWidget(cancel)
        btns.addWidget(save)
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
        self._init_ui()

    def _init_ui(self):
        self.setMinimumHeight(132)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(18)

        self.badge = QLabel(self.profile['letter'])
        self.badge.setObjectName("LetterBadge")
        self.badge.setFixedSize(54, 54)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.badge)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(6)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        name_val = self.profile.get('volname') or self.profile['remote']
        self.name_label = QLabel(name_val)
        self.name_label.setObjectName("CardTitle")
        self.name_label.setWordWrap(True)

        self.remote_label = QLabel(self.profile['remote'])
        self.remote_label.setObjectName("CardMeta")

        self.status_label = QLabel("Disconnected")
        self.status_label.setObjectName("StatusPill")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.path_label = QLabel(f"{self.profile['letter']}:  |  {self.profile.get('root_folder', '/')}")
        self.path_label.setObjectName("CardFootnote")

        meta_row = QHBoxLayout()
        meta_row.setSpacing(10)
        meta_row.addWidget(self.remote_label)
        meta_row.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignLeft)
        meta_row.addStretch()

        info_layout.addWidget(self.name_label)
        info_layout.addLayout(meta_row)
        info_layout.addWidget(self.path_label)
        layout.addLayout(info_layout)

        layout.addStretch()

        action_col = QVBoxLayout()
        action_col.setSpacing(10)
        action_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.toggle_btn = QPushButton("Connect")
        self.toggle_btn.setObjectName("AccentBtn")
        self.toggle_btn.setFixedSize(120, 38)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._on_toggle)
        action_col.addWidget(self.toggle_btn)

        sub_row = QHBoxLayout()
        sub_row.setSpacing(8)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setObjectName("GhostBtn")
        self.edit_btn.setFixedSize(68, 34)
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.profile["id"]))

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("GhostDangerBtn")
        self.delete_btn.setFixedSize(74, 34)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.profile["id"]))

        sub_row.addWidget(self.edit_btn)
        sub_row.addWidget(self.delete_btn)
        action_col.addLayout(sub_row)

        layout.addLayout(action_col)

    def _on_toggle(self):
        self.toggle_requested.emit(self.profile["id"], not self.is_running)

    def set_status(self, status):
        self.status_label.setText(status)
        if status == "Connected":
            self.toggle_btn.setText("Disconnect")
            self.toggle_btn.setObjectName("DangerBtn")
            self.status_label.setProperty("state", "connected")
            self.is_running = True
        else:
            self.toggle_btn.setText("Connect")
            self.toggle_btn.setObjectName("AccentBtn")
            self.status_label.setProperty("state", "idle")
            self.is_running = False

        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

class GlobalSettingsDialog(QDialog):
    def __init__(self, config_data, parent=None):
        super().__init__(parent)
        self.config_data = config_data
        self.setObjectName("SheetDialog")
        self.setWindowTitle("Global Settings")
        self.setFixedWidth(500)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Application Settings")
        title.setObjectName("DialogTitle")
        subtitle = QLabel("Update runtime paths, startup preferences, and the app appearance.")
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(14)

        self.rclone_path_edit = QLineEdit(self.config_data.get("rclone_path", "rclone.exe"))
        self.rclone_conf_edit = QLineEdit(self.config_data.get("rclone_conf_path", ""))

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["light", "dark"])
        self.theme_combo.setCurrentText(self.config_data.get("theme", "light"))

        form.addRow("rclone path:", self.rclone_path_edit)
        form.addRow("config path:", self.rclone_conf_edit)
        form.addRow("theme:", self.theme_combo)
        layout.addLayout(form)

        self.auto_start_check = QCheckBox("Launch automatically when Windows starts")
        self.auto_start_check.setChecked(self.config_data.get("auto_start", False))
        self.start_minimized_check = QCheckBox("Open in background tray mode")
        self.start_minimized_check.setChecked(self.config_data.get("start_minimized", False))
        layout.addWidget(self.auto_start_check)
        layout.addWidget(self.start_minimized_check)

        btns = QHBoxLayout()
        btns.addStretch()

        cancel = QPushButton("Cancel")
        cancel.setObjectName("GhostBtn")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)

        save = QPushButton("Save Preferences")
        save.setObjectName("AccentBtn")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self.accept)

        btns.addWidget(cancel)
        btns.addWidget(save)
        layout.addLayout(btns)

    def get_data(self):
        return {
            "rclone_path": self.rclone_path_edit.text().strip() or "rclone.exe",
            "rclone_conf_path": self.rclone_conf_edit.text().strip(),
            "theme": self.theme_combo.currentText(),
            "auto_start": self.auto_start_check.isChecked(),
            "start_minimized": self.start_minimized_check.isChecked(),
        }

class LDriveMainWindow(QMainWindow):
    add_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    theme_toggle_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("L-Drive")
        self.setMinimumSize(880, 680)
        self.resize(980, 760)
        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        central.setObjectName("AppShell")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(22, 22, 22, 22)
        main_layout.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("HeroPanel")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        hero_layout.setSpacing(18)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(4)
        eyebrow = QLabel("Rclone Mount Manager")
        eyebrow.setObjectName("EyebrowLabel")
        title = QLabel("L-Drive Console")
        title.setObjectName("AppTitleHeader")
        subtitle = QLabel("Professional Windows mount orchestration for remote storage volumes.")
        subtitle.setObjectName("AppSubtitle")
        subtitle.setWordWrap(True)
        title_wrap.addWidget(eyebrow)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        top_bar.addLayout(title_wrap, 1)

        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        theme_btn = QPushButton("Theme")
        theme_btn.setObjectName("GhostBtn")
        theme_btn.setFixedHeight(34)
        theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        theme_btn.clicked.connect(self.theme_toggle_requested.emit)

        settings_btn = QPushButton("Settings")
        settings_btn.setObjectName("GhostBtn")
        settings_btn.setFixedHeight(34)
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(self.settings_requested.emit)

        add_btn = QPushButton("Add Drive")
        add_btn.setObjectName("AccentBtn")
        add_btn.setFixedHeight(34)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self.add_requested.emit)

        action_bar.addWidget(theme_btn)
        action_bar.addWidget(settings_btn)
        action_bar.addWidget(add_btn)
        top_bar.addLayout(action_bar)
        hero_layout.addLayout(top_bar)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self.total_stat = self._create_stat_card("Configured Drives", "0")
        self.active_stat = self._create_stat_card("Connected Sessions", "0")
        self.theme_stat = self._create_stat_card("Current Theme", "Light")
        stats_row.addWidget(self.total_stat)
        stats_row.addWidget(self.active_stat)
        stats_row.addWidget(self.theme_stat)
        hero_layout.addLayout(stats_row)
        main_layout.addWidget(hero)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("CardScroll")
        self.scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.container.setObjectName("DriveListHost")
        self.card_layout = QVBoxLayout(self.container)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.card_layout.setSpacing(12)
        self.card_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll)

        log_panel = QFrame()
        log_panel.setObjectName("LogPanel")
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(18, 16, 18, 16)
        log_layout.setSpacing(12)

        log_header = QHBoxLayout()
        log_title_wrap = QVBoxLayout()
        log_title_wrap.setSpacing(2)
        log_title = QLabel("Activity")
        log_title.setObjectName("SectionTitle")
        log_subtitle = QLabel("Recent mount, recovery, and runtime events.")
        log_subtitle.setObjectName("SectionSubtitle")
        log_title_wrap.addWidget(log_title)
        log_title_wrap.addWidget(log_subtitle)
        log_header.addLayout(log_title_wrap)
        log_header.addStretch()

        clear_log_btn = QPushButton("Clear")
        clear_log_btn.setObjectName("GhostBtn")
        clear_log_btn.setFixedHeight(30)
        clear_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_log_btn.clicked.connect(lambda: self.log_viewer.clear())
        log_header.addWidget(clear_log_btn)

        log_layout.addLayout(log_header)

        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setObjectName("ActivityMonitor")
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setFixedHeight(148)
        log_layout.addWidget(self.log_viewer)
        main_layout.addWidget(log_panel)

    def _create_stat_card(self, label_text, value_text):
        card = QFrame()
        card.setObjectName("StatCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        label = QLabel(label_text)
        label.setObjectName("StatLabel")
        value = QLabel(value_text)
        value.setObjectName("StatValue")

        layout.addWidget(label)
        layout.addWidget(value)
        card.value_label = value
        return card

    def clear_cards(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def add_card(self, card_widget):
        self.card_layout.addWidget(card_widget)

    def show_empty_state(self):
        empty = QFrame()
        empty.setObjectName("EmptyState")

        layout = QVBoxLayout(empty)
        layout.setContentsMargins(32, 40, 32, 40)
        layout.setSpacing(8)

        title = QLabel("No drive profiles yet")
        title.setObjectName("EmptyTitle")
        subtitle = QLabel("Add a drive profile to start mounting an rclone remote with a managed Windows volume letter.")
        subtitle.setObjectName("EmptySubtitle")
        subtitle.setWordWrap(True)

        add_btn = QPushButton("Create First Drive")
        add_btn.setObjectName("AccentBtn")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFixedHeight(38)
        add_btn.clicked.connect(self.add_requested.emit)

        layout.addWidget(title, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(subtitle, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(6)
        layout.addWidget(add_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        self.card_layout.addWidget(empty)

    def update_overview(self, total_count, active_count, theme_name):
        self.total_stat.value_label.setText(str(total_count))
        self.active_stat.value_label.setText(str(active_count))
        self.theme_stat.value_label.setText(theme_name.capitalize())

    def _apply_styles(self, theme_name="light"):
        qss_path = self.resource_path(os.path.join("assets", "styles", f"{theme_name}_theme.qss"))
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        self.update_overview(self.card_layout.count(), 0, theme_name)

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

class LDriveTrayIcon(QSystemTrayIcon):
    show_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, icon, parent=None):
        super().__init__(icon, parent)
        menu = QMenu()
        show = QAction("Open", self); show.triggered.connect(self.show_requested.emit)
        ex = QAction("Exit", self); ex.triggered.connect(self.exit_requested.emit)
        menu.addAction(show); menu.addSeparator(); menu.addAction(ex)
        self.setContextMenu(menu)
