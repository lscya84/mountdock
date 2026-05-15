import subprocess
import sys
import types
import unittest
from unittest.mock import Mock, patch

psutil_stub = types.SimpleNamespace(disk_partitions=lambda: [])
qtcore_stub = types.ModuleType("PyQt6.QtCore")
subprocess_stub = types.SimpleNamespace(
    STARTUPINFO=lambda: types.SimpleNamespace(dwFlags=0),
    STARTF_USESHOWWINDOW=1,
    CREATE_NO_WINDOW=0x08000000,
)


class _FakeQThread:
    def __init__(self, *args, **kwargs):
        pass

    def wait(self):
        return None

    def msleep(self, _milliseconds):
        return None


def _fake_signal(*_args, **_kwargs):
    return Mock()


qtcore_stub.QThread = _FakeQThread
qtcore_stub.pyqtSignal = _fake_signal
pyqt6_stub = types.ModuleType("PyQt6")
pyqt6_stub.QtCore = qtcore_stub

sys.modules.setdefault("psutil", psutil_stub)
sys.modules.setdefault("PyQt6", pyqt6_stub)
sys.modules.setdefault("PyQt6.QtCore", qtcore_stub)

from mountdock.watcher import (
    ACCESS_PROBE_TIMEOUT_SECONDS,
    DRIVE_UNKNOWN,
    LDriveWatcher,
)


class WatcherDriveReadyTests(unittest.TestCase):
    def setUp(self):
        self.engine = Mock()
        self.watcher = LDriveWatcher(self.engine, "remote", "X", "full")

    def test_check_drive_ready_requires_probe_for_known_drive(self):
        with patch.object(self.watcher, "_check_drive_exists", return_value=True), \
            patch.object(self.watcher, "_get_drive_type", return_value=3), \
            patch.object(self.watcher, "_probe_drive_access", return_value=False):
            self.assertFalse(self.watcher._check_drive_ready())

    def test_check_drive_ready_uses_isdir_for_unknown_drive_type(self):
        with patch.object(self.watcher, "_check_drive_exists", return_value=True), \
            patch.object(self.watcher, "_get_drive_type", return_value=DRIVE_UNKNOWN), \
            patch("mountdock.watcher.os.path.isdir", return_value=True):
            self.assertTrue(self.watcher._check_drive_ready())

    def test_probe_drive_access_returns_false_on_timeout(self):
        with patch("mountdock.watcher.os.name", "nt"), \
            patch("mountdock.watcher.subprocess.STARTUPINFO", subprocess_stub.STARTUPINFO, create=True), \
            patch("mountdock.watcher.subprocess.STARTF_USESHOWWINDOW", subprocess_stub.STARTF_USESHOWWINDOW, create=True), \
            patch("mountdock.watcher.subprocess.CREATE_NO_WINDOW", subprocess_stub.CREATE_NO_WINDOW, create=True), \
            patch(
                "mountdock.watcher.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="dir", timeout=ACCESS_PROBE_TIMEOUT_SECONDS),
            ):
            self.assertFalse(self.watcher._probe_drive_access())

    def test_probe_drive_access_runs_directory_listing_on_windows(self):
        with patch("mountdock.watcher.os.name", "nt"), \
            patch("mountdock.watcher.subprocess.STARTUPINFO", subprocess_stub.STARTUPINFO, create=True), \
            patch("mountdock.watcher.subprocess.STARTF_USESHOWWINDOW", subprocess_stub.STARTF_USESHOWWINDOW, create=True), \
            patch("mountdock.watcher.subprocess.CREATE_NO_WINDOW", subprocess_stub.CREATE_NO_WINDOW, create=True), \
            patch("mountdock.watcher.subprocess.run") as run_mock:
            self.assertTrue(self.watcher._probe_drive_access())

        kwargs = run_mock.call_args.kwargs
        self.assertEqual(run_mock.call_args.args[0], ["cmd", "/d", "/c", f"dir {self.watcher.drive_path} >nul 2>nul"])
        self.assertTrue(kwargs["capture_output"])
        self.assertTrue(kwargs["text"])
        self.assertEqual(kwargs["timeout"], ACCESS_PROBE_TIMEOUT_SECONDS)
        self.assertTrue(kwargs["check"])
        self.assertEqual(kwargs["creationflags"], subprocess_stub.CREATE_NO_WINDOW)
        self.assertEqual(kwargs["startupinfo"].dwFlags, subprocess_stub.STARTF_USESHOWWINDOW)


if __name__ == "__main__":
    unittest.main()
