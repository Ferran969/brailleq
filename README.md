# 😀 BrailleQ

BrailleQ is an Arduino App Lab project that photographs printed English text,
recognizes it with OCR, translates it to six-dot Unified English Braille (UEB),
and presents one Braille cell at a time on the Arduino LED matrix.

The project combines Linux services running on the Arduino UNO Q with firmware
running on its microcontroller. A Modulino Buttons module provides the user
controls and a USB V4L2 camera supplies the image.

> [!IMPORTANT]
> BrailleQ is under active development. It currently supports English,
> uncontracted six-dot Braille and one photograph at a time. It is not an
> assistive product certified for safety-critical use.

## System overview

```text
Modulino button B
       │
       ▼
Arduino sketch ── take_picture ──► Python application
                                         │
                          ┌──────────────┼──────────────┐
                          ▼              ▼              ▼
                    V4L2 Capture     PaddleOCR       Liblouis
                    camera service   OCR service   Braille service
                          │              │              │
                          └──── JPEG ────┴─ text ───────┘
                                         │
                                six-bit Braille cells
                                         │
                                         ▼
Arduino sketch ◄── braille_begin/chunk/end ── Python application
       │
       ▼
LED matrix and A/C navigation
```

The services are packaged as three App Lab Bricks:

| Brick | Responsibility | Internal service |
| --- | --- | --- |
| `v4l2_capture` | Focus the camera and return one JPEG frame. | `http://v4l2_capture:8000` |
| `paddle_ocr` | Detect and recognize text and estimate text-region sharpness. | `http://paddle_ocr_service:5000` |
| `braille` | Translate sanitized English text to six-dot UEB cells. | `http://braille:8080` |

See [Architecture](docs/architecture.md) for component boundaries, data formats,
startup behaviour and the complete request sequence.

## Hardware requirements

- Arduino UNO Q supported by Arduino App Lab.
- Arduino LED matrix available to the sketch.
- Modulino Buttons module at I²C address `0x3E`.
- Linux V4L2-compatible USB camera with an `MJPG` capture mode.
- Sufficient device storage for the PaddlePaddle packages and OCR model cache.
- Network access during the first OCR model download.

The default camera configuration targets the Logitech HD Pro Webcam C920 used
during development. Other cameras must be configured before the App starts.

## Software requirements

- Arduino App Lab and `arduino-app-cli` on the UNO Q.
- Docker/container support managed by App Lab.
- `v4l2-ctl` on the Linux host when identifying camera capture nodes.
- Python 3 for running the repository's development tests.

The Brick images install their runtime dependencies themselves. PaddleOCR uses
Python 3.13, PaddlePaddle 3.2.1 and the PP-OCRv5 mobile detection and
recognition models.

## Repository layout

```text
app.yaml                         App Lab application manifest
python/main.py                   Linux-side application orchestration
bricks/v4l2_capture/             Camera client and capture service
bricks/paddle_ocr/               OCR client and service
bricks/braille/                  Liblouis client and translation service
sketch/                          Microcontroller firmware and display code
tests/                           Development-machine unit tests
```

Each Brick has its own README describing its Python API, HTTP API,
configuration and limitations:

- [V4L2 Capture Brick](bricks/v4l2_capture/README.md)
- [PaddleOCR Brick](bricks/paddle_ocr/README.md)
- [Braille Translator Brick](bricks/braille/README.md)
- [Arduino sketch](sketch/README.md)

## Initial setup

### 1. Obtain the project

```bash
git clone https://github.com/Ferran969/brailleq.git
cd brailleq
```

Open or import the repository as an Arduino App Lab project on the UNO Q.

### 2. Connect the hardware

1. Connect the V4L2 camera to the UNO Q.
2. Connect the Modulino Buttons module.
3. Confirm that the camera appears on the Linux side of the board.

### 3. Select the camera

List stable camera paths on the UNO Q host:

```bash
ls -l /dev/v4l/by-id/
```

A camera can expose multiple nodes:

```text
usb-Example_Camera_SERIAL-video-index0 -> ../../video0
usb-Example_Camera_SERIAL-video-index1 -> ../../video1
```

Inspect each candidate and choose the node that advertises `MJPG`:

```bash
v4l2-ctl \
  --device /dev/v4l/by-id/usb-Example_Camera_SERIAL-video-index0 \
  --list-formats-ext
```

Set the `CAMERA_HOST_DEVICE` Brick variable to the complete stable path:

```text
CAMERA_HOST_DEVICE=/dev/v4l/by-id/usb-Example_Camera_SERIAL-video-index0
```

Do not configure `/dev/video0` or `/dev/video2` directly. Those numbers can
change after a reboot or reconnection. If `/dev/v4l/by-id/` is unavailable,
use the appropriate stable entry under `/dev/v4l/by-path/`.

Docker maps the selected host node to `/dev/brailleq-camera` inside the
capture container. Recreate the Brick after changing this mapping.

### 4. Review the application settings

| Setting | Default | Location | Purpose |
| --- | --- | --- | --- |
| `CAMERA_HOST_DEVICE` | Development C920 `by-id` path | V4L2 Brick variable | Selects the host capture node. |
| `BRAILLE_TABLE` | `en-ueb-g1.ctb` | Braille Brick variable | Selects the installed Liblouis table. |
| `MIN_TEXT_SHARPNESS` | `500.0` | `python/main.py` | Rejects photographs below the calibrated text sharpness. |
| Camera focus duration | `5.0` seconds | `python/main.py` | Controls how long frames are discarded while autofocus settles. |
| Camera frame format | `1920×1080`, 30 FPS, MJPEG | V4L2 client defaults | Controls capture size and frame rate. |
| Braille transfer chunk | `180` bytes | `python/main.py` | Limits each Bridge payload sent to the sketch. |

The sharpness value is camera-, resolution-, lighting- and text-dependent.
Recalibrate `MIN_TEXT_SHARPNESS` if the camera setup or capture resolution
changes.

### 5. Build and start

Use the App identifier configured on the device. The development identifier is
shown here as `user:brailleq`:

```bash
arduino-app-cli app start user:brailleq --verbose
```

The first start can take considerably longer while the OCR image is built and
the models are downloaded. The application waits for the OCR readiness
endpoint before submitting a photograph.

## Using BrailleQ

The three buttons have these functions:

| Button | Action |
| --- | --- |
| A | Move to the previous Braille cell. |
| B | Start a new photograph and OCR request. |
| C | Move to the next Braille cell. |

Typical operation:

1. Position the printed English text in front of the camera.
2. Press B.
3. Keep the document still during the five-second focus/countdown period.
4. Wait while the loading indicator is displayed.
5. If the photograph is rejected, the LED matrix shows a cross; reposition the
   document and press B again.
6. If accepted, the first Braille cell appears.
7. Use A and C to navigate through the translated cells.

A new accepted translation replaces the previous one and resets navigation to
its first cell.

## Photograph acceptance

PaddleOCR returns the polygons associated with recognized text. The OCR Brick
calculates a Laplacian-variance sharpness value for every polygon, ignores
regions covering less than 2% of the combined text area, and combines the
remaining values using an area-weighted median.

The application rejects the photograph when:

```text
text_sharpness is unavailable
or
text_sharpness < MIN_TEXT_SHARPNESS
```

Rejected photographs are not translated or displayed. The sketch receives a
`blurry_picture` notification and presents its retry indicator.

## Text and Braille behaviour

Before translation, OCR output is normalized with Unicode NFKC and restricted
to ASCII letters, digits, punctuation and whitespace. Unsupported characters
are replaced by spaces so that unrelated words are not accidentally joined.

The default Liblouis table is `en-ueb-g1.ctb`:

- English Unified English Braille.
- Grade 1, without contractions.
- Six dots per cell.
- Cell values from `0` to `63`.

Changing to an eight-dot table is not supported by the current display and
Bridge data path.

## Rebuilding after changes

Changes to a Brick service, Dockerfile, Compose file, dependency or device
mapping require the App cache to be rebuilt:

```bash
arduino-app-cli app stop user:brailleq
arduino-app-cli app clean-cache user:brailleq
arduino-app-cli app start user:brailleq --verbose
```

Replace `user:brailleq` with the actual App identifier if necessary. Pure
Python application or sketch changes may follow a shorter App Lab development
cycle, but a clean rebuild is the reliable option when container contents have
changed.

## Logs and performance timings

The current development build reports the duration of important phases:

```text
[PERF] Application - camera capture: ...
[PERF] OCR request - readiness wait: ...
[PERF] OCR request - PaddleOCR predict (detection + recognition): ...
[PERF] OCR request - result extraction: ...
[PERF] OCR request - total server time: ...
```

The result-extraction line also reports the number of fragments and polygons.
This is useful when a particular image is much slower than another: a scene
with many false text detections can cause many recognition operations.

These messages are temporary performance instrumentation and are not a stable
API. Do not write application logic that parses them.

## Tests

Run the current development-machine test suite from the repository root:

```bash
python -m unittest discover -s tests -v
```

The tests currently cover:

- Braille conversion, normalization and HTTP behaviour.
- Braille client validation and readiness retries.
- V4L2 device probing and MJPEG validation.

The PaddleOCR Brick, microcontroller firmware and complete hardware pipeline
do not yet have automated coverage. Changes to those areas require validation
on an UNO Q with representative clear and blurred photographs.

See [Contributing](CONTRIBUTING.md) for the expected validation checklist.

## Troubleshooting

Common failures and the corresponding checks are collected in
[Troubleshooting](docs/troubleshooting.md), including:

- Camera device unavailable after restarting the board.
- Camera node present but incompatible with MJPEG capture.
- Autofocus-control errors.
- OCR initialization or unusually slow recognition.
- Photograph rejected because sharpness is unavailable or below threshold.
- Unsupported OCR characters and Braille translation failures.
- Bridge or LED matrix not updating.

## Current limitations

- English text and six-dot UEB only.
- One photograph and OCR request at a time.
- OCR inference currently uses the CPU with four inference threads.
- OCR latency depends strongly on image content and detected-region count.
- The camera must provide MJPEG through V4L2.
- The autofocus control is camera-dependent.
- The sharpness threshold is calibrated for the development setup.
- There is no automatic language detection.
- Hardware integration is not covered by automated tests.

## License status

This repository does not currently contain a top-level `LICENSE` file. The
maintainers should select and add an appropriate license before presenting the
project as generally reusable or accepting external contributions. No license
is implied by the presence of source code on GitHub.

## Further documentation

- [Architecture](docs/architecture.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Contributing and testing](CONTRIBUTING.md)
- [Arduino sketch](sketch/README.md)
- [V4L2 Capture Brick](bricks/v4l2_capture/README.md)
- [PaddleOCR Brick](bricks/paddle_ocr/README.md)
- [Braille Translator Brick](bricks/braille/README.md)
