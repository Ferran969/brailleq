from __future__ import annotations

import importlib.util
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SERVER_PATH = (
    Path(__file__).parents[1] / "bricks" / "v4l2_capture" / "server.py"
)
SPEC = importlib.util.spec_from_file_location("v4l2_capture_server", SERVER_PATH)
assert SPEC is not None and SPEC.loader is not None
server = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = server
SPEC.loader.exec_module(server)


class CameraDeviceValidationTests(unittest.TestCase):
    @patch.object(server.subprocess, "run")
    @patch.object(server.os, "stat")
    def test_accepts_capture_device_with_mjpeg(self, stat_mock, run_mock) -> None:
        stat_mock.return_value = SimpleNamespace(st_mode=stat.S_IFCHR)
        run_mock.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="[0]: 'MJPG' (Motion-JPEG)",
            stderr="",
        )

        server._validate_camera_device()

        run_mock.assert_called_once_with(
            ["v4l2-ctl", "-d", server.DEVICE, "--list-formats-ext"],
            capture_output=True,
            text=True,
            timeout=10.0,
        )

    @patch.object(server.os, "stat", side_effect=FileNotFoundError)
    def test_rejects_missing_device(self, _stat_mock) -> None:
        with self.assertRaisesRegex(RuntimeError, "does not exist"):
            server._validate_camera_device()

    @patch.object(server.subprocess, "run")
    @patch.object(server.os, "stat")
    def test_rejects_non_capture_node(self, stat_mock, run_mock) -> None:
        stat_mock.return_value = SimpleNamespace(st_mode=stat.S_IFCHR)
        run_mock.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="not a video capture device",
        )

        with self.assertRaisesRegex(RuntimeError, "not a usable video capture node"):
            server._validate_camera_device()

    @patch.object(server.subprocess, "run")
    @patch.object(server.os, "stat")
    def test_rejects_device_without_mjpeg(self, stat_mock, run_mock) -> None:
        stat_mock.return_value = SimpleNamespace(st_mode=stat.S_IFCHR)
        run_mock.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="[0]: 'YUYV' (YUYV 4:2:2)",
            stderr="",
        )

        with self.assertRaisesRegex(RuntimeError, "required MJPEG format"):
            server._validate_camera_device()


class CaptureArchiveTests(unittest.TestCase):
    def test_save_capture_archives_jpeg_bytes(self) -> None:
        image = b"\xff\xd8example-jpeg"

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(server, "CAPTURE_ARCHIVE_DIR", Path(directory)):
                server._save_capture(image)

            captures = list(Path(directory).glob("capture_*.jpg"))
            self.assertEqual(len(captures), 1)
            self.assertEqual(captures[0].read_bytes(), image)


if __name__ == "__main__":
    unittest.main()
