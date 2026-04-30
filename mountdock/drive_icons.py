from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap


ICON_KEYS = [
    "auto",
    "google_drive",
    "smb",
    "webdav",
    "onedrive",
    "dropbox",
    "s3",
    "generic_cloud",
    "generic_folder",
]


def infer_drive_icon_key(remote_type: str | None, remote_name: str | None = None) -> str:
    remote_type = (remote_type or "").strip().lower()
    remote_name = (remote_name or "").strip().lower()

    mapping = {
        "drive": "google_drive",
        "google cloud storage": "generic_cloud",
        "smb": "smb",
        "webdav": "webdav",
        "onedrive": "onedrive",
        "dropbox": "dropbox",
        "s3": "s3",
        "b2": "generic_cloud",
        "swift": "generic_cloud",
        "ftp": "smb",
        "sftp": "smb",
        "nfs": "smb",
    }
    if remote_type in mapping:
        return mapping[remote_type]

    if "google" in remote_name:
        return "google_drive"
    if "smb" in remote_name:
        return "smb"
    if "webdav" in remote_name or "dav" in remote_name:
        return "webdav"
    if "onedrive" in remote_name:
        return "onedrive"
    if "dropbox" in remote_name:
        return "dropbox"
    if "s3" in remote_name:
        return "s3"
    if "cloud" in remote_name:
        return "generic_cloud"
    return "generic_folder"


def resolve_drive_icon_key(profile_or_key, remote_type: str | None = None, remote_name: str | None = None) -> str:
    if isinstance(profile_or_key, dict):
        selected = (profile_or_key.get("icon") or "auto").strip() or "auto"
        remote_type = profile_or_key.get("remote_type", remote_type)
        remote_name = profile_or_key.get("remote", remote_name)
    else:
        selected = str(profile_or_key or "auto").strip() or "auto"

    if selected == "auto":
        return infer_drive_icon_key(remote_type, remote_name)
    return selected if selected in ICON_KEYS else "generic_folder"


def _color(value: str) -> QColor:
    return QColor(value)


def _draw_drive_base(painter: QPainter, size: int, mounted: bool):
    body = QRectF(size * 0.12, size * 0.28, size * 0.76, size * 0.44)
    top = QRectF(size * 0.16, size * 0.20, size * 0.68, size * 0.18)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_color("#D9E3F0" if mounted else "#D7DEE8"))
    painter.drawRoundedRect(body, size * 0.08, size * 0.08)

    painter.setBrush(_color("#F7FBFF" if mounted else "#EDF3F8"))
    painter.drawRoundedRect(top, size * 0.06, size * 0.06)

    light_color = "#27C26C" if mounted else "#8FA2B8"
    painter.setBrush(_color(light_color))
    painter.drawEllipse(QRectF(size * 0.70, size * 0.53, size * 0.07, size * 0.07))

    painter.setBrush(_color("#B9C8D8"))
    painter.drawRoundedRect(QRectF(size * 0.23, size * 0.53, size * 0.38, size * 0.05), size * 0.02, size * 0.02)


def _draw_badge_background(painter: QPainter, x: float, y: float, size: float, color: str):
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_color(color))
    painter.drawEllipse(QRectF(x, y, size, size))


def _draw_badge_text(painter: QPainter, x: float, y: float, size: float, text: str, color: str = "#FFFFFF"):
    font = QFont("Segoe UI", max(7, int(size * 0.34)))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(_color(color))
    painter.drawText(QRectF(x, y, size, size), int(Qt.AlignmentFlag.AlignCenter), text)


def _draw_folder_badge(painter: QPainter, x: float, y: float, size: float):
    path = QPainterPath()
    path.moveTo(x + size * 0.12, y + size * 0.38)
    path.lineTo(x + size * 0.42, y + size * 0.38)
    path.lineTo(x + size * 0.50, y + size * 0.24)
    path.lineTo(x + size * 0.86, y + size * 0.24)
    path.lineTo(x + size * 0.80, y + size * 0.80)
    path.lineTo(x + size * 0.14, y + size * 0.80)
    path.closeSubpath()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_color("#F4C247"))
    painter.drawPath(path)
    painter.setBrush(_color("#F8D36B"))
    painter.drawRect(QRectF(x + size * 0.16, y + size * 0.32, size * 0.60, size * 0.16))


def _draw_google_drive_badge(painter: QPainter, x: float, y: float, size: float):
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    cx = x + size * 0.5
    top = QPointF(cx, y + size * 0.12)
    left = QPointF(x + size * 0.18, y + size * 0.78)
    right = QPointF(x + size * 0.82, y + size * 0.78)
    inner = QPointF(cx, y + size * 0.42)
    for color, points in [
        ("#0F9D58", [left, inner, right]),
        ("#4285F4", [top, inner, left]),
        ("#F4B400", [top, right, inner]),
    ]:
        path = QPainterPath()
        path.moveTo(points[0])
        path.lineTo(points[1])
        path.lineTo(points[2])
        path.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_color(color))
        painter.drawPath(path)


def _draw_cloud_badge(painter: QPainter, x: float, y: float, size: float, color: str, text: str | None = None):
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_color(color))
    painter.drawEllipse(QRectF(x + size * 0.22, y + size * 0.34, size * 0.22, size * 0.22))
    painter.drawEllipse(QRectF(x + size * 0.36, y + size * 0.20, size * 0.28, size * 0.28))
    painter.drawEllipse(QRectF(x + size * 0.56, y + size * 0.34, size * 0.20, size * 0.20))
    painter.drawRoundedRect(QRectF(x + size * 0.26, y + size * 0.42, size * 0.46, size * 0.18), size * 0.08, size * 0.08)
    if text:
        _draw_badge_text(painter, x, y + size * 0.02, size, text)


def _draw_server_badge(painter: QPainter, x: float, y: float, size: float, color: str):
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_color(color))
    painter.drawRoundedRect(QRectF(x + size * 0.18, y + size * 0.20, size * 0.64, size * 0.22), size * 0.07, size * 0.07)
    painter.drawRoundedRect(QRectF(x + size * 0.18, y + size * 0.48, size * 0.64, size * 0.22), size * 0.07, size * 0.07)
    painter.setBrush(_color("#FFFFFF"))
    painter.drawEllipse(QRectF(x + size * 0.28, y + size * 0.28, size * 0.06, size * 0.06))
    painter.drawEllipse(QRectF(x + size * 0.28, y + size * 0.56, size * 0.06, size * 0.06))


def _draw_globe_badge(painter: QPainter, x: float, y: float, size: float, color: str):
    pen = QPen(_color(color), max(1.6, size * 0.08))
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QRectF(x + size * 0.18, y + size * 0.18, size * 0.64, size * 0.64))
    painter.drawArc(QRectF(x + size * 0.34, y + size * 0.18, size * 0.32, size * 0.64), 90 * 16, 180 * 16)
    painter.drawArc(QRectF(x + size * 0.34, y + size * 0.18, size * 0.32, size * 0.64), 270 * 16, 180 * 16)
    painter.drawLine(QPointF(x + size * 0.22, y + size * 0.50), QPointF(x + size * 0.78, y + size * 0.50))


def _draw_dropbox_badge(painter: QPainter, x: float, y: float, size: float):
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_color("#0061FF"))
    diamonds = [
        [QPointF(x + size * 0.32, y + size * 0.26), QPointF(x + size * 0.46, y + size * 0.16), QPointF(x + size * 0.60, y + size * 0.26), QPointF(x + size * 0.46, y + size * 0.36)],
        [QPointF(x + size * 0.14, y + size * 0.42), QPointF(x + size * 0.28, y + size * 0.32), QPointF(x + size * 0.42, y + size * 0.42), QPointF(x + size * 0.28, y + size * 0.52)],
        [QPointF(x + size * 0.50, y + size * 0.42), QPointF(x + size * 0.64, y + size * 0.32), QPointF(x + size * 0.78, y + size * 0.42), QPointF(x + size * 0.64, y + size * 0.52)],
        [QPointF(x + size * 0.32, y + size * 0.58), QPointF(x + size * 0.46, y + size * 0.48), QPointF(x + size * 0.60, y + size * 0.58), QPointF(x + size * 0.46, y + size * 0.68)],
    ]
    for points in diamonds:
        path = QPainterPath()
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)
        path.closeSubpath()
        painter.drawPath(path)


def _draw_cube_badge(painter: QPainter, x: float, y: float, size: float, color: str):
    pen = QPen(_color(color), max(1.4, size * 0.06))
    painter.setPen(pen)
    painter.setBrush(_color("#FFF5EA"))
    painter.drawRect(QRectF(x + size * 0.26, y + size * 0.24, size * 0.40, size * 0.40))
    painter.drawLine(QPointF(x + size * 0.26, y + size * 0.24), QPointF(x + size * 0.44, y + size * 0.10))
    painter.drawLine(QPointF(x + size * 0.66, y + size * 0.24), QPointF(x + size * 0.84, y + size * 0.10))
    painter.drawLine(QPointF(x + size * 0.44, y + size * 0.10), QPointF(x + size * 0.84, y + size * 0.10))
    painter.drawLine(QPointF(x + size * 0.66, y + size * 0.24), QPointF(x + size * 0.84, y + size * 0.10))


def _draw_provider_badge(painter: QPainter, key: str, size: int):
    badge_size = size * 0.46
    x = size * 0.50
    y = size * 0.02

    if key == "google_drive":
        _draw_google_drive_badge(painter, x, y, badge_size)
    elif key == "smb":
        _draw_badge_background(painter, x, y, badge_size, "#3B82F6")
        _draw_server_badge(painter, x, y, badge_size, "#FFFFFF")
    elif key == "webdav":
        _draw_badge_background(painter, x, y, badge_size, "#14B8A6")
        _draw_globe_badge(painter, x, y, badge_size, "#FFFFFF")
    elif key == "onedrive":
        _draw_badge_background(painter, x, y, badge_size, "#2563EB")
        _draw_cloud_badge(painter, x, y, badge_size, "#FFFFFF")
    elif key == "dropbox":
        _draw_badge_background(painter, x, y, badge_size, "#EAF2FF")
        _draw_dropbox_badge(painter, x, y, badge_size)
    elif key == "s3":
        _draw_badge_background(painter, x, y, badge_size, "#FFF1E5")
        _draw_cube_badge(painter, x, y, badge_size, "#F97316")
    elif key == "generic_cloud":
        _draw_badge_background(painter, x, y, badge_size, "#64748B")
        _draw_cloud_badge(painter, x, y, badge_size, "#FFFFFF")
    elif key == "generic_folder":
        _draw_badge_background(painter, x, y, badge_size, "#FFF4CC")
        _draw_folder_badge(painter, x, y, badge_size)
    else:
        _draw_badge_background(painter, x, y, badge_size, "#94A3B8")
        _draw_badge_text(painter, x, y, badge_size, "M")


def build_drive_icon(
    profile_or_key,
    size: int = 32,
    mounted: bool = False,
    remote_type: str | None = None,
    remote_name: str | None = None,
) -> QIcon:
    icon_key = resolve_drive_icon_key(profile_or_key, remote_type=remote_type, remote_name=remote_name)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _draw_drive_base(painter, size, mounted=mounted)
    _draw_provider_badge(painter, icon_key, size)
    painter.end()
    return QIcon(pixmap)


def ensure_drive_icon_file(
    app_dir: str | Path,
    profile_or_key,
    remote_type: str | None = None,
    remote_name: str | None = None,
) -> str:
    icon_key = resolve_drive_icon_key(profile_or_key, remote_type=remote_type, remote_name=remote_name)
    target_dir = Path(app_dir).resolve() / ".mountdock" / "drive_icons"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{icon_key}.ico"
    if target_path.exists() and target_path.stat().st_size > 0:
        return str(target_path)

    icon = build_drive_icon(icon_key, size=256, mounted=True, remote_type=remote_type, remote_name=remote_name)
    pixmap = icon.pixmap(256, 256)
    if not pixmap.isNull() and pixmap.save(str(target_path), "ICO"):
        return str(target_path)
    return ""
