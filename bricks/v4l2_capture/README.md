# V4L2 Capture Brick

The V4L2 Capture Brick captures one MJPEG/JPEG frame from a Linux V4L2 camera.
It lets continuous autofocus settle by discarding a configurable number of
frames before returning the final image to the main application.

Camera access and `v4l2-ctl` run in a dedicated container. The application uses
the Python client in `bricks/v4l2_capture/__init__.py`.

## Requirements

- A Linux host with a V4L2-compatible camera.
- A capture node that advertises the `MJPG` pixel format.
- A stable host device path, preferably under `/dev/v4l/by-id/`.
- Permission for Docker to expose the selected character device to the
  container.

Use this command on the Arduino host to list stable camera paths:

```bash
ls -l /dev/v4l/by-id/
```

A camera can expose multiple video nodes. Check each candidate and select the
one that advertises `MJPG`:

```bash
v4l2-ctl \
  --device /dev/v4l/by-id/usb-Example_Camera_SERIAL-video-index0 \
  --list-formats-ext
```

## Quick start

```python
from v4l2_capture import capture_image

jpeg = capture_image(5.0)
print(len(jpeg))
```

The returned value contains the complete encoded JPEG file, not decoded pixel
data.

To capture directly to a file:

```python
from v4l2_capture import capture_to_file

path = capture_to_file("/tmp/captured_image.jpg", 5.0)
print(path)
```

## Python API

### `capture_image`

```python
capture_image(
    focus_seconds=5.0,
    *,
    width=1920,
    height=1080,
    fps=30,
    autofocus=True,
) -> bytes
```

| Parameter | Description |
| --- | --- |
| `focus_seconds` | Approximate time allowed for focus to settle. The service accepts `0..60`. |
| `width` | Requested capture width in pixels. The service accepts `1..8192`. |
| `height` | Requested capture height in pixels. The service accepts `1..8192`. |
| `fps` | Requested frame rate. The service accepts `1..240`. |
| `autofocus` | Enables the configured continuous-autofocus control when true. |

The service calculates the discarded frame count as:

```text
round(focus_seconds * fps)
```

For example, `focus_seconds=5` and `fps=30` discards 150 frames. This does not
guarantee that every camera has focused after exactly five seconds; it gives
continuous autofocus time to converge before selecting a frame.

Invalid local arguments raise `ValueError`. Service errors, camera failures,
and unsuccessful HTTP responses are reported as `RuntimeError`.

If the service is still starting, the client retries connection failures up to
20 times with a 250 ms pause. HTTP errors are not retried because they already
represent a response from the service. The request timeout is the greater of
15 seconds or `focus_seconds + 10` seconds.

### `capture_to_file`

```python
capture_to_file(path, focus_seconds=5.0, **capture_options) -> Path
```

Calls `capture_image`, writes the returned JPEG bytes to `path`, and returns a
`pathlib.Path` object.

## Capture command

With the default options, the service runs the equivalent of:

```bash
v4l2-ctl -d /dev/brailleq-camera \
  --set-fmt-video=width=1920,height=1080,pixelformat=MJPG \
  --set-parm=30 \
  --set-ctrl=focus_automatic_continuous=1 \
  --stream-mmap=4 \
  --stream-skip=150 \
  --stream-count=1 \
  --stream-to=captured_image.jpg
```

Only one process configures and captures from the camera at a time.

## Service API

The application container reaches the service at
`http://v4l2_capture:8000`.

### Health check

```http
GET /health
```

Example response:

```json
{
  "ok": true,
  "device": "/dev/brailleq-camera"
}
```

### Capture an image

```http
POST /capture
Content-Type: application/json

{
  "focus_seconds": 5.0,
  "width": 1920,
  "height": 1080,
  "fps": 30,
  "autofocus": true
}
```

A successful request returns `image/jpeg`. Invalid options return JSON with
HTTP `400`; capture errors return `500`; and capture timeouts return `504`.
Request bodies are limited to 64 KiB.

| Status | Meaning |
| --- | --- |
| `200` | A non-empty JPEG frame was captured. |
| `400` | Invalid JSON, oversized request or option outside its accepted range. |
| `404` | Unknown service path. |
| `500` | Camera configuration, capture or output validation failed. |
| `504` | `v4l2-ctl` exceeded the capture timeout. |

The HTTP server can receive requests concurrently, but a process-wide camera
lock serializes configuration and capture. This prevents two requests from
trying to own the same V4L2 node simultaneously.

## Camera configuration

The repository default is the Logitech C920 used during development:

```text
/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_E24E2F9F-video-index0
```

This path is only a default and will not match every user's camera. Configure
`CAMERA_HOST_DEVICE` with the complete stable path of the desired capture node:

```text
CAMERA_HOST_DEVICE=/dev/v4l/by-id/usb-Example_Camera_SERIAL-video-index0
```

Docker maps that host device to the fixed path `/dev/brailleq-camera` inside
the container. The Python service therefore does not depend on changing
`/dev/videoN` numbers.

| Variable | Default | Scope | Description |
| --- | --- | --- | --- |
| `CAMERA_HOST_DEVICE` | Logitech C920 `by-id` path | Brick | Stable camera path on the Arduino host. |
| `CAMERA_DEVICE` | `/dev/brailleq-camera` | Internal | Fixed device path inside the container. |
| `DEBUG_CAPTURE_DIR` | `/captures` | Internal | Temporary raw-capture archive directory. |

At startup, the service verifies that the mapped path exists, is a character
device, can be queried as a V4L2 capture node, and supports MJPEG.

The server starts only after that validation succeeds. Its `/health` response
therefore indicates that startup probing completed, but it does not take a
test photograph.

If `/dev/v4l/by-id/` is unavailable, `/dev/v4l/by-path/` can provide a path
associated with a physical USB port.

## Debug output

Temporary debugging code archives every successful raw capture inside the
container using names such as:

```text
/captures/capture_20260913_034835_263667.jpg
```

The shared volume exposes the files on the Arduino host at:

```text
/home/arduino/brailleq-captures
```

A debug-copy failure is logged but does not prevent the image from being sent
to OCR. This archive should be removed after camera diagnostics are complete.

## Limitations

- The selected video node must support MJPEG.
- The autofocus control name
  `focus_automatic_continuous` is camera-dependent. A different camera may
  require a change in `server.py` or `autofocus=False`.
- Camera device mappings are applied when Docker creates the container. After
  changing `CAMERA_HOST_DEVICE`, recreate the Brick container.
- A stable `by-id` path identifies a camera reliably, but the repository cannot
  automatically know which of several connected cameras the user intends to
  use.

## Rebuilding

After modifying the service, Dockerfile, Compose configuration, or camera
mapping, rebuild the App cache on the Arduino host:

```bash
arduino-app-cli app stop user:brailleq
arduino-app-cli app clean-cache user:brailleq
arduino-app-cli app start user:brailleq --verbose
```

Replace `user:brailleq` if the App has a different identifier.

For device mapping, MJPEG and autofocus failures, see the project
[troubleshooting guide](../../docs/troubleshooting.md#camera-problems).

## Tests

The current tests validate camera-device probing without requiring a physical
camera:

```bash
python -m unittest tests.test_v4l2_capture_service -v
```
