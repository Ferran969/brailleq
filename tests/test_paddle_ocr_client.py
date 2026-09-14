from __future__ import annotations

import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


CLIENT_PATH = Path(__file__).parents[1] / "bricks" / "paddle_ocr" / "__init__.py"
SPEC = importlib.util.spec_from_file_location("paddle_ocr_client", CLIENT_PATH)
assert SPEC is not None and SPEC.loader is not None
client = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = client
SPEC.loader.exec_module(client)


class Response:
    ok = True
    status_code = 200
    text = ""

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def json(self) -> dict:
        return self.payload


class RecognizeOutputTests(unittest.TestCase):
    @patch.object(client, "wait_until_ready")
    @patch.object(client.requests, "post")
    def test_prints_detected_fragments_and_confidence(
        self,
        post_mock,
        _ready_mock,
    ) -> None:
        post_mock.return_value = Response({
            "text": "Hello world",
            "text_sharpness": 725.5,
            "fragments": [
                {"text": "Hello world", "confidence": 0.984},
            ],
        })

        output = io.StringIO()
        with redirect_stdout(output):
            result = client.recognize(b"jpeg")

        self.assertEqual(result, ("Hello world", 725.5))
        self.assertIn("[OCR] Texto detectado:", output.getvalue())
        self.assertIn('[OCR] 98.4% | "Hello world"', output.getvalue())

    @patch.object(client, "wait_until_ready")
    @patch.object(client.requests, "post")
    def test_reports_when_no_text_is_detected(
        self,
        post_mock,
        _ready_mock,
    ) -> None:
        post_mock.return_value = Response({
            "text": "",
            "text_sharpness": None,
            "fragments": [],
        })

        output = io.StringIO()
        with redirect_stdout(output):
            result = client.recognize(b"jpeg")

        self.assertEqual(result, ("", None))
        self.assertIn("[OCR] No se ha detectado texto.", output.getvalue())


if __name__ == "__main__":
    unittest.main()
