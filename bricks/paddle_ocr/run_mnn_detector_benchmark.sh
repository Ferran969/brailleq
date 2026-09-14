#!/bin/sh
set -eu

MODEL=/models/mnn/PP-OCRv5_mobile_det_544x960.mnn
MODEL_DIR=/models/benchmark
RESULT_DIR=/captures/mnn-detector-benchmark
PASS_MARKER=/tmp/mnn-detector-benchmark-passed
LOOPS=${MNN_BENCHMARK_LOOPS:-10}
WARMUPS=${MNN_BENCHMARK_WARMUPS:-3}

rm -f "$PASS_MARKER"
mkdir -p "$RESULT_DIR"

echo "[MNN DETECTOR] Verifying files and OpenCL backend"
test -s "$MODEL"
clinfo -l > "$RESULT_DIR/opencl_devices.txt" 2>&1
cat "$RESULT_DIR/opencl_devices.txt"

echo "[MNN DETECTOR] Inspecting converted model"
GetMNNInfo "$MODEL" > "$RESULT_DIR/model_info.txt" 2>&1
cat "$RESULT_DIR/model_info.txt"

echo "[MNN DETECTOR] Comparing OpenCL output with the CPU backend"
backendTest.out "$MODEL" 3 0.05 0 0 \
    > "$RESULT_DIR/backend_correctness.txt" 2>&1
cat "$RESULT_DIR/backend_correctness.txt"
if ! grep -q "Correct !" "$RESULT_DIR/backend_correctness.txt"; then
    echo "[MNN DETECTOR] FAIL OpenCL output did not match CPU" >&2
    exit 1
fi

echo "[MNN DETECTOR] CPU benchmark: loops=$LOOPS warmups=$WARMUPS threads=4"
benchmark.out "$MODEL_DIR" "$LOOPS" "$WARMUPS" 0 4 0 \
    > "$RESULT_DIR/cpu_benchmark.txt" 2>&1
cat "$RESULT_DIR/cpu_benchmark.txt"

echo "[MNN DETECTOR] OpenCL benchmark: loops=$LOOPS warmups=$WARMUPS"
benchmark.out "$MODEL_DIR" "$LOOPS" "$WARMUPS" 3 1 0 \
    > "$RESULT_DIR/opencl_benchmark.txt" 2>&1
cat "$RESULT_DIR/opencl_benchmark.txt"

echo "[MNN DETECTOR] Recording per-operation OpenCL profile"
timeProfile.out "$MODEL" 5 3 1x3x544x960 1 0 \
    > "$RESULT_DIR/opencl_profile.txt" 2>&1
cat "$RESULT_DIR/opencl_profile.txt"

{
    echo "MNN version: 3.6.1"
    echo "MNN commit: d407447ed56c4121a11ccbd266dc184ca1ead0c2"
    echo "Detector: PP-OCRv5_mobile_det_onnx_infer"
    echo "Detector archive SHA-256: 781056046c9ed77a15c94681605db6a0f62317c2e9cce6931c71da2478d4bc30"
    echo "Input shape: 1x3x544x960"
    echo "CPU threads: 4"
    echo "Measured loops: $LOOPS"
    echo "Warm-up loops: $WARMUPS"
    dpkg-query -W -f='${Package} ${Version}\n' \
        mesa-opencl-icd \
        mesa-libgallium \
        ocl-icd-libopencl1
} > "$RESULT_DIR/environment.txt"

touch "$PASS_MARKER"
echo "[MNN DETECTOR] PASS detector conversion and CPU/OpenCL benchmark completed"
echo "[MNN DETECTOR] Results saved to $RESULT_DIR"

# Keep the experimental service alive so its health and logs can be inspected.
exec sleep infinity
