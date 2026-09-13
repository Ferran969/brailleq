"""Client for the Braille Translator Brick."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "http://braille:8080"


@dataclass(frozen=True)
class BrailleTranslation:
    text: str
    braille: str
    cells: list[int]
    dots: list[str]
    table: str


class BrailleClientError(RuntimeError):
    """Raised when the Braille Brick cannot satisfy a request."""


def _dots_for_cell(cell: int) -> str:
    dots = "".join(
        str(dot) for dot in range(1, 7) if cell & (1 << (dot - 1))
    )
    return dots or "0"


def _translation_from_payload(payload: Any) -> BrailleTranslation:
    if not isinstance(payload, dict):
        raise BrailleClientError(
            "Braille Brick returned a JSON value that is not an object"
        )

    text = payload.get("text")
    braille = payload.get("braille")
    cells = payload.get("cells")
    dots = payload.get("dots")
    table = payload.get("table")

    if not isinstance(text, str):
        raise BrailleClientError(
            "Braille Brick returned an invalid or missing 'text' field"
        )
    if not isinstance(braille, str):
        raise BrailleClientError(
            "Braille Brick returned an invalid or missing 'braille' field"
        )
    if not isinstance(cells, list) or not all(
        type(cell) is int and 0 <= cell <= 0x3F for cell in cells
    ):
        raise BrailleClientError(
            "Braille Brick returned an invalid or missing 'cells' field"
        )
    if not isinstance(dots, list) or not all(
        isinstance(dot_notation, str) for dot_notation in dots
    ):
        raise BrailleClientError(
            "Braille Brick returned an invalid or missing 'dots' field"
        )
    if not isinstance(table, str):
        raise BrailleClientError(
            "Braille Brick returned an invalid or missing 'table' field"
        )

    braille_cells = []
    for character in braille:
        codepoint = ord(character)
        if not 0x2800 <= codepoint <= 0x283F:
            raise BrailleClientError(
                "Braille Brick returned a non-six-dot character in 'braille'"
            )
        braille_cells.append(codepoint - 0x2800)

    if braille_cells != cells:
        raise BrailleClientError(
            "Braille Brick returned inconsistent 'braille' and 'cells' fields"
        )

    expected_dots = [_dots_for_cell(cell) for cell in cells]
    if dots != expected_dots:
        raise BrailleClientError(
            "Braille Brick returned inconsistent 'cells' and 'dots' fields"
        )

    if "count" in payload:
        count = payload["count"]
        if type(count) is not int or count != len(cells):
            raise BrailleClientError(
                "Braille Brick returned an invalid 'count' field"
            )

    return BrailleTranslation(
        text=text,
        braille=braille,
        cells=cells,
        dots=dots,
        table=table,
    )


class BrailleClient:
    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = 20.0,
        ready_timeout: float = 30.0,
    ):
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if ready_timeout <= 0:
            raise ValueError("ready_timeout must be greater than zero")

        base_url = base_url.rstrip("/")
        self._health_url = f"{base_url}/health"
        self._translate_url = f"{base_url}/translate"
        self._timeout = timeout
        self._ready_timeout = ready_timeout

    def wait_until_ready(self) -> None:
        """Wait until the service health endpoint reports that it is ready."""
        deadline = time.monotonic() + self._ready_timeout
        last_error: Exception | None = None

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            request = Request(
                self._health_url,
                headers={"Accept": "application/json"},
                method="GET",
            )

            try:
                with urlopen(request, timeout=min(2.0, remaining)) as response:
                    health: Any = json.load(response)

                if isinstance(health, dict) and health.get("status") == "ok":
                    return

                last_error = BrailleClientError(
                    f"unexpected health response: {health!r}"
                )
            except (
                HTTPError,
                URLError,
                TimeoutError,
                UnicodeDecodeError,
                json.JSONDecodeError,
            ) as error:
                last_error = error

            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(0.25, remaining))

        detail = str(last_error) if last_error is not None else "no response"
        raise BrailleClientError(
            "Braille Brick did not become ready within "
            f"{self._ready_timeout:g}s. Last error: {detail}"
        ) from last_error

    def translate(
        self,
        text: str,
        *,
        normalize_whitespace: bool = True,
    ) -> BrailleTranslation:
        self.wait_until_ready()

        payload = json.dumps(
            {"text": text, "normalize_whitespace": normalize_whitespace}
        ).encode("utf-8")
        request = Request(
            self._translate_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self._timeout) as response:
                try:
                    result: Any = json.load(response)
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise BrailleClientError(
                        "Braille Brick returned invalid JSON"
                    ) from error
        except HTTPError as error:
            try:
                error_payload: Any = json.load(error)
            except (UnicodeDecodeError, json.JSONDecodeError):
                detail = str(error)
            else:
                error_detail = (
                    error_payload.get("error")
                    if isinstance(error_payload, dict)
                    else None
                )
                detail = error_detail if isinstance(error_detail, str) else str(error)
            raise BrailleClientError(detail) from error
        except (URLError, TimeoutError) as error:
            raise BrailleClientError(
                f"Braille Brick is unavailable: {error}"
            ) from error

        return _translation_from_payload(result)
