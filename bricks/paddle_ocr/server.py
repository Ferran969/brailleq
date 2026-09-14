"""Serial HTTP OCR service with fragment confidence and sharpness reporting."""

import os
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, jsonify, request


app = Flask(__name__)

ocr = None
ocr_error = None
ocr_ready = threading.Event()


MIN_REGION_AREA_RATIO = 0.02
DEBUG_OVERLAY_DIR = Path(os.getenv("DEBUG_OVERLAY_DIR", "/captures"))


def _weighted_median(values, weights):
    """Return the median of values, using the corresponding areas as weights."""
    order = np.argsort(values)
    sorted_values = np.asarray(values, dtype=np.float64)[order]
    sorted_weights = np.asarray(weights, dtype=np.float64)[order]
    midpoint = sorted_weights.sum() / 2.0
    index = np.searchsorted(np.cumsum(sorted_weights), midpoint, side="left")
    return float(sorted_values[min(index, len(sorted_values) - 1)])


def _save_detection_overlay(image, polygons):
    """Temporarily save an image highlighting every detected text region."""
    try:
        height, width = image.shape[:2]
        highlighted = image.copy()
        overlay = image.copy()
        clipped_polygons = []

        for polygon in polygons:
            points = np.asarray(polygon, dtype=np.int32).reshape(-1, 2)
            if len(points) < 3:
                continue

            points[:, 0] = np.clip(points[:, 0], 0, width - 1)
            points[:, 1] = np.clip(points[:, 1], 0, height - 1)
            clipped_polygons.append(points)
            cv2.fillPoly(overlay, [points], (0, 255, 0))

        highlighted = cv2.addWeighted(
            highlighted,
            0.70,
            overlay,
            0.30,
            0.0,
        )

        for points in clipped_polygons:
            cv2.polylines(highlighted, [points], True, (0, 255, 0), 3)

        DEBUG_OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_path = DEBUG_OVERLAY_DIR / f"ocr_overlay_{timestamp}.jpg"
        if not cv2.imwrite(str(output_path), highlighted):
            raise OSError("cv2.imwrite returned false")
        print(
            f"[paddle_ocr] detection overlay saved to {output_path}",
            flush=True,
        )
    except Exception as error:
        # TEMPORARY DEBUG CODE: saving an overlay must not break OCR.
        print(
            f"[paddle_ocr] could not save detection overlay: {error}",
            flush=True,
        )


def _text_region_sharpness(image, polygons):
    """Return an area-weighted median of significant text-region sharpness."""
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = grayscale.shape
    laplacian = cv2.Laplacian(grayscale, cv2.CV_64F)
    regions = []

    for polygon in polygons:
        points = np.asarray(polygon, dtype=np.int32).reshape(-1, 2)
        if len(points) < 3:
            continue

        points[:, 0] = np.clip(points[:, 0], 0, width - 1)
        points[:, 1] = np.clip(points[:, 1], 0, height - 1)
        region_mask = np.zeros(grayscale.shape, dtype=np.uint8)
        cv2.fillPoly(region_mask, [points], 255)

        selected_pixels = region_mask > 0
        area = int(np.count_nonzero(selected_pixels))
        if area == 0:
            continue

        regions.append({
            "area": area,
            "sharpness": float(laplacian[selected_pixels].var()),
        })

    if not regions:
        return None

    total_text_area = sum(region["area"] for region in regions)
    minimum_area = total_text_area * MIN_REGION_AREA_RATIO
    significant_regions = [
        region
        for region in regions
        if region["area"] >= minimum_area
    ]

    # More than 50 similarly-sized regions could all fall below 2% of the
    # total. In that unusual case, keep every region instead of returning no
    # sharpness measurement.
    if not significant_regions:
        significant_regions = regions

    return _weighted_median(
        [region["sharpness"] for region in significant_regions],
        [region["area"] for region in significant_regions],
    )


def initialize_ocr():
    """Load the configured OCR models once and publish initialization state."""
    global ocr, ocr_error

    # TEMPORARY PERFORMANCE DIAGNOSTICS: remove after OCR profiling.
    initialization_started = time.perf_counter()

    try:
        phase_started = time.perf_counter()
        print("Importing PaddleOCR...", flush=True)
        from paddleocr import PaddleOCR
        print(
            "[PERF] PaddleOCR import: "
            f"{time.perf_counter() - phase_started:.3f} s",
            flush=True,
        )

        print("Loading OCR models...", flush=True)

        print(
            "OCR configuration: CPU, MKL-DNN disabled, 4 inference threads",
            flush=True,
        )

        phase_started = time.perf_counter()
        ocr = PaddleOCR(
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="PP-OCRv5_mobile_rec",
        
            device="cpu",
            enable_mkldnn=False,
            cpu_threads=4,
        
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        print(
            "[PERF] PaddleOCR model loading: "
            f"{time.perf_counter() - phase_started:.3f} s",
            flush=True,
        )
        print("PaddleOCR ready", flush=True)

    except Exception as error:
        ocr_error = error
        traceback.print_exc()
        print(
            f"PaddleOCR initialization failed: {error}",
            flush=True,
        )

    finally:
        print(
            "[PERF] PaddleOCR initialization total: "
            f"{time.perf_counter() - initialization_started:.3f} s",
            flush=True,
        )
        ocr_ready.set()


@app.get("/health")
def health():
    """Report that the Flask process is serving requests."""
    # Flask itself is alive.
    return {
        "status": "alive"
    }


@app.get("/ready")
def ready():
    """Report whether model initialization completed successfully."""
    if not ocr_ready.is_set():
        return {
            "status": "initializing"
        }, 503

    if ocr_error is not None:
        return {
            "status": "failed",
            "error": str(ocr_error),
        }, 500

    return {
        "status": "ready"
    }


@app.post("/ocr")
def recognize():
    """Decode one uploaded image and return OCR fragments and sharpness."""
    # TEMPORARY PERFORMANCE DIAGNOSTICS: remove after OCR profiling.
    request_started = time.perf_counter()

    # Connection succeeds immediately because Flask is already running.
    # If PaddleOCR is still loading, this request waits here.
    phase_started = time.perf_counter()
    if not ocr_ready.wait(timeout=300):
        return {
            "error": "OCR initialization timed out"
        }, 503
    ready_wait_seconds = time.perf_counter() - phase_started
    print(
        f"[PERF] OCR request - readiness wait: {ready_wait_seconds:.3f} s",
        flush=True,
    )

    if ocr_error is not None:
        return {
            "error": f"OCR initialization failed: {ocr_error}"
        }, 500

    if "image" not in request.files:
        return {
            "error": "No image supplied"
        }, 400

    phase_started = time.perf_counter()
    image_bytes = request.files["image"].read()
    upload_read_seconds = time.perf_counter() - phase_started
    print(
        "[PERF] OCR request - uploaded image read: "
        f"{upload_read_seconds:.3f} s ({len(image_bytes)} bytes)",
        flush=True,
    )

    phase_started = time.perf_counter()
    image = cv2.imdecode(
        np.frombuffer(image_bytes, dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )
    decode_seconds = time.perf_counter() - phase_started

    if image is None:
        return {
            "error": "Could not decode image"
        }, 400

    height, width = image.shape[:2]
    print(
        "[PERF] OCR request - image decode: "
        f"{decode_seconds:.3f} s ({width}x{height})",
        flush=True,
    )

    phase_started = time.perf_counter()
    # Materialize the result so this timing also covers inference if the
    # installed PaddleOCR version returns a lazy iterator.
    results = list(ocr.predict(image))
    predict_seconds = time.perf_counter() - phase_started
    print(
        "[PERF] OCR request - PaddleOCR predict "
        f"(detection + recognition): {predict_seconds:.3f} s",
        flush=True,
    )

    phase_started = time.perf_counter()
    lines = []
    fragments = []
    text_polygons = []

    for result in results:
        data = result.json
        data = data.get("res", data)

        texts = data.get("rec_texts", [])
        scores = data.get("rec_scores", [])

        for text, score in zip(texts, scores):
            confidence = float(score)
            lines.append(text)
            fragments.append({
                "text": text,
                "confidence": confidence,
            })

        polygons = data.get("rec_polys")
        if polygons is None:
            polygons = data.get("dt_polys", [])
        text_polygons.extend(polygons)
    result_processing_seconds = time.perf_counter() - phase_started
    print(
        "[PERF] OCR request - result extraction: "
        f"{result_processing_seconds:.3f} s "
        f"({len(fragments)} fragments, {len(text_polygons)} polygons)",
        flush=True,
    )

    # TEMPORARY DEBUG CODE: remove after OCR-region diagnostics are complete.
    phase_started = time.perf_counter()
    _save_detection_overlay(image, text_polygons)
    overlay_seconds = time.perf_counter() - phase_started
    print(
        "[PERF] OCR request - detection overlay: "
        f"{overlay_seconds:.3f} s",
        flush=True,
    )

    phase_started = time.perf_counter()
    text_sharpness = _text_region_sharpness(image, text_polygons)
    sharpness_seconds = time.perf_counter() - phase_started
    print(
        "[PERF] OCR request - text sharpness: "
        f"{sharpness_seconds:.3f} s",
        flush=True,
    )

    phase_started = time.perf_counter()
    response = jsonify({
        "text": "\n".join(lines),
        "lines": lines,
        "fragments": fragments,
        "text_sharpness": text_sharpness,
    })
    response_seconds = time.perf_counter() - phase_started
    total_seconds = time.perf_counter() - request_started
    print(
        "[PERF] OCR request - JSON response build: "
        f"{response_seconds:.3f} s",
        flush=True,
    )
    print(
        f"[PERF] OCR request - total server time: {total_seconds:.3f} s",
        flush=True,
    )
    return response


if __name__ == "__main__":
    # Create the OCR instance on the main thread.
    initialize_ocr()

    if ocr_error is not None:
        raise RuntimeError(
            f"OCR initialization failed: {ocr_error}"
        ) from ocr_error

    # Handle requests on that same thread.
    app.run(
        host="0.0.0.0",
        port=5000,
        threaded=False,
        use_reloader=False,
    )
