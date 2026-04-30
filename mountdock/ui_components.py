import os
import re
import string
import subprocess
import sys
import threading

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal, QThread
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QTextCursor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
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

from mountdock.i18n import tr


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
    def __init__(self, remotes, lang="en", parent=None, profile=None, used_letters=None, system_used_letters=None, used_remotes=None):
        super().__init__(parent)
        self.lang = lang
        self.profile = profile or {}
        current_remote = str(self.profile.get("remote", "")).strip()
        blocked_remotes = {str(name).strip() for name in (used_remotes or []) if str(name).strip()}
        self.remotes = [name for name in remotes if name == current_remote or name not in blocked_remotes]
        self.used_letters = {str(letter).replace(':', '').upper() for letter in (used_letters or [])}
        self.system_used_letters = {str(letter).replace(':', '').upper() for letter in (system_used_letters or [])}
        self.setObjectName("SheetDialog")
        self.setWindowTitle(tr(self.lang, "drive_title"))
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
        self.auto_mount_check = QCheckBox(tr(self.lang, "auto_mount_drive"))
        self.auto_mount_check.setChecked(self.profile.get("auto_mount", False))

        form.addRow(tr(self.lang, "remote"), self.remote_combo)
        form.addRow(tr(self.lang, "drive"), self.letter_combo)
        form.addRow(tr(self.lang, "name"), self.vol_edit)
        form.addRow(tr(self.lang, "path"), self.root_edit)
        form.addRow(tr(self.lang, "cache_dir"), self.cache_dir_edit)
        form.addRow(tr(self.lang, "extra_args"), self.extra_args_edit)
        form.addRow(tr(self.lang, "vfs"), self.vfs_combo)
        form.addRow("", self.auto_mount_check)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch()

        cancel = QPushButton(tr(self.lang, "cancel"))
        cancel.setObjectName("GhostBtn")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)

        save = QPushButton(tr(self.lang, "save"))
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
            QMessageBox.warning(self, tr(self.lang, "validation_error"), tr(self.lang, "remote_required"))
            return

        if root and not root.startswith("/"):
            QMessageBox.warning(self, tr(self.lang, "validation_error"), tr(self.lang, "path_must_start"))
            return

        if cache_dir and any(ch in cache_dir for ch in ['"', "'", "\n", "\r"]):
            QMessageBox.warning(self, tr(self.lang, "validation_error"), tr(self.lang, "cache_invalid"))
            return

        if any(ch in extra_args for ch in ["\n", "\r"]):
            QMessageBox.warning(self, tr(self.lang, "validation_error"), tr(self.lang, "args_single_line"))
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

    def __init__(self, profile, lang="en"):
        super().__init__()
        self.profile = profile
        self.lang = lang
        self.is_running = False
        self.current_theme = "light"
        self.setObjectName("DriveCard")
        self._init_ui()

    def _init_ui(self):
        self.setMinimumHeight(38)
        self.setObjectName("")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 1, 6, 1)
        layout.setSpacing(6)

        self.status_dot = QLabel("")
        self.status_dot.setObjectName("StatusDot")
        self.status_dot.setFixedSize(10, 10)
        layout.addWidget(self.status_dot, 0, Qt.AlignmentFlag.AlignVCenter)

        self.badge = QLabel(self.profile["letter"])
        self.badge.setObjectName("LetterBadge")
        self.badge.setFixedSize(24, 24)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignVCenter)

        display_name = self.profile.get("volname") or self.profile["remote"]
        self.name_label = QLabel(display_name)
        self.name_label.setObjectName("CardTitle")
        self.name_label.setWordWrap(False)
        layout.addWidget(self.name_label, 1, Qt.AlignmentFlag.AlignVCenter)

        self.toggle_btn = self._make_icon_button("play", tr(self.lang, "connect"), accent=True)
        self.toggle_btn.clicked.connect(self._on_toggle)
        layout.addWidget(self.toggle_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.edit_btn = self._make_icon_button("edit", tr(self.lang, "edit"))
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.profile["id"]))
        layout.addWidget(self.edit_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.delete_btn = self._make_icon_button("trash", tr(self.lang, "delete"), danger=True)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.profile["id"]))
        layout.addWidget(self.delete_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.set_status("Disconnected")

    def _make_icon_button(self, kind, tooltip, danger=False, accent=False):
        button = QPushButton("")
        button.icon_kind = kind
        if accent:
            button.icon_role = "accent"
            button.setObjectName("AccentBtn")
        elif danger:
            button.icon_role = "danger"
            button.setObjectName("GhostDangerBtn")
        else:
            button.icon_role = "ghost"
            button.setObjectName("GhostBtn")
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
            self.toggle_btn.setToolTip(tr(self.lang, "disconnect"))
            self.toggle_btn.setObjectName("DangerBtn")
            self.status_dot.setProperty("state", "connected")
            self.is_running = True
        elif status == "Admin Block":
            self.toggle_btn.icon_kind = "play"
            self.toggle_btn.setToolTip(tr(self.lang, "connect"))
            self.toggle_btn.setObjectName("GhostBtn")
            self.status_dot.setProperty("state", "blocked")
            self.is_running = False
        else:
            self.toggle_btn.icon_kind = "play"
            self.toggle_btn.setToolTip(tr(self.lang, "connect"))
            self.toggle_btn.setObjectName("AccentBtn" if status == "Disconnected" else "GhostBtn")
            self.status_dot.setProperty("state", "idle" if status == "Disconnected" else "busy")
            self.is_running = False

        self.toggle_btn.setToolTip(tr(self.lang, "disconnect") if status == "Connected" else tr(self.lang, "connect"))
        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)
        self.refresh_icons(self.current_theme)


class RcloneConfigWorker(QThread):
    output_received = pyqtSignal(str)
    running_changed = pyqtSignal(bool)
    failed_to_start = pyqtSignal(str)
    finished_with_status = pyqtSignal(int, bool)

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._lock = threading.Lock()
        self._process = None
        self._stop_requested = False

    def run(self):
        self._stop_requested = False
        process = self.engine.start_config_session()
        if not process:
            self.failed_to_start.emit(self.engine.last_error or "Failed to start rclone config")
            self.finished_with_status.emit(-1, False)
            return

        with self._lock:
            self._process = process

        self.running_changed.emit(True)
        self.output_received.emit(f"$ {subprocess.list2cmdline(self.engine.build_config_command())}\n\n")

        stream = process.stdout
        pending = []
        try:
            while True:
                chunk = stream.read(1) if stream is not None else ""
                if chunk == "":
                    if process.poll() is not None:
                        break
                    continue

                pending.append(chunk)
                if chunk == "\n" or len(pending) >= 80 or chunk in {":", ">", ")", "?"}:
                    self.output_received.emit("".join(pending))
                    pending.clear()
        finally:
            if pending:
                self.output_received.emit("".join(pending))

            code = process.wait()
            with self._lock:
                self._process = None
            self.running_changed.emit(False)
            self.finished_with_status.emit(code, self._stop_requested)

    def send_input(self, value: str) -> bool:
        with self._lock:
            process = self._process

        if not process or process.stdin is None or process.poll() is not None:
            return False

        try:
            process.stdin.write(f"{value}\n")
            process.stdin.flush()
            return True
        except Exception as exc:
            self.output_received.emit(f"\n[MountDock] {exc}\n")
            return False

    def stop_session(self):
        self._stop_requested = True
        with self._lock:
            process = self._process

        if not process or process.poll() is not None:
            return

        try:
            process.terminate()
            process.wait(timeout=1)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass


class RcloneConfigDialog(QDialog):
    def __init__(self, engine, lang="en", parent=None):
        super().__init__(parent)
        self.engine = engine
        self.lang = lang
        self.worker = None
        self.is_running = False
        self.config_changed = False
        self._restart_pending = False
        self._close_pending = False
        self._secret_mode = False
        self._helper_rows = []
        self.setObjectName("SheetDialog")
        self.setWindowTitle(tr(self.lang, "rclone_config_title"))
        self.resize(720, 520)
        self._init_ui()
        self._start_session(clear_log=True)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        hint = QLabel(tr(self.lang, "rclone_config_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.status_label = QLabel(tr(self.lang, "rclone_config_status_idle"))
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setMinimumHeight(300)
        layout.addWidget(self.log_viewer, 1)

        self.helper_title = QLabel(tr(self.lang, "rclone_config_choices"))
        layout.addWidget(self.helper_title)

        self.helper_host = QWidget()
        self.helper_layout = QVBoxLayout(self.helper_host)
        self.helper_layout.setContentsMargins(0, 0, 0, 0)
        self.helper_layout.setSpacing(6)
        layout.addWidget(self.helper_host)

        input_label = QLabel(tr(self.lang, "rclone_config_input"))
        layout.addWidget(input_label)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText(tr(self.lang, "rclone_config_placeholder"))
        self.input_edit.returnPressed.connect(self._send_current_input)
        input_row.addWidget(self.input_edit, 1)

        self.send_btn = QPushButton(tr(self.lang, "rclone_config_send"))
        self.send_btn.setObjectName("AccentBtn")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self._send_current_input)
        input_row.addWidget(self.send_btn)
        layout.addLayout(input_row)

        buttons = QHBoxLayout()
        buttons.addStretch()

        self.restart_btn = QPushButton(tr(self.lang, "rclone_config_restart"))
        self.restart_btn.setObjectName("GhostBtn")
        self.restart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restart_btn.clicked.connect(self._restart_session)

        self.close_btn = QPushButton(tr(self.lang, "rclone_config_cancel"))
        self.close_btn.setObjectName("GhostBtn")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self._handle_close)

        buttons.addWidget(self.restart_btn)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

        self._set_helper_choices([])
        self._set_running(False)

    def _start_session(self, clear_log=False):
        if clear_log:
            self.log_viewer.clear()
        self._set_helper_choices([])
        self._apply_secret_mode(False)
        self.input_edit.clear()
        self.worker = RcloneConfigWorker(self.engine)
        self.worker.output_received.connect(self._append_output)
        self.worker.running_changed.connect(self._set_running)
        self.worker.failed_to_start.connect(self._handle_failed_start)
        self.worker.finished_with_status.connect(self._handle_session_finished)
        self.worker.start()

    def _append_output(self, text: str):
        cursor = self.log_viewer.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_viewer.setTextCursor(cursor)
        self.log_viewer.insertPlainText(text)
        self.log_viewer.verticalScrollBar().setValue(self.log_viewer.verticalScrollBar().maximum())
        self._refresh_prompt_state()

    def _refresh_prompt_state(self):
        recent_text = self.log_viewer.toPlainText()[-4000:]
        self._apply_secret_mode(self._looks_like_secret_prompt(recent_text))
        self._set_helper_choices(self._extract_helper_choices(recent_text))

    def _looks_like_secret_prompt(self, text: str) -> bool:
        recent_lines = [line.strip() for line in text.splitlines() if line.strip()]
        recent_tail = "\n".join(recent_lines[-6:]).lower()
        if not recent_tail:
            return False
        secret_tokens = [
            "password",
            "secret",
            "token",
            "apikey",
            "api key",
            "pass phrase",
            "passphrase",
            "client_secret",
            "access key",
        ]
        return any(token in recent_tail for token in secret_tokens)

    def _extract_helper_choices(self, text: str):
        lines = text.splitlines()[-120:]
        groups = []
        current = []
        for line in lines:
            stripped = line.rstrip()
            match = re.match(r"^\s*([A-Za-z0-9._-]+)\)\s+(.+?)\s*$", stripped)
            if not match:
                match = re.match(r"^\s*([A-Za-z0-9._-]+)\s*/\s+(.+?)\s*$", stripped)
            if match:
                current.append((match.group(1), self._normalize_choice_label(match.group(2))))
                continue
            if current and (stripped.startswith(" ") or stripped.startswith("\t")):
                continue
            if current:
                groups.append(current)
                current = []
        if current:
            groups.append(current)
        if not groups:
            return []

        latest = []
        seen = set()
        for value, label in groups[-1]:
            normalized_value = value.strip()
            if normalized_value in seen:
                continue
            seen.add(normalized_value)
            latest.append((normalized_value, label))
        return latest[:12]

    def _normalize_choice_label(self, label: str) -> str:
        normalized = re.sub(r"\s+", " ", label).strip()
        normalized = re.sub(r"\s*\([^)]*default[^)]*\)", "", normalized, flags=re.IGNORECASE).strip()
        return normalized or label.strip()

    def _set_helper_choices(self, choices):
        while self.helper_layout.count():
            item = self.helper_layout.takeAt(0)
            if item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                item.layout().deleteLater()
            elif item.widget():
                item.widget().deleteLater()

        self.helper_title.setVisible(True)
        self.helper_host.setVisible(True)
        if not choices:
            empty_label = QLabel(tr(self.lang, "rclone_config_no_choices"))
            empty_label.setWordWrap(True)
            self.helper_layout.addWidget(empty_label)
            return

        row = None
        for index, (value, label) in enumerate(choices):
            if index % 3 == 0:
                row = QHBoxLayout()
                row.setSpacing(6)
                self.helper_layout.addLayout(row)
            button = QPushButton(f"{value} · {label}")
            button.setObjectName("GhostBtn")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, answer=value: self._apply_helper_choice(answer))
            row.addWidget(button)
        if row is not None:
            row.addStretch()

    def _apply_helper_choice(self, value: str):
        self.input_edit.setText(value)
        self._send_current_input()

    def _apply_secret_mode(self, enabled: bool):
        self._secret_mode = enabled
        mode = QLineEdit.EchoMode.Password if enabled else QLineEdit.EchoMode.Normal
        self.input_edit.setEchoMode(mode)
        self.input_edit.setPlaceholderText(
            tr(self.lang, "rclone_config_placeholder_secret") if enabled else tr(self.lang, "rclone_config_placeholder")
        )
        self.status_label.setText(
            tr(self.lang, "rclone_config_status_secret") if enabled else (tr(self.lang, "rclone_config_running") if self.is_running else tr(self.lang, "rclone_config_status_idle"))
        )

    def _send_current_input(self):
        value = self.input_edit.text()
        if not self.worker or not self.is_running:
            return
        masked = "*" * max(4, len(value)) if self._secret_mode and value else value
        if self.worker.send_input(value):
            self.log_viewer.appendPlainText(f"> {masked}")
            self.input_edit.clear()
            self._refresh_prompt_state()

    def _restart_session(self):
        if self.is_running and self.worker:
            self._restart_pending = True
            self.worker.stop_session()
            return
        self._start_session(clear_log=True)

    def _handle_close(self):
        if self.is_running and self.worker:
            self._close_pending = True
            self.worker.stop_session()
            return
        self.accept()

    def closeEvent(self, event):
        if self.is_running and self.worker and not self._close_pending:
            self._close_pending = True
            self.worker.stop_session()
            event.ignore()
            return
        super().closeEvent(event)

    def _handle_failed_start(self, message: str):
        self._append_output(tr(self.lang, "rclone_config_failed_start", message=message) + "\n")
        QMessageBox.critical(self, tr(self.lang, "rclone_config_title"), tr(self.lang, "rclone_config_failed_start", message=message))

    def _handle_session_finished(self, exit_code: int, stopped: bool):
        self._set_running(False)
        if exit_code == 0 and not stopped:
            self.config_changed = True
            message = tr(self.lang, "rclone_config_exited_ok")
            self.status_label.setText(message)
            self._append_output("\n" + message + "\n")
        elif stopped:
            message = tr(self.lang, "rclone_config_stopped")
            self.status_label.setText(message)
            self._append_output("\n" + message + "\n")
        elif exit_code >= 0:
            message = tr(self.lang, "rclone_config_exited_fail", code=exit_code)
            self.status_label.setText(message)
            self._append_output("\n" + message + "\n")

        if self._restart_pending:
            self._restart_pending = False
            self._close_pending = False
            self._start_session(clear_log=True)
            return

        if self._close_pending:
            self._close_pending = False
            self.accept()

    def _set_running(self, running: bool):
        self.is_running = running
        self.input_edit.setEnabled(running)
        self.send_btn.setEnabled(running)
        self.restart_btn.setEnabled(True)
        self.close_btn.setText(tr(self.lang, "rclone_config_cancel" if running else "rclone_config_close"))
        if running:
            self.status_label.setText(tr(self.lang, "rclone_config_running"))
            self.helper_title.setText(tr(self.lang, "rclone_config_choices"))
        else:
            self.status_label.setText(tr(self.lang, "rclone_config_status_idle"))
            self._apply_secret_mode(False)


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


class AppUpdateWorker(QThread):
    progress_changed = pyqtSignal(int)
    finished_with_result = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, updater, installer_url, installer_name=""):
        super().__init__()
        self.updater = updater
        self.installer_url = installer_url
        self.installer_name = installer_name

    def run(self):
        try:
            result = self.updater.download_installer(
                self.installer_url,
                filename=self.installer_name or None,
                progress_cb=self.progress_changed.emit,
            )
            self.finished_with_result.emit(str(result))
        except Exception as exc:
            self.failed.emit(str(exc))


class AppUpdateDialog(QDialog):
    def __init__(self, installed_version, latest_version, lang="en", parent=None):
        super().__init__(parent)
        self.lang = lang
        self.setObjectName("SheetDialog")
        self.setWindowTitle(tr(self.lang, "app_update_title"))
        self.setFixedWidth(420)
        self.installed_version = installed_version or "unknown"
        self.latest_version = latest_version or "unknown"
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        title = QLabel(f"MountDock {self.installed_version} → {self.latest_version}")
        title.setObjectName("CardTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        note = QLabel(tr(self.lang, "app_update_downloading"))
        note.setWordWrap(True)
        layout.addWidget(note)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.status_label = QLabel(tr(self.lang, "app_update_starting"))
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.close_btn = QPushButton(tr(self.lang, "close"))
        self.close_btn.setObjectName("GhostBtn")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)


class RcloneUpdateDialog(QDialog):
    def __init__(self, installed_version, latest_version, lang="en", parent=None):
        super().__init__(parent)
        self.lang = lang
        self.setObjectName("SheetDialog")
        self.setWindowTitle(tr(self.lang, "rclone_update_title"))
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

        note = QLabel(tr(self.lang, "rclone_update_downloading"))
        note.setWordWrap(True)
        layout.addWidget(note)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.status_label = QLabel(tr(self.lang, "rclone_update_starting"))
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.close_btn = QPushButton(tr(self.lang, "close"))
        self.close_btn.setObjectName("GhostBtn")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

    def set_progress(self, value: int):
        self.progress.setValue(max(0, min(100, value)))
        self.status_label.setText(tr(self.lang, "rclone_downloading_progress", percent=self.progress.value()))

    def mark_done(self, message: str):
        self.progress.setValue(100)
        self.status_label.setText(message)
        self.close_btn.setEnabled(True)

    def mark_failed(self, message: str):
        self.status_label.setText(message)
        self.close_btn.setEnabled(True)


class PassphraseDialog(QDialog):
    def __init__(self, lang="en", title="", prompt="", require_confirm=False, remember_enabled=False, parent=None):
        super().__init__(parent)
        self.lang = lang
        self.require_confirm = require_confirm
        self.remember_enabled = remember_enabled
        self.setObjectName("SheetDialog")
        self.setWindowTitle(title)
        self.setFixedWidth(420)
        self._init_ui(prompt)

    def _init_ui(self, prompt: str):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        note = QLabel(prompt)
        note.setWordWrap(True)
        layout.addWidget(note)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)

        self.passphrase_edit = QLineEdit()
        self.passphrase_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(tr(self.lang, "path"), self.passphrase_edit)

        self.confirm_edit = None
        if self.require_confirm:
            self.confirm_edit = QLineEdit()
            self.confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
            form.addRow(tr(self.lang, "passphrase_confirm"), self.confirm_edit)

        layout.addLayout(form)

        self.remember_check = None
        if self.remember_enabled:
            self.remember_check = QCheckBox(tr(self.lang, "remember_on_device"))
            layout.addWidget(self.remember_check)

        buttons = QHBoxLayout()
        buttons.addStretch()

        cancel = QPushButton(tr(self.lang, "cancel"))
        cancel.setObjectName("GhostBtn")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)

        save = QPushButton(tr(self.lang, "save"))
        save.setObjectName("AccentBtn")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self._validate_and_accept)

        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def _validate_and_accept(self):
        passphrase = self.passphrase_edit.text()
        if not passphrase:
            QMessageBox.warning(self, tr(self.lang, "validation_error"), tr(self.lang, "passphrase_required"))
            return
        if self.require_confirm and self.confirm_edit is not None and passphrase != self.confirm_edit.text():
            QMessageBox.warning(self, tr(self.lang, "validation_error"), tr(self.lang, "passphrase_mismatch"))
            return
        self.accept()

    def get_passphrase(self) -> str:
        return self.passphrase_edit.text()

    def remember_on_device(self) -> bool:
        return bool(self.remember_check and self.remember_check.isChecked())


class GoogleSyncDialog(QDialog):
    def __init__(self, config_data, lang="en", parent=None):
        super().__init__(parent)
        self.lang = lang
        self.config_data = config_data
        self.setObjectName("SheetDialog")
        self.setWindowTitle(tr(self.lang, "google_sync"))
        self.setFixedWidth(620)
        self.google_sign_in_requested = False
        self.google_sign_out_requested = False
        self.google_backup_requested = False
        self.google_restore_requested = False
        self.google_check_backup_requested = False
        self.on_google_sign_in = None
        self.on_google_sign_out = None
        self.on_google_backup = None
        self.on_google_restore = None
        self.on_google_check_backup = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)

        self.google_client_secret_edit = QLineEdit(self.config_data.get("google_client_secret_path", ""))
        form.addRow(tr(self.lang, "google_client_secret"), self._build_picker_row(self.google_client_secret_edit, "file"))
        layout.addLayout(form)

        self.google_sync_status_label = QLabel("")
        self.google_sync_status_label.setWordWrap(True)
        layout.addWidget(self.google_sync_status_label)

        self.google_sync_backup_label = QLabel("")
        self.google_sync_backup_label.setWordWrap(True)
        layout.addWidget(self.google_sync_backup_label)

        self.google_sync_backup_presence_label = QLabel("")
        self.google_sync_backup_presence_label.setWordWrap(True)
        layout.addWidget(self.google_sync_backup_presence_label)

        self.google_sync_restore_label = QLabel("")
        self.google_sync_restore_label.setWordWrap(True)
        layout.addWidget(self.google_sync_restore_label)

        self.google_sync_target_label = QLabel("")
        self.google_sync_target_label.setWordWrap(True)
        layout.addWidget(self.google_sync_target_label)

        self.google_sync_token_label = QLabel("")
        self.google_sync_token_label.setWordWrap(True)
        layout.addWidget(self.google_sync_token_label)

        google_grid = QGridLayout()
        google_grid.setHorizontalSpacing(8)
        google_grid.setVerticalSpacing(8)
        self.google_sign_in_btn = QPushButton(tr(self.lang, "google_sign_in"))
        self.google_sign_in_btn.setObjectName("GhostBtn")
        self.google_sign_in_btn.clicked.connect(self._request_google_sign_in)

        self.google_sign_out_btn = QPushButton(tr(self.lang, "google_sign_out"))
        self.google_sign_out_btn.setObjectName("GhostBtn")
        self.google_sign_out_btn.clicked.connect(self._request_google_sign_out)

        self.google_backup_btn = QPushButton(tr(self.lang, "google_backup_conf_button"))
        self.google_backup_btn.setObjectName("GhostBtn")
        self.google_backup_btn.clicked.connect(self._request_google_backup)

        self.google_restore_btn = QPushButton(tr(self.lang, "google_restore_conf_button"))
        self.google_restore_btn.setObjectName("GhostBtn")
        self.google_restore_btn.clicked.connect(self._request_google_restore)

        self.google_check_backup_btn = QPushButton(tr(self.lang, "google_check_backup"))
        self.google_check_backup_btn.setObjectName("GhostBtn")
        self.google_check_backup_btn.clicked.connect(self._request_google_check_backup)

        for button in (
            self.google_sign_in_btn,
            self.google_sign_out_btn,
            self.google_backup_btn,
            self.google_restore_btn,
            self.google_check_backup_btn,
        ):
            button.setMinimumHeight(44)

        google_grid.addWidget(self.google_sign_in_btn, 0, 0)
        google_grid.addWidget(self.google_sign_out_btn, 0, 1)
        google_grid.addWidget(self.google_backup_btn, 1, 0)
        google_grid.addWidget(self.google_restore_btn, 1, 1)
        google_grid.addWidget(self.google_check_backup_btn, 2, 0, 1, 2)
        layout.addLayout(google_grid)

        buttons = QHBoxLayout()
        buttons.addStretch()
        close = QPushButton(tr(self.lang, "close"))
        close.setObjectName("AccentBtn")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        self.refresh_icons(self.config_data.get("theme", "light"))
        self.set_google_sync_status(
            self.config_data.get("google_account_email", ""),
            self.config_data.get("google_sync_last_uploaded_at", ""),
            self.config_data.get("google_sync_last_downloaded_at", ""),
        )

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
            selected, _ = QFileDialog.getOpenFileName(self, tr(self.lang, "config"), start)
        else:
            selected = QFileDialog.getExistingDirectory(self, tr(self.lang, "cache_dir"), start)
        if selected:
            target_edit.setText(selected)

    def refresh_icons(self, theme_name="light"):
        color = "#DCE8F5" if theme_name == "dark" else "#5F7087"
        self.google_client_secret_edit.browse_button.setIcon(_make_line_icon("folder", color))

    def _request_google_sign_in(self):
        if callable(self.on_google_sign_in):
            self.on_google_sign_in()

    def _request_google_sign_out(self):
        if callable(self.on_google_sign_out):
            self.on_google_sign_out()

    def _request_google_backup(self):
        if callable(self.on_google_backup):
            self.on_google_backup()

    def _request_google_restore(self):
        if callable(self.on_google_restore):
            self.on_google_restore()

    def _request_google_check_backup(self):
        if callable(self.on_google_check_backup):
            self.on_google_check_backup()

    def set_google_sync_status(self, email: str, last_uploaded: str = "", last_downloaded: str = "", restore_target: str = "", token_path: str = "", backup_exists: bool | None = None, signed_in: bool | None = None):
        effective_signed_in = bool(str(email).strip()) if signed_in is None else bool(signed_in)
        if effective_signed_in and str(email).strip():
            status_text = tr(self.lang, "google_sync_status_signed_in", email=email)
        elif effective_signed_in:
            status_text = tr(self.lang, "google_sync_status_signed_in_generic")
        else:
            status_text = tr(self.lang, "google_sync_status_signed_out")
        self.google_sync_status_label.setText(status_text)
        self.google_sync_backup_label.setText(
            tr(self.lang, "google_sync_last_upload", value=last_uploaded) if last_uploaded else ""
        )
        self.google_sync_backup_presence_label.setText(
            tr(self.lang, "google_backup_exists") if backup_exists is True else (tr(self.lang, "google_backup_missing") if backup_exists is False else "")
        )
        self.google_sync_restore_label.setText(
            tr(self.lang, "google_sync_last_restore", value=last_downloaded) if last_downloaded else ""
        )
        self.google_sync_target_label.setText(
            tr(self.lang, "google_restore_target", value=restore_target) if restore_target else ""
        )
        self.google_sync_token_label.setText(
            tr(self.lang, "google_token_path", value=token_path) if token_path else ""
        )
        self.google_sign_out_btn.setEnabled(effective_signed_in)

    def get_data(self):
        return {
            "google_client_secret_path": self.google_client_secret_edit.text().strip(),
        }


class GlobalSettingsDialog(QDialog):
    def __init__(self, config_data, lang="en", parent=None):
        super().__init__(parent)
        self.lang = lang
        self.config_data = config_data
        self.setObjectName("SheetDialog")
        self.setWindowTitle(tr(self.lang, "settings_title"))
        self.setFixedWidth(420)
        self.update_rclone_requested = False
        self.check_app_update_requested = False
        self.open_app_download_requested = False
        self.install_app_update_requested = False
        self.open_rclone_config_requested = False
        self.open_google_sync_requested = False
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

        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("한국어", "ko")
        current_lang = self.config_data.get("language", self.lang)
        idx = self.language_combo.findData(current_lang)
        if idx >= 0:
            self.language_combo.setCurrentIndex(idx)

        form.addRow(tr(self.lang, "rclone"), self._build_rclone_row())
        form.addRow(tr(self.lang, "config"), self._build_picker_row(self.rclone_conf_edit, "file"))
        form.addRow(tr(self.lang, "theme"), self.theme_combo)
        form.addRow(tr(self.lang, "language"), self.language_combo)
        layout.addLayout(form)

        self.rclone_version_label = QLabel(self.config_data.get("rclone_version_status", tr(self.lang, "rclone_version_unknown")))
        self.rclone_version_label.setWordWrap(True)
        layout.addWidget(self.rclone_version_label)

        self.app_version_label = QLabel(self.config_data.get("app_version_status", tr(self.lang, "app_version_unknown")))
        self.app_version_label.setWordWrap(True)
        layout.addWidget(self.app_version_label)

        self.app_update_buttons = QHBoxLayout()
        self.app_update_check_btn = QPushButton(tr(self.lang, "app_update_check"))
        self.app_update_check_btn.setObjectName("GhostBtn")
        self.app_update_check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.app_update_check_btn.clicked.connect(self._request_app_update_check)
        self.app_update_buttons.addWidget(self.app_update_check_btn)

        self.app_update_install_btn = QPushButton(tr(self.lang, "app_update_install_now"))
        self.app_update_install_btn.setObjectName("GhostBtn")
        self.app_update_install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.app_update_install_btn.setEnabled(bool(self.config_data.get("app_installer_url")))
        self.app_update_install_btn.clicked.connect(self._request_app_update_install)
        self.app_update_buttons.addWidget(self.app_update_install_btn)

        self.app_update_open_btn = QPushButton(tr(self.lang, "app_update_open_download"))
        self.app_update_open_btn.setObjectName("GhostBtn")
        self.app_update_open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.app_update_open_btn.setEnabled(bool(self.config_data.get("app_download_url")))
        self.app_update_open_btn.clicked.connect(self._request_app_download_open)
        self.app_update_buttons.addWidget(self.app_update_open_btn)
        layout.addLayout(self.app_update_buttons)

        self.rclone_config_btn = QPushButton(tr(self.lang, "rclone_config_button"))
        self.rclone_config_btn.setObjectName("GhostBtn")
        self.rclone_config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rclone_config_btn.clicked.connect(self._request_rclone_config)
        layout.addWidget(self.rclone_config_btn)

        self.google_sync_title = QLabel(tr(self.lang, "google_sync"))
        self.google_sync_title.setObjectName("CardTitle")
        layout.addWidget(self.google_sync_title)

        self.google_sync_status_label = QLabel("")
        self.google_sync_status_label.setWordWrap(True)
        layout.addWidget(self.google_sync_status_label)

        self.google_sync_backup_presence_label = QLabel("")
        self.google_sync_backup_presence_label.setWordWrap(True)
        layout.addWidget(self.google_sync_backup_presence_label)

        self.google_sync_open_btn = QPushButton(tr(self.lang, "google_sync_open"))
        self.google_sync_open_btn.setObjectName("GhostBtn")
        self.google_sync_open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.google_sync_open_btn.clicked.connect(self._request_open_google_sync)
        layout.addWidget(self.google_sync_open_btn)

        self.auto_start_check = QCheckBox(tr(self.lang, "auto_start"))
        self.auto_start_check.setChecked(self.config_data.get("auto_start", False))
        self.mount_on_launch_check = QCheckBox(tr(self.lang, "mount_on_launch"))
        self.mount_on_launch_check.setChecked(self.config_data.get("mount_on_launch", False))
        self.start_minimized_check = QCheckBox(tr(self.lang, "start_to_tray"))
        self.start_minimized_check.setChecked(self.config_data.get("start_minimized", False))
        self.minimize_to_tray_check = QCheckBox(tr(self.lang, "minimize_to_tray"))
        self.minimize_to_tray_check.setChecked(self.config_data.get("minimize_to_tray", True))
        layout.addWidget(self.auto_start_check)
        layout.addWidget(self.mount_on_launch_check)
        layout.addWidget(self.start_minimized_check)
        layout.addWidget(self.minimize_to_tray_check)

        buttons = QHBoxLayout()
        buttons.addStretch()

        cancel = QPushButton(tr(self.lang, "cancel"))
        cancel.setObjectName("GhostBtn")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)

        save = QPushButton(tr(self.lang, "save"))
        save.setObjectName("AccentBtn")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self.accept)

        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)
        self.refresh_icons(self.config_data.get("theme", "light"))
        self.set_google_sync_status(
            self.config_data.get("google_account_email", ""),
            self.config_data.get("google_sync_last_uploaded_at", ""),
            self.config_data.get("google_sync_last_downloaded_at", ""),
        )

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

        self.rclone_update_btn = QPushButton(tr(self.lang, "update"))
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
            selected, _ = QFileDialog.getOpenFileName(self, tr(self.lang, "config"), start)
        else:
            selected = QFileDialog.getExistingDirectory(self, tr(self.lang, "cache_dir"), start)
        if selected:
            target_edit.setText(selected)

    def refresh_icons(self, theme_name="light"):
        color = "#DCE8F5" if theme_name == "dark" else "#5F7087"
        for edit in (self.rclone_path_edit, self.rclone_conf_edit):
            edit.browse_button.setIcon(_make_line_icon("folder", color))

    def _request_rclone_update(self):
        self.update_rclone_requested = True
        self.accept()

    def _request_app_update_check(self):
        self.check_app_update_requested = True
        self.accept()

    def _request_app_download_open(self):
        self.open_app_download_requested = True
        self.accept()

    def _request_app_update_install(self):
        self.install_app_update_requested = True
        self.accept()

    def _request_rclone_config(self):
        self.open_rclone_config_requested = True
        self.accept()

    def _request_open_google_sync(self):
        self.open_google_sync_requested = True
        self.accept()

    def set_rclone_version_status(self, text: str, update_available=None, tooltip=None):
        self.rclone_version_label.setText(text)
        if update_available is not None:
            self.rclone_update_btn.setEnabled(update_available)
        if tooltip is not None:
            self.rclone_update_btn.setToolTip(tooltip)

    def set_app_version_status(self, text: str, update_available=None, tooltip=None, download_url: str = ""):
        self.app_version_label.setText(text)
        if tooltip is not None:
            self.app_update_check_btn.setToolTip(tooltip)
            self.app_update_install_btn.setToolTip(tooltip)
            self.app_update_open_btn.setToolTip(tooltip)
        self.app_update_install_btn.setEnabled(bool(self.config_data.get("app_installer_url")))
        self.app_update_open_btn.setEnabled(bool(download_url))
        self.config_data["app_download_url"] = download_url

    def set_app_installer_url(self, installer_url: str = ""):
        self.config_data["app_installer_url"] = installer_url
        self.app_update_install_btn.setEnabled(bool(installer_url))

    def set_google_sync_status(self, email: str, last_uploaded: str = "", last_downloaded: str = "", restore_target: str = "", token_path: str = "", backup_exists: bool | None = None, signed_in: bool | None = None):
        effective_signed_in = bool(str(email).strip()) if signed_in is None else bool(signed_in)
        if effective_signed_in and str(email).strip():
            status_text = tr(self.lang, "google_sync_status_signed_in", email=email)
        elif effective_signed_in:
            status_text = tr(self.lang, "google_sync_status_signed_in_generic")
        else:
            status_text = tr(self.lang, "google_sync_status_signed_out")
        self.google_sync_status_label.setText(status_text)
        self.google_sync_backup_presence_label.setText(
            tr(self.lang, "google_backup_exists") if backup_exists is True else (tr(self.lang, "google_backup_missing") if backup_exists is False else "")
        )

    def get_data(self):
        return {
            "rclone_path": self.rclone_path_edit.text().strip() or "rclone.exe",
            "rclone_conf_path": self.rclone_conf_edit.text().strip(),
            "theme": self.theme_combo.currentText(),
            "language": self.language_combo.currentData(),
            "google_client_secret_path": self.config_data.get("google_client_secret_path", ""),
            "auto_start": self.auto_start_check.isChecked(),
            "mount_on_launch": self.mount_on_launch_check.isChecked(),
            "start_minimized": self.start_minimized_check.isChecked(),
            "minimize_to_tray": self.minimize_to_tray_check.isChecked(),
        }


class LDriveMainWindow(QMainWindow):
    add_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    mount_all_requested = pyqtSignal()
    unmount_all_requested = pyqtSignal()

    def __init__(self, lang="en"):
        super().__init__()
        self.lang = lang
        self.current_theme = "light"
        self.setWindowTitle(tr(self.lang, "app_title"))
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
        top_layout = QVBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 10, 12, 10)
        top_layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)

        self.brand_icon = QLabel()
        self.brand_icon.setObjectName("BrandIcon")
        self.brand_icon.setFixedSize(40, 40)
        self._refresh_brand_icon()

        self.title_label = QLabel(tr(self.lang, "app_title"))
        self.title_label.setObjectName("AppTitleHeader")

        title_row.addWidget(self.brand_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        title_row.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        title_row.addStretch()
        top_layout.addLayout(title_row)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)
        action_row.addStretch()

        self.mount_all_btn = self._make_top_action_button("play", tr(self.lang, "mount_all"), accent=True)
        self.mount_all_btn.clicked.connect(self.mount_all_requested.emit)
        self.unmount_all_btn = self._make_top_action_button("stop", tr(self.lang, "unmount_all"))
        self.unmount_all_btn.clicked.connect(self.unmount_all_requested.emit)
        self.settings_btn = self._make_top_action_button("settings", tr(self.lang, "settings_title"))
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        self.add_btn = self._make_top_action_button("add", tr(self.lang, "add"), accent=True)
        self.add_btn.clicked.connect(self.add_requested.emit)

        action_row.addWidget(self.mount_all_btn)
        action_row.addWidget(self.unmount_all_btn)
        action_row.addWidget(self.settings_btn)
        action_row.addWidget(self.add_btn)
        top_layout.addLayout(action_row)
        main_layout.addWidget(top_bar)

        self.warning_banner = QLabel("")
        self.warning_banner.setObjectName("WarningBanner")
        self.warning_banner.setWordWrap(True)
        self.warning_banner.hide()
        main_layout.addWidget(self.warning_banner)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("CardScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

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

    def _make_top_action_button(self, kind, text, accent=False):
        button = QPushButton(text)
        button.icon_kind = kind
        button.icon_role = "accent" if accent else "ghost"
        button.setObjectName("AccentBtn" if accent else "GhostBtn")
        button.setToolTip(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(30)
        return button

    def _refresh_brand_icon(self):
        icon_path = self.resource_path(os.path.join("assets", "icon.ico"))
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            self.brand_icon.setPixmap(
                pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )

    def refresh_icons(self, theme_name="light"):
        self.current_theme = theme_name
        palette = {
            "light": {"ghost": "#5F7087", "accent": "#FFFFFF"},
            "dark": {"ghost": "#DCE8F5", "accent": "#FFFFFF"},
        }["dark" if theme_name == "dark" else "light"]

        for button in (self.mount_all_btn, self.unmount_all_btn, self.settings_btn, self.add_btn):
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

    def set_bulk_buttons_enabled(self, can_mount_any: bool, can_unmount_any: bool):
        self.mount_all_btn.setEnabled(can_mount_any)
        self.unmount_all_btn.setEnabled(can_unmount_any)

    def show_empty_state(self):
        empty = QFrame()
        empty.setObjectName("EmptyState")

        layout = QVBoxLayout(empty)
        layout.setContentsMargins(20, 22, 20, 22)
        layout.setSpacing(8)

        title = QLabel(tr(self.lang, "no_drives"))
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

    def set_language(self, lang: str):
        self.lang = lang
        self.setWindowTitle(tr(self.lang, "app_title"))
        self._retranslate_top_bar()
        self._refresh_brand_icon()

    def _retranslate_top_bar(self):
        self.title_label.setText(tr(self.lang, "app_title"))
        self.mount_all_btn.setText(tr(self.lang, "mount_all"))
        self.mount_all_btn.setToolTip(tr(self.lang, "mount_all"))
        self.unmount_all_btn.setText(tr(self.lang, "unmount_all"))
        self.unmount_all_btn.setToolTip(tr(self.lang, "unmount_all"))
        self.settings_btn.setText(tr(self.lang, "settings_title"))
        self.settings_btn.setToolTip(tr(self.lang, "settings_title"))
        self.add_btn.setText(tr(self.lang, "add"))
        self.add_btn.setToolTip(tr(self.lang, "add"))

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

    def __init__(self, icon, lang="en", parent=None):
        super().__init__(icon, parent)
        self.lang = lang
        self.profile_states = []
        self.refresh_menu()
        self.activated.connect(self._on_activated)

    def set_profiles(self, profile_states):
        self.profile_states = profile_states
        self.refresh_menu()

    def refresh_menu(self):
        menu = QMenu()
        show = QAction(tr(self.lang, "open"), self)
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

        close = QAction(tr(self.lang, "exit"), self)
        close.triggered.connect(self.exit_requested.emit)
        menu.addAction(close)
        self.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_requested.emit()
