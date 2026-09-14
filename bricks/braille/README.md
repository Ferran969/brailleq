# Braille Translator Brick

The Braille Translator Brick converts complete English strings into six-dot
Unified English Braille (UEB) using Liblouis. It returns Unicode Braille,
MCU-friendly cell values, and human-readable dot notation.

The default table is `en-ueb-g1.ctb`, which produces uncontracted Grade 1 UEB.

In the BrailleQ pipeline, `python/main.py` sanitizes OCR output before calling
this Brick. The returned integer cells are then sent to the microcontroller in
binary chunks; the Brick does not communicate with the display directly.

## Requirements

The service runs in its own container. Its image installs Flask,
`liblouis-bin`, and `liblouis-data`, so Liblouis is not required in the main
application container.

Any table selected through `BRAILLE_TABLE` must be installed in the service
image and must produce six-dot Unicode Braille characters.

## Quick start

```python
from braille import BrailleClient

translator = BrailleClient()
result = translator.translate("Hello 123")

print(result.braille)
# ⠠⠓⠑⠇⠇⠕⠀⠼⠁⠃⠉

print(result.cells)
# [32, 19, 17, 7, 7, 21, 0, 60, 1, 3, 9]
```

## Python API

### `BrailleClient`

```python
BrailleClient(
    base_url="http://braille:8080",
    timeout=20.0,
    ready_timeout=30.0,
)
```

- `base_url` is the internal address of the translation service.
- `timeout` is the maximum duration of one translation request.
- `ready_timeout` is the maximum time spent waiting for the service health
  endpoint before a translation.

Both timeout values must be greater than zero.

`wait_until_ready()` polls `GET /health` every 250 ms when necessary. Each
translation performs this readiness check before sending its request. A
connection attempt uses at most two seconds or the remaining readiness time,
whichever is smaller.

### `translate`

```python
result = translator.translate(
    "Hello world",
    normalize_whitespace=True,
)
```

With `normalize_whitespace=True`, line breaks, tabs, and repeated spaces are
converted into one Braille blank. If normalization is disabled, input line
breaks are rejected because they cannot be represented by one six-bit cell.

The returned `BrailleTranslation` contains:

| Field | Type | Description |
| --- | --- | --- |
| `text` | `str` | Text actually passed to Liblouis after normalization. |
| `braille` | `str` | Unicode six-dot Braille string. |
| `cells` | `list[int]` | Cell bit masks in the range `0..63`. |
| `dots` | `list[str]` | Dot notation such as `125` or `0`. |
| `table` | `str` | Liblouis table used for translation. |

Cell integers use the following bit layout:

```text
bit 0 = dot 1
bit 1 = dot 2
bit 2 = dot 3
bit 3 = dot 4
bit 4 = dot 5
bit 5 = dot 6
```

Connection failures, service errors, timeouts, malformed responses, and
non-six-dot output raise `BrailleClientError`.

## Service API

The application container reaches the service at `http://braille:8080`.

### Health check

```http
GET /health
```

Example response:

```json
{
  "status": "ok",
  "table": "en-ueb-g1.ctb",
  "display_table": "unicode.dis"
}
```

### Translate text

```http
POST /translate
Content-Type: application/json

{"text":"Hello 123","normalize_whitespace":true}
```

Example response:

```json
{
  "text": "Hello 123",
  "braille": "⠠⠓⠑⠇⠇⠕⠀⠼⠁⠃⠉",
  "cells": [32, 19, 17, 7, 7, 21, 0, 60, 1, 3, 9],
  "dots": ["6", "125", "15", "123", "123", "135", "0", "3456", "1", "12", "14"],
  "count": 11,
  "table": "en-ueb-g1.ctb"
}
```

Invalid requests return a JSON object with an `error` field. Request bodies
are limited to 64 KiB and input text is limited to 16,000 characters.

| Status | Meaning |
| --- | --- |
| `200` | Health check or successful translation. |
| `400` | Malformed JSON, missing/invalid text, or invalid normalization option. |
| `404` | Unknown endpoint. |
| `405` | Method not accepted by an existing endpoint. |
| `413` | Request body exceeds 64 KiB. |
| `500` | Liblouis is unavailable, times out, fails, or returns unsupported output. |

The Liblouis subprocess has a 15-second timeout. The Flask service permits
concurrent HTTP handlers, and each translation starts its own bounded
`lou_translate` process.

## Startup behaviour

Before listening for requests, the service translates `a` and verifies that
the configured table produces six-dot cell value `1`. A missing table, missing
`lou_translate` executable or incompatible display table therefore fails at
startup rather than during the first user request.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `BRAILLE_TABLE` | `en-ueb-g1.ctb` | Liblouis translation table. For example, `en-ueb-g2.ctb` selects contracted Grade 2 UEB. |

## Limitations

- The complete data path is six-dot only; every cell must be between `0` and
  `63`.
- The default table is for English UEB. Selecting an eight-dot table does not
  add support for another language.
- Unsupported characters can make Liblouis emit technical fallback patterns.
  Output containing dots 7 or 8 is rejected instead of being sent to the
  display as valid six-dot Braille.
- Text from OCR should be sanitized for the expected language before calling
  this Brick.

## Rebuilding

After modifying the client, service, Dockerfile, or Compose configuration,
rebuild the App cache on the Arduino host:

```bash
arduino-app-cli app stop user:brailleq
arduino-app-cli app clean-cache user:brailleq
arduino-app-cli app start user:brailleq --verbose
```

Replace `user:brailleq` if the App has a different identifier.

For startup and translation failures, see the project
[troubleshooting guide](../../docs/troubleshooting.md#braille-translation-problems).

## Tests

The unit tests mock the Liblouis process and therefore do not require
`lou_translate` on the development host. Flask is required.

```bash
python -m unittest tests.test_braille_service -v
```

The suite covers conversion helpers, whitespace normalization, HTTP error
responses, readiness retries, client validation, and an end-to-end local HTTP
request.
