import os
import string
import sys

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal, QThread
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)


def _make_line_icon(kind: str, color: str, size: int = 16) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if kind == "theme":
        painter.drawArc(QRectF(3, 3, 10, 10), 40 * 16, 280 * 16)
        painter.drawLine(QPointF(9.5, 1.8), QPointF(9.5, 4.0))
        painter.drawLine(QPointF(14.2, 9.0), QPointF(12.0, 9.0))
        painter.drawLine(QPointF(11.9, 4.1), QPointF(13.4, 2.6))
    elif kind == "settings":
        painter.drawRoundedRect(QRectF(3, 3, 10, 10), 3, 3)
        painter.drawLine(QPointF(5, 6), QPointF(11, 6))
        painter.drawLine(QPointF(5, 10), QPointF(11, 10))
        painter.drawEllipse(QRectF(7.2, 4.6, 2.2, 2.2))
        painter.drawEllipse(QRectF(5.5, 8.6, 2.2, 2.2))
    elif kind == "add":
        painter.drawEllipse(QRectF(2.5, 2.5, 11, 11))
        painter.drawLine(QPointF(8, 5), QPointF(8, 11))
        painter.drawLine(QPointF(5, 8), QPointF(11, 8))
    elif kind == "play":
        path = QPainterPath()
        path.moveTo(5.2, 4.4)
        path.lineTo(11.6, 8.0)
        path.lineTo(5.2, 11.6)
        path.closeSubpath()
        painter.fillPath(path, QColor(color))
    elif kind == "stop":
        painter.fillRect(QRectF(4.4, 4.4, 7.2, 7.2), QColor(color))
    elif kind == "edit":
        path = QPainterPath()
        path.moveTo(4.0, 11.8)
        path.lineTo(5.5, 9.0)
        path.lineTo(10.7, 3.8)
        path.lineTo(12.2, 5.3)
        path.lineTo(7.0, 10.5)
        path.closeSubpath()
        painter.fillPath(path, QColor(color))
        painter.drawLine(QPointF(4.0, 11.8), QPointF(6.4, 11.1))
    elif kind == "trash":
        painter.drawLine(QPointF(5.2, 4.8), QPointF(10.8, 4.8))
        painter.drawLine(QPointF(6.2, 4.8), QPointF(6.8, 12))
        painter.drawLine(QPointF(9.2, 4.8), QPointF(8.8, 12))
        painter.drawLine(QPointF(4.5, 4.8), QPointF(5.2, 12))
        painter.drawLine(QPointF(11.5, 4.8), QPointF(10.8, 12))
        painter.drawLine(QPointF(4.5, 4.8), QPointF(11.5, 4.8))
        painter.drawLine(QPointF(6.2, 3.2), QPointF(9.8, 3.2))
    elif kind == "folder":
        path = QPainterPath()
        path.moveTo(2.8, 5.5)
        path.lineTo(6.0, 5.5)
        path.lineTo(7.0, 4.0)
        path.lineTo(13.2, 4.0)
        path.lineTo(12.2, 12.2)
        path.lineTo(3.8, 12.2)
        path.closeSubpath()
        painter.drawPath(path)

    painter.end()
    return QIcon(pixmap)


class DriveSettingsDialog(QDialog):
    def __init__(self, remotes, parent=None, profile=None, used_letters=None, system_used_letters=None):
        super().__init__(parent)
        self.profile = profile or {}
        self.remotes = remotes
        self.used_letters = {str(letter).replace(':', '').upper() for letter in (used_letters or [])}
        self.system_used_letters = {str(letter).replace(':', '').upper() for letter in (system_used_letters or [])}
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
        current_letter = str(self.profile.get("letter", "")).replace(":", "").upper()
        for char in reversed(string.ascii_uppercase):
            if char in ["C", "D"]:
                continue
            if char in self.used_letters and char != current_letter:
                continue
            if char in self.system_used_letters and char != current_letter:
                continue
            self.letter_combo.addItem(f"{char}:")
        if "letter" in self.profile:
            self.letter_combo.setCurrentText(f"{self.profile['letter']}:")

        self.vol_edit = QLineEdit(self.profile.get("volname", ""))
        self.root_edit = QLineEdit(self.profile.get("root_folder", "/"))
        self.cache_dir_edit = QLineEdit(self.profile.get("cache_dir", ""))
        self.extra_args_edit = QLineEdit(self.profile.get("custom_args", self.profile.get("extra_flags", "")))
        self.vfs_combo = QComboBox()
        self.vfs_combo.addItems(["full", "writes", "off", "minimal"])
        if "vfs_mode" in self.profile:
            self.vfs_combo.setCurrentText(self.profile["vfs_mode"])
        self.auto_mount_check = QCheckBox("Auto mount this drive on app launch")
        self.auto_mount_check.setChecked(self.profile.get("auto_mount", False))

        form.addRow("Remote", self.remote_combo)
        form.addRow("Drive", self.letter_combo)
        form.addRow("Name", self.vol_edit)
        form.addRow("Path", self.root_edit)
        form.addRow("Cache dir", self.cache_dir_edit)
        form.addRow("Extra args", self.extra_args_edit)
        form.addRow("VFS", self.vfs_combo)
        form.addRow("", self.auto_mount_check)
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
        save.clicked.connect(self._validate_and_accept)

        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def _validate_and_accept(self):
        remote = self.remote_combo.currentText().strip()
        root = self.root_edit.text().strip() or "/"
        cache_dir = self.cache_dir_edit.text().strip()
        extra_args = self.extra_args_edit.text().strip()

        if not remote:
            QMessageBox.warning(self, "Validation Error", "Remote is required.")
            return

        if root and not root.startswith("/"):
            QMessageBox.warning(self, "Validation Error", "Path must start with '/'.")
            return

        if cache_dir and any(ch in cache_dir for ch in ['"', "'", "\n", "\r"]):
            QMessageBox.warning(self, "Validation Error", "Cache dir contains invalid characters.")
            return

        if any(ch in extra_args for ch in ["\n", "\r"]):
            QMessageBox.warning(self, "Validation Error", "Extra args must be a single line.")
            return

        self.accept()

    def get_data(self):
        return {
            "remote": self.remote_combo.currentText().strip(),
            "letter": self.letter_combo.currentText().replace(":", ""),
            "volname": self.vol_edit.text().strip(),
            "root_folder": self.root_edit.text().strip() or "/",
            "vfs_mode": self.vfs_combo.currentText(),
            "auto_mount": self.auto_mount_check.isChecked(),
            "cache_dir": self.cache_dir_edit.text().strip(),
            "custom_args": self.extra_args_edit.text().strip(),
            "extra_flags": self.extra_args_edit.text().strip(),
        }


class DriveCardWidget(QFrame):
    toggle_requested = pyqtSignal(str, bool)
    edit_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, profile):
        super().__init__()
        self.profile = profile
        self.is_running = False
        self.current_theme = "light"
        self.setObjectName("DriveCard")
        self._init_ui()

    def _init_ui(self):
        self.setMinimumHeight(68)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self.status_dot = QLabel("")
        self.status_dot.setObjectName("StatusDot")
        self.status_dot.setFixedSize(10, 10)
        layout.addWidget(self.status_dot, 0, Qt.AlignmentFlag.AlignVCenter)

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

        self.toggle_btn = self._make_icon_button("play", "Connect")
        self.toggle_btn.clicked.connect(self._on_toggle)
        layout.addWidget(self.toggle_btn)

        self.edit_btn = self._make_icon_button("edit", "Edit")
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.profile["id"]))
        layout.addWidget(self.edit_btn)

        self.delete_btn = self._make_icon_button("trash", "Delete", danger=True)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.profile["id"]))
        layout.addWidget(self.delete_btn)

        self.set_status("Disconnected")

    def _make_icon_button(self, kind, tooltip, danger=False):
        button = QPushButton("")
        button.icon_kind = kind
        button.icon_role = "danger" if danger else "ghost"
        button.setObjectName("GhostDangerBtn" if danger else "GhostBtn")
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedSize(28, 28)
        return button

    def refresh_icons(self, theme_name="light"):
        self.current_theme = theme_name
        colors = {
            "light": {"ghost": "#5F7087", "danger": "#B33A33", "accent": "#FFFFFF"},
            "dark": {"ghost": "#DCE8F5", "danger": "#FFD2CC", "accent": "#FFFFFF"},
        }
        palette = colors["dark" if theme_name == "dark" else "light"]

        for button in (self.toggle_btn, self.edit_btn, self.delete_btn):
            role = getattr(button, "icon_role", "ghost")
            icon_kind = getattr(button, "icon_kind", "play")
            color = palette["ghost"]
            if role == "danger":
                color = palette["danger"]
            if button.objectName() in {"AccentBtn", "DangerBtn"}:
                color = palette["accent"]
            button.setIcon(_make_line_icon(icon_kind, color))

    def _on_toggle(self):
        self.toggle_requested.emit(self.profile["id"], not self.is_running)

    def set_status(self, status):
        if status == "Connected":
            self.toggle_btn.icon_kind = "stop"
            self.toggle_btn.setToolTip("Disconnect")
            self.toggle_btn.setObjectName("DangerBtn")
            self.status_dot.setProperty("state", "connected")
            self.is_running = True
        elif status == "Admin Block":
            self.toggle_btn.icon_kind = "play"
            self.toggle_btn.setToolTip("Connect")
            self.toggle_btn.setObjectName("GhostBtn")
            self.status_dot.setProperty("state", "blocked")
            self.is_running = False
        else:
            self.toggle_btn.icon_kind = "play"
            self.toggle_btn.setToolTip("Connect")
            self.toggle_btn.setObjectName("AccentBtn" if status == "Disconnected" else "GhostBtn")
            self.status_dot.setProperty("state", "idle" if status == "Disconnected" else "busy")
            self.is_running = False

        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)
        self.refresh_icons(self.current_theme)


class RcloneUpdateWorker(QThread):
    progress_changed = pyqtSignal(int)
    finished_with_result = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, updater, target_dir, version=None):
        super().__init__()
        self.updater = updater
        self.target_dir = target_dir
        self.version = version

    def run(self):
        try:
            result = self.updater.download_and_install(
                self.target_dir,
                self.version,
                progress_cb=self.progress_changed.emit,
            )
            self.finished_with_result.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class RcloneUpdateDialog(QDialog):
    def __init__(self, installed_version, latest_version, parent=None):
        super().__init__(parent)
        self.setObjectName("SheetDialog")
        self.setWindowTitle("rclone Update")
        self.setFixedWidth(420)
        self.installed_version = installed_version or "unknown"
        self.latest_version = latest_version or "unknown"
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        title = QLabel(f"rclone {self.installed_version} → {self.latest_version}")
        title.setObjectName("CardTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        note = QLabel("Downloading the latest rclone build. Please wait.")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.status_label = QLabel("Starting update...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("GhostBtn")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

    def set_progress(self, value: int):
        self.progress.setValue(max(0, min(100, value)))
        self.status_label.setText(f"Downloading... {self.progress.value()}%")

    def mark_done(self, message: str):
        self.progress.setValue(100)
        self.status_label.setText(message)
        self.close_btn.setEnabled(True)

    def mark_failed(self, message: str):
        self.status_label.setText(message)
        self.close_btn.setEnabled(True)


class GlobalSettingsDialog(QDialog):
    def __init__(self, config_data, parent=None):
        super().__init__(parent)
        self.config_data = config_data
        self.setObjectName("SheetDialog")
        self.setWindowTitle("Settings")
        self.setFixedWidth(420)
        self.update_rclone_requested = False
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

        form.addRow("rclone", self._build_rclone_row())
        form.addRow("config", self._build_picker_row(self.rclone_conf_edit, "file"))
        form.addRow("theme", self.theme_combo)
        layout.addLayout(form)

        self.rclone_version_label = QLabel(self.config_data.get("rclone_version_status", "rclone version: unknown"))
        self.rclone_version_label.setWordWrap(True)
        layout.addWidget(self.rclone_version_label)

        self.auto_start_check = QCheckBox("Auto start")
        self.auto_start_check.setChecked(self.config_data.get("auto_start", False))
        self.mount_on_launch_check = QCheckBox("Mount on launch")
        self.mount_on_launch_check.setChecked(self.config_data.get("mount_on_launch", False))
        self.start_minimized_check = QCheckBox("Start to tray")
        self.start_minimized_check.setChecked(self.config_data.get("start_minimized", False))
        self.minimize_to_tray_check = QCheckBox("Minimize/close to tray")
        self.minimize_to_tray_check.setChecked(self.config_data.get("minimize_to_tray", True))
        layout.addWidget(self.auto_start_check)
        layout.addWidget(self.mount_on_launch_check)
        layout.addWidget(self.start_minimized_check)
        layout.addWidget(self.minimize_to_tray_check)

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
        self.refresh_icons(self.config_data.get("theme", "light"))

    def _build_rclone_row(self):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.rclone_path_edit, 1)

        browse_button = QPushButton("")
        browse_button.setObjectName("GhostBtn")
        browse_button.setFixedSize(30, 30)
        browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_button.icon_kind = "folder"
        browse_button.icon_role = "ghost"
        browse_button.clicked.connect(lambda: self._browse_path(self.rclone_path_edit, "file"))
        layout.addWidget(browse_button)
        self.rclone_path_edit.browse_button = browse_button

        self.rclone_update_btn = QPushButton("Update")
        self.rclone_update_btn.setObjectName("GhostBtn")
        self.rclone_update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rclone_update_btn.setEnabled(self.config_data.get("rclone_update_available", False))
        self.rclone_update_btn.setToolTip(self.config_data.get("rclone_update_tooltip", ""))
        self.rclone_update_btn.clicked.connect(self._request_rclone_update)
        layout.addWidget(self.rclone_update_btn)
        return row

    def _build_picker_row(self, line_edit, mode):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(line_edit, 1)

        button = QPushButton("")
        button.setObjectName("GhostBtn")
        button.setFixedSize(30, 30)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.icon_kind = "folder"
        button.icon_role = "ghost"
        button.clicked.connect(lambda: self._browse_path(line_edit, mode))
        layout.addWidget(button)
        line_edit.browse_button = button
        return row

    def _browse_path(self, target_edit, mode):
        current = target_edit.text().strip()
        start = current or os.path.expanduser("~")
        if mode == "file":
            selected, _ = QFileDialog.getOpenFileName(self, "Select File", start)
        else:
            selected = QFileDialog.getExistingDirectory(self, "Select Folder", start)
        if selected:
            target_edit.setText(selected)

    def refresh_icons(self, theme_name="light"):
        color = "#DCE8F5" if theme_name == "dark" else "#5F7087"
        for edit in (self.rclone_path_edit, self.rclone_conf_edit):
            edit.browse_button.setIcon(_make_line_icon("folder", color))

    def _request_rclone_update(self):
        self.update_rclone_requested = True
        self.accept()

    def set_rclone_version_status(self, text: str, update_available=None, tooltip=None):
        self.rclone_version_label.setText(text)
        if update_available is not None:
            self.rclone_update_btn.setEnabled(update_available)
        if tooltip is not None:
            self.rclone_update_btn.setToolTip(tooltip)

    def get_data(self):
        return {
            "rclone_path": self.rclone_path_edit.text().strip() or "rclone.exe",
            "rclone_conf_path": self.rclone_conf_edit.text().strip(),
            "theme": self.theme_combo.currentText(),
            "auto_start": self.auto_start_check.isChecked(),
            "mount_on_launch": self.mount_on_launch_check.isChecked(),
            "start_minimized": self.start_minimized_check.isChecked(),
            "minimize_to_tray": self.minimize_to_tray_check.isChecked(),
        }


class LDriveMainWindow(QMainWindow):
    add_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    theme_toggle_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.current_theme = "light"
        self.setWindowTitle("L-Drive")
        self.setMinimumSize(460, 330)
        self.resize(500, 360)
        self._init_ui()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange and self.isMinimized():
            self.hide()

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

        self.theme_btn = self._make_top_icon_button("theme", "Theme")
        self.theme_btn.clicked.connect(self.theme_toggle_requested.emit)
        self.settings_btn = self._make_top_icon_button("settings", "Settings")
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        self.add_btn = self._make_top_icon_button("add", "Add", accent=True)
        self.add_btn.clicked.connect(self.add_requested.emit)

        top_layout.addWidget(self.theme_btn)
        top_layout.addWidget(self.settings_btn)
        top_layout.addWidget(self.add_btn)
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
        self.refresh_icons("light")

    def _make_top_icon_button(self, kind, tooltip, accent=False):
        button = QPushButton("")
        button.icon_kind = kind
        button.icon_role = "accent" if accent else "ghost"
        button.setObjectName("AccentBtn" if accent else "GhostBtn")
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedSize(28, 28)
        return button

    def refresh_icons(self, theme_name="light"):
        self.current_theme = theme_name
        palette = {
            "light": {"ghost": "#5F7087", "accent": "#FFFFFF"},
            "dark": {"ghost": "#DCE8F5", "accent": "#FFFFFF"},
        }["dark" if theme_name == "dark" else "light"]

        for button in (self.theme_btn, self.settings_btn, self.add_btn):
            role = button.icon_role
            color = palette["accent"] if role == "accent" else palette["ghost"]
            button.setIcon(_make_line_icon(button.icon_kind, color))

        for i in range(self.card_layout.count()):
            widget = self.card_layout.itemAt(i).widget()
            if isinstance(widget, DriveCardWidget):
                widget.refresh_icons(theme_name)

    def clear_cards(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def add_card(self, card_widget):
        card_widget.refresh_icons(self.current_theme)
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
        add_btn.setIcon(_make_line_icon("add", "#FFFFFF"))
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
        self.refresh_icons(theme_name)

    @staticmethod
    def resource_path(relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        return os.path.join(base_path, relative_path)

    def append_log(self, message: str):
        import datetime

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_viewer.appendPlainText(f"[{timestamp}] {message}")
        self.log_viewer.verticalScrollBar().setValue(self.log_viewer.verticalScrollBar().maximum())


class LDriveTrayIcon(QSystemTrayIcon):
    show_requested = pyqtSignal()
    exit_requested = pyqtSignal()
    toggle_mount_requested = pyqtSignal(str, bool)

    def __init__(self, icon, parent=None):
        super().__init__(icon, parent)
        self.profile_states = []
        self.refresh_menu()
        self.activated.connect(self._on_activated)

    def set_profiles(self, profile_states):
        self.profile_states = profile_states
        self.refresh_menu()

    def refresh_menu(self):
        menu = QMenu()
        show = QAction("Open", self)
        show.triggered.connect(self.show_requested.emit)
        menu.addAction(show)
        menu.addSeparator()

        if self.profile_states:
            for item in self.profile_states:
                mounted = item.get("mounted", False)
                drive = item.get("letter", "?")
                remote = item.get("remote", "")
                root = item.get("root_folder", "/")
                label = f"{'■' if mounted else '▶'} {drive}: ({remote}:{root})"
                action = QAction(label, self)
                action.triggered.connect(
                    lambda _checked=False, pid=item["id"], should_start=not mounted: self.toggle_mount_requested.emit(pid, should_start)
                )
                menu.addAction(action)
            menu.addSeparator()

        close = QAction("Exit", self)
        close.triggered.connect(self.exit_requested.emit)
        menu.addAction(close)
        self.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_requested.emit()
