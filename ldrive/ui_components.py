import os
import string
import sys

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)


class DriveSettingsDialog(QDialog):
    def __init__(self, remotes, parent=None, profile=None):
        super().__init__(parent)
        self.profile = profile or {}
        self.remotes = remotes
        self.setObjectName("SheetDialog")
        self.setWindowTitle("Drive")
        self.setFixedWidth(380)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)

        self.remote_combo = QComboBox()
        self.remote_combo.addItems(self.remotes)
        if "remote" in self.profile:
            self.remote_combo.setCurrentText(self.profile["remote"])

        self.letter_combo = QComboBox()
        for char in reversed(string.ascii_uppercase):
            if char not in ["C", "D"]:
                self.letter_combo.addItem(f"{char}:")
        if "letter" in self.profile:
            self.letter_combo.setCurrentText(f"{self.profile['letter']}:")

        self.vol_edit = QLineEdit(self.profile.get("volname", ""))
        self.root_edit = QLineEdit(self.profile.get("root_folder", "/"))
        self.vfs_combo = QComboBox()
        self.vfs_combo.addItems(["full", "writes", "off", "minimal"])
        if "vfs_mode" in self.profile:
            self.vfs_combo.setCurrentText(self.profile["vfs_mode"])

        form.addRow("Remote", self.remote_combo)
        form.addRow("Drive", self.letter_combo)
        form.addRow("Name", self.vol_edit)
        form.addRow("Path", self.root_edit)
        form.addRow("VFS", self.vfs_combo)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch()

        cancel = QPushButton("Cancel")
        cancel.setObjectName("GhostBtn")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)

        save = QPushButton("Save")
        save.setObjectName("AccentBtn")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self.accept)

        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def get_data(self):
        return {
            "remote": self.remote_combo.currentText(),
            "letter": self.letter_combo.currentText().replace(":", ""),
            "volname": self.vol_edit.text().strip(),
            "root_folder": self.root_edit.text().strip() or "/",
            "vfs_mode": self.vfs_combo.currentText(),
            "custom_args": "",
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
        self.setMinimumHeight(68)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self.badge = QLabel(self.profile["letter"])
        self.badge.setObjectName("LetterBadge")
        self.badge.setFixedSize(32, 32)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.badge)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        display_name = self.profile.get("volname") or self.profile["remote"]
        self.name_label = QLabel(display_name)
        self.name_label.setObjectName("CardTitle")
        self.name_label.setWordWrap(True)

        self.path_label = QLabel(f"{self.profile['letter']}:  {self.profile.get('root_folder', '/')}")
        self.path_label.setObjectName("CardFootnote")

        info_layout.addWidget(self.name_label)
        info_layout.addWidget(self.path_label)
        layout.addLayout(info_layout, 1)

        self.status_dot = QLabel("")
        self.status_dot.setObjectName("StatusDot")
        self.status_dot.setFixedSize(10, 10)
        layout.addWidget(self.status_dot, 0, Qt.AlignmentFlag.AlignVCenter)

        self.toggle_btn = self._make_icon_button(QStyle.StandardPixmap.SP_MediaPlay, "Connect")
        self.toggle_btn.clicked.connect(self._on_toggle)
        layout.addWidget(self.toggle_btn)

        self.edit_btn = self._make_icon_button(QStyle.StandardPixmap.SP_FileDialogDetailedView, "Edit")
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.profile["id"]))
        layout.addWidget(self.edit_btn)

        self.delete_btn = self._make_icon_button(QStyle.StandardPixmap.SP_TrashIcon, "Delete", danger=True)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.profile["id"]))
        layout.addWidget(self.delete_btn)

        self.set_status("Disconnected")

    def _make_icon_button(self, icon_type, tooltip, danger=False):
        button = QPushButton("")
        button.setObjectName("GhostDangerBtn" if danger else "GhostBtn")
        button.setIcon(self.style().standardIcon(icon_type))
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedSize(28, 28)
        return button

    def _on_toggle(self):
        self.toggle_requested.emit(self.profile["id"], not self.is_running)

    def set_status(self, status):
        if status == "Connected":
            self.toggle_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
            self.toggle_btn.setToolTip("Disconnect")
            self.toggle_btn.setObjectName("DangerBtn")
            self.status_dot.setProperty("state", "connected")
            self.is_running = True
        elif status == "Admin Block":
            self.toggle_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.toggle_btn.setToolTip("Connect")
            self.toggle_btn.setObjectName("GhostBtn")
            self.status_dot.setProperty("state", "blocked")
            self.is_running = False
        else:
            self.toggle_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.toggle_btn.setToolTip("Connect")
            self.toggle_btn.setObjectName("AccentBtn" if status == "Disconnected" else "GhostBtn")
            self.status_dot.setProperty("state", "idle" if status == "Disconnected" else "busy")
            self.is_running = False

        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)


class GlobalSettingsDialog(QDialog):
    def __init__(self, config_data, parent=None):
        super().__init__(parent)
        self.config_data = config_data
        self.setObjectName("SheetDialog")
        self.setWindowTitle("Settings")
        self.setFixedWidth(420)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)

        self.rclone_path_edit = QLineEdit(self.config_data.get("rclone_path", "rclone.exe"))
        self.rclone_conf_edit = QLineEdit(self.config_data.get("rclone_conf_path", ""))

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["light", "dark"])
        self.theme_combo.setCurrentText(self.config_data.get("theme", "light"))

        form.addRow("rclone", self.rclone_path_edit)
        form.addRow("config", self.rclone_conf_edit)
        form.addRow("theme", self.theme_combo)
        layout.addLayout(form)

        self.auto_start_check = QCheckBox("Auto start")
        self.auto_start_check.setChecked(self.config_data.get("auto_start", False))
        self.start_minimized_check = QCheckBox("Start minimized")
        self.start_minimized_check.setChecked(self.config_data.get("start_minimized", False))
        layout.addWidget(self.auto_start_check)
        layout.addWidget(self.start_minimized_check)

        buttons = QHBoxLayout()
        buttons.addStretch()

        cancel = QPushButton("Cancel")
        cancel.setObjectName("GhostBtn")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)

        save = QPushButton("Save")
        save.setObjectName("AccentBtn")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self.accept)

        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

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
        self.setMinimumSize(460, 330)
        self.resize(500, 360)
        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        central.setObjectName("AppShell")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        top_bar = QFrame()
        top_bar.setObjectName("HeroPanel")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(10, 8, 10, 8)
        top_layout.setSpacing(6)

        title = QLabel("L-Drive")
        title.setObjectName("AppTitleHeader")
        top_layout.addWidget(title)
        top_layout.addStretch()

        theme_btn = self._make_top_icon_button(QStyle.StandardPixmap.SP_BrowserReload, "Theme")
        theme_btn.clicked.connect(self.theme_toggle_requested.emit)
        settings_btn = self._make_top_icon_button(QStyle.StandardPixmap.SP_FileDialogContentsView, "Settings")
        settings_btn.clicked.connect(self.settings_requested.emit)
        add_btn = self._make_top_icon_button(QStyle.StandardPixmap.SP_FileDialogNewFolder, "Add")
        add_btn.setObjectName("AccentBtn")
        add_btn.clicked.connect(self.add_requested.emit)

        top_layout.addWidget(theme_btn)
        top_layout.addWidget(settings_btn)
        top_layout.addWidget(add_btn)
        main_layout.addWidget(top_bar)

        self.warning_banner = QLabel("")
        self.warning_banner.setObjectName("WarningBanner")
        self.warning_banner.setWordWrap(True)
        self.warning_banner.hide()
        main_layout.addWidget(self.warning_banner)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("CardScroll")
        self.scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.container.setObjectName("DriveListHost")
        self.card_layout = QVBoxLayout(self.container)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.card_layout.setSpacing(6)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll)

        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setObjectName("ActivityMonitor")
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setFixedHeight(58)
        main_layout.addWidget(self.log_viewer)

    def _make_top_icon_button(self, icon_type, tooltip):
        button = QPushButton("")
        button.setObjectName("GhostBtn")
        button.setIcon(self.style().standardIcon(icon_type))
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedSize(28, 28)
        return button

    def clear_cards(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def add_card(self, card_widget):
        self.card_layout.addWidget(card_widget)

    def set_warning_banner(self, message: str):
        self.warning_banner.setText(message)
        self.warning_banner.setVisible(bool(message))

    def show_empty_state(self):
        empty = QFrame()
        empty.setObjectName("EmptyState")

        layout = QVBoxLayout(empty)
        layout.setContentsMargins(20, 22, 20, 22)
        layout.setSpacing(8)

        title = QLabel("No drives")
        title.setObjectName("EmptyTitle")

        add_btn = QPushButton("")
        add_btn.setObjectName("AccentBtn")
        add_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFixedSize(34, 30)
        add_btn.clicked.connect(self.add_requested.emit)

        layout.addWidget(title, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(add_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        self.card_layout.addWidget(empty)

    def update_overview(self, total_count, active_count, theme_name):
        return

    def _apply_styles(self, theme_name="light"):
        qss_path = self.resource_path(os.path.join("assets", "styles", f"{theme_name}_theme.qss"))
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as file:
                self.setStyleSheet(file.read())

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
        menu = QMenu()
        show = QAction("Open", self)
        show.triggered.connect(self.show_requested.emit)
        close = QAction("Exit", self)
        close.triggered.connect(self.exit_requested.emit)
        menu.addAction(show)
        menu.addSeparator()
        menu.addAction(close)
        self.setContextMenu(menu)
