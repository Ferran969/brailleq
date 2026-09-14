# PaddleOCR Brick

The PaddleOCR Brick detects and recognizes text in an encoded image. It also
reports recognition confidence for each fragment and estimates the sharpness
of the detected text regions.

PaddleOCR runs in a dedicated CPU container. The main application communicates
with it through the Python client in `bricks/paddle_ocr/__init__.py`.

## Requirements

- Enough storage for PaddlePaddle, PaddleOCR, and the downloaded model cache.
- An image encoded in a format supported by OpenCV. BrailleQ normally supplies
  an MJPEG/JPEG frame from the V4L2 Capture Brick.
- Network access during the first model download unless the model cache is
  already populated.

The current container uses Python 3.13, PaddlePaddle 3.2.1, and the mobile
PP-OCRv5 detection and recognition models.

## Quick start

```python
from paddle_ocr import recognize

with open("picture.jpg", "rb") as image_file:
    image = image_file.read()

text, text_sharpness = recognize(image)

print(text)
print(text_sharpness)
```

During recognition, the client prints every recognized fragment and its
confidence score:

```text
[OCR] 97.4% | "Example text"
```

## Python API

### `wait_until_ready`

```python
wait_until_ready(timeout=600)
```

Waits until the OCR models have finished loading. A `TimeoutError` is raised if
the service does not become ready before the timeout. A failed readiness check
raises `RuntimeError`.

### `recognize`

```python
text, text_sharpness = recognize(image)
```

Parameters:

| Parameter | Type | Description |
| --- | --- | --- |
| `image` | `bytes` | Complete encoded image file. |

Return values:

| Value | Type | Description |
| --- | --- | --- |
| `text` | `str` | Recognized fragments joined with line breaks. |
| `text_sharpness` | `float \| None` | Sharpness of significant text regions, or `None` when no valid text polygon exists. |

The client raises `RuntimeError` for unsuccessful HTTP responses. Connection
and request timeout exceptions from `requests` can also propagate to the
caller.

## Text sharpness

The service measures sharpness using the variance of the grayscale image
Laplacian inside PaddleOCR's recognized text polygons.

The calculation is performed as follows:

1. Calculate a separate sharpness value for each detected text polygon.
2. Calculate the total area covered by all valid polygons.
3. Ignore any polygon whose area is less than 2% of that total.
4. Combine the remaining values using a median weighted by polygon area.

If more than 50 similarly sized regions make every individual area smaller
than 2% of the total, all regions are retained as a fallback.

The Brick only reports the measurement. The acceptance threshold belongs to
the application logic and is currently defined by `MIN_TEXT_SHARPNESS` in
`python/main.py`.

Laplacian variance depends on the camera, resolution, lighting, focus, and text
size. Calibrate the application threshold using representative good and bad
captures from the final hardware setup.

## Service API

The application container reaches the service at
`http://paddle_ocr_service:5000`.

### Liveness check

```http
GET /health
```

Returns `200` as soon as Flask is alive:

```json
{"status":"alive"}
```

This endpoint does not guarantee that the OCR models are ready.

### Readiness check

```http
GET /ready
```

- `200` with `{"status":"ready"}` when OCR can accept requests.
- `503` with `{"status":"initializing"}` while models are loading.
- `500` with an error description if model initialization failed.

### Recognize an image

```http
POST /ocr
Content-Type: multipart/form-data
```

The multipart body must contain a file field named `image`.

Example response:

```json
{
  "text": "First line\nSecond line",
  "lines": ["First line", "Second line"],
  "fragments": [
    {"text": "First line", "confidence": 0.974},
    {"text": "Second line", "confidence": 0.951}
  ],
  "text_sharpness": 842.37
}
```

## Configuration

These operational variables are set in `brick_compose.yaml`:

| Variable | Container default | Description |
| --- | --- | --- |
| `PADDLE_PDX_CACHE_HOME` | `/models` | Paddle model cache directory. |
| `PADDLE_PDX_MODEL_SOURCE` | `bos` | Paddle model download source. |
| `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK` | `True` | Disables the model-source availability check. |
| `DEBUG_OVERLAY_DIR` | `/captures` | Directory used for temporary text-detection overlays. |

The host directory `/home/arduino/paddle-cache` is mounted at `/models` so
models survive container recreation.

## Debug output

Temporary debugging code saves a copy of every processed image with all
detected text polygons highlighted in green. This includes polygons later
ignored by the 2% sharpness-area filter.

Inside the container, files are written as:

```text
/captures/ocr_overlay_YYYYMMDD_HHMMSS_microseconds.jpg
```

The shared volume exposes them on the Arduino host at:

```text
/home/arduino/brailleq-captures
```

Failure to save an overlay is logged but does not fail the OCR request. The
overlay archive is temporary and should be removed after diagnostics are
complete.

For raw detector probability maps, threshold masks, and heatmaps, use
`tools/debug_detection.py`. The production service works with PaddleOCR's
postprocessed text polygons and does not expose its raw probability map.

## Limitations

- Inference currently runs on the CPU.
- Document orientation classification, document unwarping, and text-line
  orientation are disabled.
- Recognition confidence applies to complete fragments, not individual
  characters.
- A confident fragment can still contain an incorrect or unsupported Unicode
  character. Validate OCR text before passing it to the Braille Brick.
- No automated tests currently cover this Brick.

## Rebuilding

After modifying the service, Dockerfile, model configuration, or Compose
mounts, rebuild the App cache on the Arduino host:

```bash
arduino-app-cli app stop user:brailleq
arduino-app-cli app clean-cache user:brailleq
arduino-app-cli app start user:brailleq --verbose
```

Replace `user:brailleq` if the App has a different identifier.

## Tests

There is currently no automated test module dedicated to this Brick. Until one
is added, validate changes by rebuilding the container, checking `/ready`, and
submitting representative sharp and blurred images through the Python client.
