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
v4l2-ctl -d /dev/video2 \
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
Camera device
By default the brick maps the host camera:
```text
/dev/video2 -> /dev/video2
```
If the camera appears under another device number, change the `devices`
entry in `brick_compose.yaml` and the `DEVICE` constant in `service.py`
to match.
Notes
Only one capture is allowed at a time.
The brick container installs `v4l-utils`, which provides `v4l2-ctl`.
If your camera exposes a different autofocus control name, edit the
`--set-ctrl=...` argument in `service.py`.