from __future__ import annotations

import importlib.util
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.serving import make_server


PROJECT_ROOT = Path(__file__).parents[1]

SERVER_PATH = PROJECT_ROOT / "bricks" / "braille" / "server.py"
SERVER_SPEC = importlib.util.spec_from_file_location(
    "braille_server", SERVER_PATH
)
assert SERVER_SPEC is not None and SERVER_SPEC.loader is not None
server = importlib.util.module_from_spec(SERVER_SPEC)
sys.modules[SERVER_SPEC.name] = server
SERVER_SPEC.loader.exec_module(server)

CLIENT_PATH = PROJECT_ROOT / "bricks" / "braille" / "__init__.py"
CLIENT_SPEC = importlib.util.spec_from_file_location(
    "braille_client", CLIENT_PATH
)
assert CLIENT_SPEC is not None and CLIENT_SPEC.loader is not None
client_module = importlib.util.module_from_spec(CLIENT_SPEC)
sys.modules[CLIENT_SPEC.name] = client_module
CLIENT_SPEC.loader.exec_module(client_module)


class BrailleServiceTests(unittest.TestCase):
    def test_unicode_braille_to_cells(self) -> None:
        self.assertEqual(
            server.unicode_braille_to_cells("⠠⠓⠑⠇⠇⠕⠀⠼⠁⠃⠉"),
            [32, 19, 17, 7, 7, 21, 0, 60, 1, 3, 9],
        )

    def test_cell_to_dots(self) -> None:
        self.assertEqual(server.cell_to_dots(0), "0")
        self.assertEqual(server.cell_to_dots(19), "125")
        self.assertEqual(server.cell_to_dots(60), "3456")

    def test_normalizes_ocr_whitespace(self) -> None:
        self.assertEqual(
            server.normalize_ocr_text("  Hello\n\tworld  "),
            "Hello world",
        )

    def test_rejects_non_braille_output(self) -> None:
        with self.assertRaises(server.TranslationError):
            server.unicode_braille_to_cells("a")

    @patch.object(server.subprocess, "run")
    def test_complete_translation(self, run_mock) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="⠠⠓⠊", stderr=""
        )

        result = server.translate("Hi")

        self.assertEqual(result["braille"], "⠠⠓⠊")
        self.assertEqual(result["cells"], [32, 19, 10])
        self.assertEqual(result["dots"], ["6", "125", "24"])
        run_mock.assert_called_once()

    def test_health_endpoint(self) -> None:
        response = server.app.test_client().get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_translate_rejects_invalid_text(self) -> None:
        response = server.app.test_client().post(
            "/translate",
            json={"text": 123},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "'text' must be a string")

    def test_translate_rejects_malformed_json(self) -> None:
        response = server.app.test_client().post(
            "/translate",
            data="{",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("request", response.get_json()["error"].lower())

    def test_unknown_endpoint_returns_json(self) -> None:
        response = server.app.test_client().get("/missing")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"error": "not found"})

    def test_http_service_and_client(self) -> None:
        expected = {
            "text": "Hi",
            "braille": "⠠⠓⠊",
            "cells": [32, 19, 10],
            "dots": ["6", "125", "24"],
            "count": 3,
            "table": "en-ueb-g1.ctb",
        }
        http_server = make_server("127.0.0.1", 0, server.app)
        thread = threading.Thread(target=http_server.serve_forever, daemon=True)

        try:
            with patch.object(server, "translate", return_value=expected):
                thread.start()
                client = client_module.BrailleClient(
                    f"http://127.0.0.1:{http_server.server_port}"
                )
                result = client.translate("Hi")

            self.assertEqual(result.braille, "⠠⠓⠊")
            self.assertEqual(result.cells, [32, 19, 10])
        finally:
            http_server.shutdown()
            http_server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
