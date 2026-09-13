"""HTTP service that translates English text into six-dot Braille cells."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


HOST = "0.0.0.0"
PORT = 8080
TABLE = os.environ.get("BRAILLE_TABLE", "en-ueb-g1.ctb")
DISPLAY_TABLE = "unicode.dis"
MAX_REQUEST_BYTES = 64 * 1024
MAX_TEXT_CHARACTERS = 16_000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("braille")


class TranslationError(RuntimeError):
    """Raised when Liblouis cannot translate the supplied text."""


def normalize_ocr_text(text: str) -> str:
    """Turn OCR line breaks and other whitespace runs into one space."""
    return re.sub(r"\s+", " ", text).strip()


def translate_to_unicode_braille(text: str) -> str:
    """Translate a complete string with the configured Liblouis table."""
    if len(text) > MAX_TEXT_CHARACTERS:
        raise ValueError(
            f"text is too long ({len(text)} characters); "
            f"maximum is {MAX_TEXT_CHARACTERS}"
        )

    if not text:
        return ""

    try:
        completed = subprocess.run(
            [
                "lou_translate",
                "--forward",
                "--display-table",
                DISPLAY_TABLE,
                TABLE,
            ],
            input=text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=15,
        )
    except FileNotFoundError as error:
        raise TranslationError("lou_translate is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise TranslationError("Liblouis translation timed out") from error

    if completed.returncode != 0:
        detail = completed.stderr.strip() or "unknown Liblouis error"
        raise TranslationError(detail)

    return completed.stdout


def unicode_braille_to_cells(braille: str) -> list[int]:
    """Convert U+2800..U+283F characters to dot bits 1..6."""
    cells: list[int] = []

    for character in braille:
        codepoint = ord(character)
        if not 0x2800 <= codepoint <= 0x283F:
            raise TranslationError(
                "Liblouis returned a non-six-dot-Braille character: "
                f"U+{codepoint:04X}"
            )
        cells.append(codepoint - 0x2800)

    return cells


def cell_to_dots(cell: int) -> str:
    """Return conventional dot-number notation such as '125' or '0'."""
    dots = "".join(str(dot) for dot in range(1, 7) if cell & (1 << (dot - 1)))
    return dots or "0"


def translate(text: str, *, normalize_whitespace: bool = True) -> dict[str, Any]:
    """Return the normalized text, Unicode Braille, and MCU-friendly cells."""
    normalized = normalize_ocr_text(text) if normalize_whitespace else text

    if "\n" in normalized or "\r" in normalized:
        raise ValueError(
            "line breaks require normalize_whitespace=true because a six-bit "
            "Braille cell cannot encode a newline"
        )

    braille = translate_to_unicode_braille(normalized)
    cells = unicode_braille_to_cells(braille)

    return {
        "text": normalized,
        "braille": braille,
        "cells": cells,
        "dots": [cell_to_dots(cell) for cell in cells],
        "count": len(cells),
        "table": TABLE,
    }


class BrailleRequestHandler(BaseHTTPRequestHandler):
    server_version = "BrailleBrick/1.0"

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/health":
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        self._write_json(
            HTTPStatus.OK,
            {"status": "ok", "table": TABLE, "display_table": DISPLAY_TABLE},
        )

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/translate":
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0:
                raise ValueError("request body is empty")
            if content_length > MAX_REQUEST_BYTES:
                self._write_json(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    {"error": f"request exceeds {MAX_REQUEST_BYTES} bytes"},
                )
                return

            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")

            text = payload.get("text")
            if not isinstance(text, str):
                raise ValueError("'text' must be a string")

            normalize_whitespace = payload.get("normalize_whitespace", True)
            if not isinstance(normalize_whitespace, bool):
                raise ValueError("'normalize_whitespace' must be a boolean")

            self._write_json(
                HTTPStatus.OK,
                translate(text, normalize_whitespace=normalize_whitespace),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except TranslationError as error:
            logger.exception("Translation failed")
            self._write_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": str(error)},
            )

    def log_message(self, message_format: str, *args: Any) -> None:
        logger.info("%s - %s", self.address_string(), message_format % args)


def main() -> None:
    probe = unicode_braille_to_cells(translate_to_unicode_braille("a"))
    if probe != [1]:
        raise TranslationError(
            f"unexpected startup probe result for {TABLE}: {probe!r}"
        )

    server = ThreadingHTTPServer((HOST, PORT), BrailleRequestHandler)
    logger.info("Braille Brick listening on %s:%d using %s", HOST, PORT, TABLE)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()