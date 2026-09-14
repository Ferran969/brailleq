# BrailleQ architecture

This document describes how the Linux application, three service Bricks and
microcontroller sketch cooperate. Public usage instructions remain in the
repository README; implementation-specific details belong here or in the
individual Brick README.

## Runtime boundaries

BrailleQ spans two execution environments on the Arduino UNO Q:

1. The Linux side runs `python/main.py` and the service containers.
2. The microcontroller side runs `sketch/sketch.ino` and drives the buttons and
   LED matrix.

The Arduino Router Bridge carries events and binary Braille data between these
environments. Internal HTTP requests connect the Linux application to each
Brick service.

```text
┌──────────────────────── Microcontroller ────────────────────────┐
│ Modulino buttons → sketch state machine → Arduino LED matrix    │
│                         ▲             │                         │
└─────────────────────────┼─────────────┼─────────────────────────┘
                          │ Router      │ Router
                          │ Bridge      │ Bridge
┌─────────────────────────┼─────────────┼─────────────────────────┐
│ Linux application       │             ▼                         │
│                   python/main.py                                │
│                      │       │       │                          │
│                    HTTP    HTTP    HTTP                         │
│                      ▼       ▼       ▼                          │
│                   camera    OCR   Braille                       │
│                   service service service                       │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### Application orchestrator

`python/main.py` owns the user-request workflow. It does not implement camera
capture, OCR or Braille translation itself. Its responsibilities are:

- Receive `take_picture` from the sketch.
- Ensure only the pending request flag starts a capture.
- Call the camera and OCR Brick clients synchronously.
- Accept or reject the photograph using `MIN_TEXT_SHARPNESS`.
- Sanitize OCR output for the English Braille pipeline.
- Request a Liblouis translation.
- Transfer the resulting cells to the sketch in bounded chunks.

The current loop handles one photograph at a time. While a capture and OCR call
are running, another request is not processed concurrently.

### V4L2 Capture Brick

The client in `bricks/v4l2_capture/__init__.py` sends capture options to the
service in `bricks/v4l2_capture/server.py`.

The service validates its camera when it starts, serializes access with a
process lock, runs `v4l2-ctl`, and returns the captured JPEG bytes. The stable
host camera path is mapped to `/dev/brailleq-camera` inside the container.

### PaddleOCR Brick

The client in `bricks/paddle_ocr/__init__.py` waits for the service to become
ready and uploads the JPEG as multipart form data.

The service in `bricks/paddle_ocr/server.py` loads PP-OCRv5 mobile detection
and recognition models once. The current entrypoint finishes model
initialization before Flask begins accepting requests. The client therefore
retries connection attempts during startup and then checks `/ready`.

For each request the service:

1. Decodes the JPEG with OpenCV.
2. Runs PaddleOCR detection and recognition.
3. Extracts recognized fragments, confidence values and text polygons.
4. Calculates sharpness over significant text polygons.
5. Returns a JSON response to the client.

Inference currently uses the CPU with four Paddle inference threads. Flask is
configured with `threaded=False`, so OCR requests are processed serially.

### Braille Translator Brick

The client in `bricks/braille/__init__.py` waits for `/health`, submits the
sanitized text, and validates every field returned by the service.

The service in `bricks/braille/server.py` invokes `lou_translate` with the
configured Liblouis table. It converts Unicode Braille characters to integer
cell masks and refuses any character outside the six-dot range.

### Microcontroller sketch

The sketch owns the physical interface:

- Button B requests a photograph.
- Buttons A and C navigate through received Braille cells.
- The LED matrix presents countdown, loading, retry and Braille states.
- `BrailleReceiver` assembles a translation sent over several Bridge calls.

See `sketch/README.md` for the state machine, display layout and protocol.

## Successful request sequence

```text
User          Sketch       Python app       Camera        OCR       Braille
 │              │              │               │           │           │
 │ press B      │              │               │           │           │
 ├─────────────►│              │               │           │           │
 │              │ take_picture │               │           │           │
 │              ├─────────────►│               │           │           │
 │              │              │ POST /capture │           │           │
 │              │              ├──────────────►│           │           │
 │              │              │ JPEG          │           │           │
 │              │              │◄──────────────┤           │           │
 │              │              │ POST /ocr                 │           │
 │              │              ├──────────────────────────►│           │
 │              │              │ text, confidence, sharpness           │
 │              │              │◄──────────────────────────┤           │
 │              │              │ POST /translate                       │
 │              │              ├──────────────────────────────────────►│
 │              │              │ cells                                 │
 │              │              │◄──────────────────────────────────────┤
 │              │ begin/chunks/end             │           │           │
 │              │◄─────────────┤               │           │           │
 │ read cells   │              │               │           │           │
 │◄────────────►│              │               │           │           │
```

If the sharpness is unavailable or below the application threshold, the
translation stage and cell transfer are skipped. Python sends
`blurry_picture` to the sketch instead.

## Interfaces and data contracts

### Router Bridge

| Name | Direction | Arguments | Purpose |
| --- | --- | --- | --- |
| `take_picture` | Sketch → Python | None | Request one capture and OCR cycle. |
| `blurry_picture` | Python → Sketch | None | Indicate that the photograph must be repeated. |
| `braille_begin` | Python → Sketch | transfer ID, total cells | Start an atomic cell transfer. |
| `braille_chunk` | Python → Sketch | transfer ID, offset, binary cells | Append the next ordered section. |
| `braille_end` | Python → Sketch | transfer ID | Commit the completed translation. |

`BrailleReceiver` rejects chunks when no transfer is active, the transfer ID
does not match, or the offset is not exactly the current buffer size. It only
publishes a translation after the final size matches the declared size.

### Camera service

```text
POST http://v4l2_capture:8000/capture
JSON request → image/jpeg response
```

The request contains `focus_seconds`, `width`, `height`, `fps` and
`autofocus`. The client returns the encoded response unchanged.

### OCR service

```text
POST http://paddle_ocr_service:5000/ocr
multipart image/jpeg → JSON response
```

The response contains joined text, individual lines, fragment confidence
values and a nullable `text_sharpness` value. Confidence describes recognition
certainty; sharpness measures edges inside detected text regions. They are not
interchangeable.

### Braille service

```text
POST http://braille:8080/translate
JSON request → JSON response
```

The response includes normalized text, Unicode Braille, six-bit integer cells,
dot notation, cell count and table name. The client re-derives the cell and dot
values to detect malformed or inconsistent service responses.

## Configuration ownership

Configuration is intentionally located near the component that owns it:

| Setting | Owner |
| --- | --- |
| Camera host device mapping | `bricks/v4l2_capture/brick_config.yaml` and `brick_compose.yaml` |
| Camera capture defaults | `bricks/v4l2_capture/__init__.py` |
| OCR models and CPU settings | `bricks/paddle_ocr/server.py` |
| OCR model cache | `bricks/paddle_ocr/brick_compose.yaml` |
| Braille translation table | `bricks/braille/brick_config.yaml` and `brick_compose.yaml` |
| Photograph acceptance threshold | `python/main.py` |
| Bridge chunk size | `python/main.py` |
| Button and display behaviour | `sketch/sketch.ino` and `sketch/src/` |

Changing a container-owned setting generally requires rebuilding or recreating
that Brick. Changing a host device mapping always requires container
recreation.

## Failure boundaries

- Camera startup fails early if the mapped node is missing, is not a character
  device, cannot be queried, or does not advertise MJPEG.
- Capture failures become HTTP errors and then `RuntimeError` in the Python
  application.
- OCR startup failures are exposed through readiness checks. Request failures
  propagate to the application.
- An unusable sharpness result follows the normal retry path rather than
  becoming an exception.
- OCR characters outside the supported English character set are replaced
  before translation.
- The Braille client validates six-dot output before any cell reaches the
  microcontroller.
- The Bridge receiver keeps the previous completed translation until a new
  transfer has been received in full.

The current application loop does not catch all service exceptions. An
unhandled camera, OCR or translation failure can therefore stop the App. See
`docs/troubleshooting.md` for diagnosis and recovery.
