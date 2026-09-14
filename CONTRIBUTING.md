# Contributing to BrailleQ

BrailleQ crosses Python services, containers, camera hardware, OCR models, the
Arduino Router Bridge and microcontroller firmware. A change should be tested
at the narrowest affected layer and then through the complete path whenever
hardware behaviour can change.

## Development setup

Clone the repository and create an isolated Python environment for local
tests:

```bash
git clone https://github.com/Ferran969/brailleq.git
cd brailleq
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install flask
```

The complete application requires Arduino App Lab on an UNO Q. Local tests do
not require Liblouis or a physical camera because the existing suites mock
those boundaries.

## Change categories

### Linux application

Files under `python/` coordinate the complete workflow. When changing them,
verify:

- Photograph requests remain single-shot.
- A rejected photograph never reaches translation.
- OCR sanitization does not join unrelated words.
- Empty text is handled intentionally.
- Braille data is divided without dropping or duplicating cells.
- Every `braille_begin` has a matching `braille_end` on the successful path.

### Brick clients

The `bricks/*/__init__.py` files are the Python APIs consumed by the
application. Keep their public signatures small and document parameters,
return values, timeouts and exceptions in the corresponding Brick README.

Client validation should fail clearly when a service returns malformed data.
Do not silently accept an incompatible response merely to keep the application
running.

### Brick services

The `bricks/*/server.py` files define container service behaviour. Preserve:

- Machine-readable error responses.
- Bounded request sizes and external-process timeouts.
- Startup checks that fail before a bad service handles normal traffic.
- A stable client-facing response format.
- Explicit concurrency decisions around the camera and OCR model.

Changing a service or dependency requires rebuilding the corresponding Brick
container before hardware validation.

### Arduino firmware

Files under `sketch/` run on the microcontroller. Keep button processing
non-blocking and maintain the transfer validation in `BrailleReceiver`.

Changes to bit ordering or Bridge method names must be applied to both the
Python application and sketch. Validate all six dots individually after any
display-coordinate change.

### Container and App configuration

Changes to Dockerfiles, `brick_compose.yaml`, `brick_config.yaml`, `app.yaml`
or `sketch.yaml` should be reviewed for:

- ARM64 and Python-version compatibility.
- Container startup order and health checks.
- Host device and volume mappings.
- Environment-variable defaults.
- Required network and storage access.
- Whether a clean rebuild is necessary.

Never replace the stable camera mapping with a hard-coded `/dev/videoN` path.

## Automated tests

Run the complete local suite from the repository root:

```bash
python -m unittest discover -s tests -v
```

Run one suite while iterating:

```bash
python -m unittest tests.test_braille_service -v
python -m unittest tests.test_v4l2_capture_service -v
```

The current automated coverage includes:

- Braille helper conversion and whitespace normalization.
- Braille HTTP endpoint behaviour.
- Client readiness, error and response validation.
- A local client-to-service Braille request.
- Camera-node startup validation and MJPEG probing.

Automated coverage is still missing for:

- PaddleOCR response extraction.
- Text-region sharpness and area filtering.
- OCR sanitization in `python/main.py`.
- Bridge chunk generation and reception.
- Firmware state transitions and matrix coordinates.
- The complete hardware workflow.

Add focused tests when changing testable logic in these areas. Hardware-only
behaviour should be accompanied by a reproducible manual test description.

## Hardware validation

For changes affecting capture, OCR, quality assessment, Braille transfer or
display, verify on an UNO Q:

1. Start from a clean Brick build where applicable.
2. Confirm all three services start and report healthy/ready.
3. Capture a clear English document.
4. Confirm recognized text and fragment confidence are reasonable.
5. Confirm the photograph passes the configured sharpness threshold.
6. Verify the first, middle and final Braille cells on the display.
7. Navigate both directions with A and C.
8. Capture a deliberately blurred document.
9. Confirm the retry indication appears and no new Braille is displayed.
10. Repeat a capture to confirm recovery without restarting the App.

Camera-related changes should also be tested after rebooting and reconnecting
the camera, because that is where unstable `/dev/videoN` numbering appears.

## Performance changes

Measure before and after with the same images, camera settings and device
temperature. Record at least:

- Capture duration.
- OCR readiness wait.
- OCR detection and recognition duration.
- Fragment and polygon count.
- Complete request duration.
- Whether recognized text or confidence changed.

Do not claim a speed improvement from a single photograph. Test a clear page,
a blurred page, a sparse image and an image that produces many detections.

## Documentation expectations

Keep documentation next to its audience:

- Project setup and user workflow: root `README.md`.
- Component relationships and protocols: `docs/architecture.md`.
- Operational failures: `docs/troubleshooting.md`.
- Brick API and service behaviour: `bricks/<brick>/README.md`.
- Firmware controls and display mapping: `sketch/README.md`.
- Internal invariants: docstrings or comments beside the implementation.

Update documentation in the same change whenever a public function, endpoint,
environment variable, Bridge method, default value or user-visible state
changes.

## Review checklist

Before requesting review:

- Run `git diff --check`.
- Run the relevant automated tests.
- State which hardware tests were performed.
- Confirm no unrelated generated files are included.
- Check that defaults in code, Compose files and README tables agree.
- Explain any compatibility or migration requirement.
- Identify temporary instrumentation explicitly.

## Rebuilding on the UNO Q

For service, dependency or container configuration changes:

```bash
arduino-app-cli app stop user:brailleq
arduino-app-cli app clean-cache user:brailleq
arduino-app-cli app start user:brailleq --verbose
```

Replace the App identifier as appropriate.

## License status

The repository currently has no top-level `LICENSE` file. Before accepting
external contributions or presenting the project as generally reusable, the
maintainers should choose and add a license. This document does not grant
permissions beyond those provided by an eventual license.
