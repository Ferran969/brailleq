"""Synchronous Python client for the internal V4L2 Capture service."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path


_BASE_URL = "http://v4l2_capture:8000"


def _post_json(path: str, payload: dict, timeout: float) -> bytes:
    """POST JSON and return response bytes, retrying startup connection errors."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{_BASE_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    # The service container can take a short moment to become reachable when
    # the App starts, so retry connection failures briefly.
    last_error: Exception | None = None
    for _ in range(20):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"V4L2 capture service returned HTTP {exc.code}: {detail}"
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            time.sleep(0.25)

    raise RuntimeError(
        f"Could not reach V4L2 capture service at {_BASE_URL}"
    ) from last_error


def capture_image(
    focus_seconds: float = 5.0,
    *,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    autofocus: bool = True,
) -> bytes:
    """Capture one MJPEG frame and return the encoded JPEG bytes."""
    if focus_seconds < 0:
        raise ValueError("focus_seconds must be >= 0")
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be > 0")
    if fps <= 0:
        raise ValueError("fps must be > 0")

    return _post_json(
        "/capture",
        {
            "focus_seconds": float(focus_seconds),
            "width": int(width),
            "height": int(height),
            "fps": int(fps),
            "autofocus": bool(autofocus),
        },
        timeout=max(15.0, float(focus_seconds) + 10.0),
    )


def capture_to_file(
    path: str | Path,
    focus_seconds: float = 5.0,
    *,
    width: int = 1920,    
    height: int = 1080,
    fps: int = 30,
    autofocus: bool = True,
) -> Path:
    """Capture one frame, write the encoded JPEG bytes, and return its path."""
    output = Path(path)
    output.write_bytes(
        capture_image(
            focus_seconds,
            width=width,
            height=height,
            fps=fps,
            autofocus=autofocus,
        )
    )
    return output
