# Braille Translator Brick

This Arduino App Lab Brick translates complete English strings with Liblouis
and returns six-dot Unified English Braille (UEB) cells. The default table is
`en-ueb-g1.ctb`, which produces uncontracted Grade 1 Braille.

## Client API

Like the other BrailleQ Bricks, the Python client is exposed by the Brick
package itself:

```python
from braille import BrailleClient

translator = BrailleClient()
result = translator.translate("Hello 123")

print(result.braille)
# ⠠⠓⠑⠇⠇⠕⠀⠼⠁⠃⠉

print(result.cells)
# [32, 19, 17, 7, 7, 21, 0, 60, 1, 3, 9]
```

`result.cells` contains one integer for every six-dot Braille cell. Each
integer is a bit mask with this layout:

```text
bit 0 = dot 1
bit 1 = dot 2
bit 2 = dot 3
bit 3 = dot 4
bit 4 = dot 5
bit 5 = dot 6
```

OCR whitespace is normalized by default: line breaks, tabs, and repeated
spaces become one Braille blank. Pass `normalize_whitespace=False` to preserve
whitespace; line breaks are rejected because they cannot be represented by a
six-bit Braille cell.

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

The response includes the normalized text, Unicode Braille, six-bit integer
cells, human-readable dot notation, the number of cells, and the Liblouis
table used for translation.

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

Invalid requests return JSON with an `error` field and an appropriate HTTP
status. Request bodies are limited to 64 KiB and input text to 16,000
characters.

## Configuration

Set `BRAILLE_TABLE` in the Brick configuration to select another installed
Liblouis table. For example, use `en-ueb-g2.ctb` for contracted Grade 2 UEB.
The default is `en-ueb-g1.ctb`.

## Container

The image installs Flask, `liblouis-bin`, and `liblouis-data`. App Lab builds
and starts the service declared in `brick_compose.yaml`; its health check waits
for `GET /health` to respond successfully.

After changing the service or its dependencies, rebuild the Brick container so
the new code is copied into the image.

## Tests

The unit tests mock Liblouis, so they do not require `lou_translate` to be
installed on the development machine. They do require Flask:

```bash
python -m unittest discover -s tests -v
```

The suite verifies the conversion helpers, whitespace normalization, service
responses, error handling, and communication through `BrailleClient`.
