"""Client for the Braille Translator Brick."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class BrailleTranslation:
    text: str
    braille: str
    cells: list[int]
    dots: list[str]
    table: str


class BrailleClientError(RuntimeError):
    """Raised when the Braille Brick cannot satisfy a request."""


class BrailleClient:
    def __init__(self, base_url: str = "http://braille:8080", timeout: float = 20.0):
        self._translate_url = f"{base_url.rstrip('/')}/translate"
        self._timeout = timeout

    def translate(
        self,
        text: str,
        *,
        normalize_whitespace: bool = True,
    ) -> BrailleTranslation:
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
                result: dict[str, Any] = json.load(response)
        except HTTPError as error:
            try:
                detail = json.load(error).get("error", str(error))
            except Exception:
                detail = str(error)
            raise BrailleClientError(detail) from error
        except (URLError, TimeoutError) as error:
            raise BrailleClientError(f"Braille Brick is unavailable: {error}") from error

        cells = result.get("cells")
        if not isinstance(cells, list) or not all(
            isinstance(cell, int) and 0 <= cell <= 0x3F for cell in cells
        ):
            raise BrailleClientError("Braille Brick returned invalid cells")

        return BrailleTranslation(
            text=result["text"],
            braille=result["braille"],
            cells=cells,
            dots=result["dots"],
            table=result["table"],
        )

