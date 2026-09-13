from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HOST = "0.0.0.0"
PORT = 8000
DEVICE = os.getenv("CAMERA_DEVICE", "/dev/brailleq-camera")
DEBUG_CAPTURE_DIR = Path(os.getenv("DEBUG_CAPTURE_DIR", "/captures"))

# One process should own/configure the camera at a time.
_camera_lock = threading.Lock()


def _validate_camera_device() -> None:
    """Fail early unless the mapped device is a capture node with MJPEG."""
    try:
        device_stat = os.stat(DEVICE)
    except FileNotFoundError as error:
        raise RuntimeError(
            f"Camera device {DEVICE} does not exist inside the container"
        ) from error
    except OSError as error:
        raise RuntimeError(
            f"Could not inspect camera device {DEVICE}: {error}"
        ) from error

    if not stat.S_ISCHR(device_stat.st_mode):
        raise RuntimeError(f"Camera device {DEVICE} is not a character device")

    try:
        result = subprocess.run(
            ["v4l2-ctl", "-d", DEVICE, "--list-formats-ext"],
            capture_output=True,
            text=True,
            timeout=10.0,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"Timed out while checking camera device {DEVICE}"
        ) from error

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"Camera device {DEVICE} is not a usable video capture node: "
            f"{detail or 'v4l2-ctl failed'}"
        )

    if "MJPG" not in result.stdout:
        raise RuntimeError(
            f"Camera device {DEVICE} does not advertise the required MJPEG format"
        )


def _save_debug_capture(image: bytes) -> None:
    """Temporarily archive every successful capture in the shared volume."""
    try:
        DEBUG_CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        capture_path = DEBUG_CAPTURE_DIR / f"capture_{timestamp}.jpg"
        capture_path.write_bytes(image)
        print(
            f"[v4l2_capture] debug image saved to {capture_path}",
            flush=True,
        )
    except OSError as error:
        # A debug-copy failure must not prevent OCR from receiving the image.
        print(
            f"[v4l2_capture] could not save debug image: {error}",
            flush=True,
        )


def _capture(payload: dict) -> bytes:
    focus_seconds = float(payload.get("focus_seconds", 5.0))
    width = int(payload.get("width", 1920))
    height = int(payload.get("height", 1080))
    fps = int(payload.get("fps", 30))
    autofocus = bool(payload.get("autofocus", True))

    if not 0.0 <= focus_seconds <= 60.0:
        raise ValueError("focus_seconds must be between 0 and 60")
    if not 1 <= width <= 8192 or not 1 <= height <= 8192:
        raise ValueError("width/height are out of range")
    if not 1 <= fps <= 240:
        raise ValueError("fps must be between 1 and 240")

    # This reproduces --stream-skip=150 when focus_seconds=5 and fps=30.
    skip_frames = round(focus_seconds * fps)

    fd, output_path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)

    try:
        cmd = [
            "v4l2-ctl",
            "-d",
            DEVICE,
            f"--set-fmt-video=width={width},height={height},pixelformat=MJPG",
            f"--set-parm={fps}",
        ]

        if autofocus:
            cmd.append("--set-ctrl=focus_automatic_continuous=1")

        cmd.extend(
            [
                "--stream-mmap=4",
                f"--stream-skip={skip_frames}",
                "--stream-count=1",
                f"--stream-to={output_path}",
            ]
        )

        with _camera_lock:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=focus_seconds + 20.0,
            )

        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(
                f"v4l2-ctl failed with exit code {result.returncode}: {detail}"
            )

        with open(output_path, "rb") as image_file:
            image = image_file.read()

        if not image:
            raise RuntimeError("v4l2-ctl completed but produced an empty image")

        # MJPG frames should be JPEG images.
        if not image.startswith(b"\xff\xd8"):
            raise RuntimeError(
                "Captured data does not look like a JPEG frame "
                "(missing JPEG SOI marker)"
            )

        # TEMPORARY DEBUG CODE: remove after camera diagnostics are complete.
        _save_debug_capture(image)
        return image
    finally:
        try:
            os.unlink(output_path)
        except FileNotFoundError:
            pass


class Handler(BaseHTTPRequestHandler):
    server_version = "V4L2Capture/1.0"

    def _send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/health":
            self._send_json(404, {"error": "not found"})
            return

        self._send_json(
            200,
            {
                "ok": True,
                "device": DEVICE,
            },
        )

    def do_POST(self) -> None:
        if self.path != "/capture":
            self._send_json(404, {"error": "not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length > 64 * 1024:
                raise ValueError("request body is too large")

            body = self.rfile.read(content_length)
            payload = json.loads(body or b"{}")

            image = _capture(payload)

            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(image)))
            self.end_headers()
            self.wfile.write(image)
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
        except subprocess.TimeoutExpired:
            self._send_json(504, {"error": "v4l2-ctl timed out"})
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})

    def log_message(self, fmt: str, *args) -> None:
        print(f"[v4l2_capture] {self.address_string()} - {fmt % args}", flush=True)


if __name__ == "__main__":
    _validate_camera_device()
    print(
        f"[v4l2_capture] serving on {HOST}:{PORT}, camera={DEVICE}",
        flush=True,
    )
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
