# 😀 BrailleQ

BrailleQ is an Arduino App Lab project that captures printed text with a
camera, recognizes it with OCR, and displays the result as Braille.

> [!NOTE]
> This project is still under development. More installation and usage
> documentation will be added later.

## Camera configuration

The repository is currently configured for the camera used during development:

```text
Logitech HD Pro Webcam C920
/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_E24E2F9F-video-index0
```

This path identifies that particular camera and will not be correct for every
user. Do not replace it with a path such as `/dev/video0` or `/dev/video2`:
Linux may assign a different number after a reboot or after reconnecting USB
devices.

### Find your camera

Run the following command on the Linux host that runs Arduino App Lab:

```bash
ls -l /dev/v4l/by-id/
```

A camera can expose more than one video node. For example:

```text
usb-Example_Camera_SERIAL-video-index0 -> ../../video0
usb-Example_Camera_SERIAL-video-index1 -> ../../video1
```

Check each candidate with `v4l2-ctl` and select the capture node that advertises
the `MJPG` format:

```bash
v4l2-ctl \
  --device /dev/v4l/by-id/usb-Example_Camera_SERIAL-video-index0 \
  --list-formats-ext
```

The camera used for this project exposes its capture interface as
`video-index0`, but another model may be different. The selected node must
support MJPEG for the current capture service.

### Configure BrailleQ

Set the `CAMERA_HOST_DEVICE` Brick variable to the complete stable path of the
capture node. For example:

```text
CAMERA_HOST_DEVICE=/dev/v4l/by-id/usb-Example_Camera_SERIAL-video-index0
```

The Compose configuration maps that host device to the fixed path
`/dev/brailleq-camera` inside the container. Application code therefore does
not depend on changing `/dev/videoN` numbers.

If the camera does not appear under `/dev/v4l/by-id/`, inspect
`/dev/v4l/by-path/` and use the stable path associated with its physical USB
port instead.

After changing the camera variable, rebuild or recreate the `v4l2_capture`
Brick so Docker applies the new device mapping. At startup, the service checks
that the mapped device exists, is a V4L2 capture node, and supports MJPEG. If
the check fails, inspect the Brick logs for the specific error.

