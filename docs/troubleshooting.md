# BrailleQ troubleshooting

Start the App with verbose output when diagnosing a failure:

```bash
arduino-app-cli app start user:brailleq --verbose
```

Replace `user:brailleq` with the actual App identifier. Identify the first
component that fails—camera, OCR, Braille translation or Bridge—before changing
configuration in later stages.

## Camera problems

### `Cannot open device /dev/videoN`

The container should not depend on a numbered `/dev/videoN` path. Numbered
nodes can change when the board restarts or USB devices are reconnected.

1. List stable devices on the UNO Q host:

   ```bash
   ls -l /dev/v4l/by-id/
   ```

2. Identify which node supports MJPEG:

   ```bash
   v4l2-ctl \
     --device /dev/v4l/by-id/usb-Example_Camera_SERIAL-video-index0 \
     --list-formats-ext
   ```

3. Set `CAMERA_HOST_DEVICE` to that complete path.
4. Recreate the Brick so Docker applies the mapping.

If an error still mentions `/dev/video0` rather than `/dev/brailleq-camera`, an
old container image or configuration is probably still running. Perform the
clean rebuild described below.

### Camera exists but the service refuses it

At startup, `v4l2_capture` checks that the mapped target:

- Exists inside the container.
- Is a character device.
- Responds to `v4l2-ctl --list-formats-ext`.
- Advertises `MJPG`.

Read the first startup error carefully. A camera can expose separate metadata
and image nodes; selecting `video-index0` is common but not universal.

### Camera does not advertise MJPEG

The current service explicitly requests `pixelformat=MJPG`. Select another node
that provides MJPEG or modify the service to support one of the camera's actual
formats. Merely changing the requested format without updating decoding and
validation is not sufficient.

### Autofocus control fails

The service currently uses:

```text
focus_automatic_continuous=1
```

Control names and supported values vary by camera. Inspect them with:

```bash
v4l2-ctl --device CAMERA_PATH --list-ctrls
```

If the camera lacks that control, call the client with `autofocus=False` or
adapt the service for the camera's supported control. A fixed-focus camera does
not need an autofocus command.

### Photograph is still out of focus

The five-second setting discards approximately `focus_seconds × fps` frames;
it does not verify mechanically that focus has converged. Improve lighting,
hold the document still, increase text contrast and confirm that the requested
resolution and frame rate are supported. Only then consider adjusting the
focus duration.

## OCR problems

### OCR service takes a long time to become ready

The current service imports PaddleOCR and loads both PP-OCRv5 models before its
HTTP server begins accepting requests. On the first start it may also need to
download model files.

Check:

- Network access from the OCR container.
- Available storage for `/home/arduino/paddle-cache`.
- Available RAM.
- Whether the log reaches `PaddleOCR ready`.
- The reported import and model-loading durations.

The client can wait up to 600 seconds for readiness. Increasing that timeout
does not repair a failed download or initialization exception.

### OCR sometimes takes about a minute

Use the timing lines to locate the delay:

```text
[PERF] OCR request - readiness wait
[PERF] OCR request - uploaded image read
[PERF] OCR request - image decode
[PERF] OCR request - PaddleOCR predict (detection + recognition)
[PERF] OCR request - result extraction
[PERF] OCR request - total server time
```

If `PaddleOCR predict` dominates, compare the fragment and polygon counts
reported by result extraction. An image containing patterns, labels or
background details can generate many candidate text regions, and each region
may require recognition.

The current inference configuration is CPU-only with four threads. Capture
resolution is 1920×1080, although the detector may resize internally. Before
changing models or hardware, compare the same clear and slow photographs and
record resolution, inference time and detected-region count.

If `readiness wait` dominates, the request arrived before model initialization
finished. If another phase dominates, changing the inference engine will not
address that part of the delay.

### OCR request times out

The client allows up to 300 seconds for the HTTP request. A timeout means the
caller stopped waiting; it does not prove that the service process stopped.
Check the service log for model errors, memory pressure or a request that is
still executing. Repeatedly submitting more photographs can make diagnosis
harder because the OCR service processes requests serially.

### OCR returns incorrect or unexpected characters

Recognition confidence belongs to an entire fragment and is not a guarantee
that every character is correct. Improve focus, lighting, alignment and text
size first.

The application supports English output. Before translation it normalizes the
text and replaces unsupported characters with spaces. This prevents an
unexpected character—for example, one incorrectly recognized as Chinese—from
being sent directly to the six-dot English Braille translator.

## Photograph-quality problems

### Sharpness is reported as unavailable

`text_sharpness=None` means the service could not produce any valid text region
for the sharpness calculation. It does not mean the numeric sharpness was zero.

Possible causes include:

- PaddleOCR detected no text.
- The returned polygons were missing or malformed.
- All polygon areas were empty after clipping to the image.
- The photograph did not contain sufficiently recognizable text.

Check whether recognized fragments and polygons were reported. If both are
zero, investigate detection and image composition rather than lowering the
sharpness threshold.

### Every photograph is rejected below 500

The value `500` is a calibration value, not a universal definition of a clear
photograph. Laplacian variance changes with camera, resolution, lighting,
noise, text size and processing.

1. Keep camera settings and resolution fixed.
2. Collect representative clear and blurred photographs.
3. Compare their text-region sharpness values.
4. Choose a threshold that separates those groups reliably.
5. Repeat calibration after changing camera or resolution.

Do not lower the threshold solely to make every current photograph pass; first
confirm that the OCR result on accepted images is useful.

### Small blurred labels make a clear document fail

The service evaluates each detected polygon separately. Regions whose area is
less than 2% of the combined text area are excluded, and the remaining values
are combined with a median weighted by area. This is intended to reduce the
influence of small incidental labels while retaining substantial text regions.

If the main text is still rejected, compare polygon sizes and confirm that the
detector is not splitting the principal text into many tiny regions.

## Braille translation problems

### Unsupported characters or non-six-dot output

The application sanitizes OCR output for English before translation. The
Braille service then validates that every Unicode Braille character is in
`U+2800..U+283F` and every cell value is in `0..63`.

If translation fails:

- Inspect the sanitized text rather than only the raw OCR output.
- Confirm that `BRAILLE_TABLE` names a table installed in the container.
- Confirm that the selected table produces six-dot output.
- Return to `en-ueb-g1.ctb` when testing the default English path.

### Braille service does not become ready

The service performs a startup translation of `a` and expects cell value `1`.
A missing `lou_translate`, missing table or unexpected display table causes the
service to stop before normal use. Inspect the Braille container startup log.

## Bridge and display problems

### Pressing B does nothing

Check:

- Modulino initialization and I²C connection.
- That `Bridge.begin()` completed.
- That the sketch log shows normal startup.
- That the Python application registered `take_picture`.
- Whether `Take picture` appears in the application output.

The sketch sends one notification on the transition from released to pressed;
holding B does not repeatedly request captures.

### Loading continues indefinitely

Loading stops only when an accepted Braille transfer arrives or the
`blurry_picture` notification is received. Inspect the Linux log from the
camera stage onward. An unhandled service exception can stop the application
before either result reaches the sketch.

### Braille data is not displayed

The receiver rejects an invalid transfer ID, an out-of-order offset or a final
size mismatch. Verify that Python completes all three Bridge stages:

```text
braille_begin → one or more braille_chunk calls → braille_end
```

For a short result, also confirm that translation did not produce an empty cell
list after OCR sanitization.

### Dots appear in the wrong positions

Cell bytes use bits 0–5 for Braille dots 1–6. Verify each bit separately using
the layout in `sketch/README.md`. If the software mapping is correct but the
physical image is rotated, confirm the board and matrix orientation.

## Clean rebuild

Use a clean rebuild after changing Dockerfiles, service dependencies, Compose
configuration, camera mappings or model configuration:

```bash
arduino-app-cli app stop user:brailleq
arduino-app-cli app clean-cache user:brailleq
arduino-app-cli app start user:brailleq --verbose
```

If a failure persists, record the first error after the rebuild together with
the component name. Later exceptions are often consequences of that original
failure.
