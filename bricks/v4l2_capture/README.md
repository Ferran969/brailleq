V4L2 Capture Brick
A custom Arduino App Lab brick that runs `v4l2-ctl` in a dedicated
container and returns a single MJPEG/JPEG frame to the App's Python code.
Default capture
```python
from v4l2_capture import capture_image

jpg = capture_image(5.0)
print(len(jpg))
```
The default call is equivalent to approximately:
```sh
v4l2-ctl -d /dev/brailleq-camera \
  --set-fmt-video=width=1920,height=1080,pixelformat=MJPG \
  --set-parm=30 \
  --set-ctrl=focus_automatic_continuous=1 \
  --stream-mmap=4 \
  --stream-skip=150 \
  --stream-count=1 \
  --stream-to=captured_image.jpg
```
`stream-skip` is computed as:
```text
round(focus_seconds * fps)
```
So `capture_image(5.0, fps=30)` skips 150 frames.
Save directly to a file
```python
from v4l2_capture import capture_to_file

capture_to_file("/tmp/captured_image.jpg", 5.0)
```

Temporary capture archive

For camera diagnostics, every successful capture is also saved in the shared
directory `/captures` inside the service container. The Docker volume exposes
the same files on the Arduino host at:

```text
/home/arduino/brailleq-captures
```

Files use timestamped names such as
`capture_20260913_034835_263667.jpg`. This archive is temporary debugging
behaviour and should be removed after the camera investigation is complete.

Camera device
The Brick identifies the Logitech C920 through its stable Linux device path:
```text
/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_E24E2F9F-video-index0
    -> /dev/brailleq-camera
```
The `/dev/videoN` number may change after a reboot, but the `by-id` path remains
associated with the same physical camera. `video-index0` is used because it is
the image capture node; `video-index1` is not selected.

To use another camera, set the `CAMERA_HOST_DEVICE` Brick variable to its
stable `/dev/v4l/by-id/...-video-index0` path. The host device is always exposed
inside the container as `/dev/brailleq-camera`, and `server.py` reads that path
from `CAMERA_DEVICE`.

At startup the service verifies that the mapped path exists, is a character
device, can be queried as a V4L2 capture node, and advertises MJPEG. A failed
check stops the service with a descriptive error instead of silently using the
wrong `/dev/videoN` node.
Notes
Only one capture is allowed at a time.
The brick container installs `v4l-utils`, which provides `v4l2-ctl`.
If your camera exposes a different autofocus control name, edit the
`--set-ctrl=...` argument in `server.py`.
