#!/bin/sh
set -eu

PASS_MARKER=/tmp/opencl-probe-passed
rm -f "$PASS_MARKER"

echo "[OPENCL PROBE] Checking DRM devices"
if ! find /dev/dri -maxdepth 1 -type c -name 'renderD*' -print -quit \
    | grep -q .; then
    echo "[OPENCL PROBE] FAIL no /dev/dri/renderD* device is available" >&2
    exit 1
fi
find /dev/dri -maxdepth 1 -type c -print

echo "[OPENCL PROBE] Mesa package versions"
dpkg-query -W -f='${Package} ${Version}\n' \
    mesa-opencl-icd \
    mesa-libgallium \
    ocl-icd-libopencl1

echo "[OPENCL PROBE] Enumerating OpenCL devices"
clinfo -l

echo "[OPENCL PROBE] Compiling and executing a kernel on the GPU"
/usr/local/bin/opencl_probe

touch "$PASS_MARKER"
echo "[OPENCL PROBE] Verification completed successfully"

# Keep the experimental service alive so its health and logs can be inspected.
exec sleep infinity
