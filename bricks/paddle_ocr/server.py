from flask import Flask, request, jsonify

import cv2
import numpy as np
import threading
import traceback


app = Flask(__name__)

ocr = None
ocr_error = None
ocr_ready = threading.Event()


MIN_REGION_AREA_RATIO = 0.02


def _weighted_median(values, weights):
    """Return the median of values, using the corresponding areas as weights."""
    order = np.argsort(values)
    sorted_values = np.asarray(values, dtype=np.float64)[order]
    sorted_weights = np.asarray(weights, dtype=np.float64)[order]
    midpoint = sorted_weights.sum() / 2.0
    index = np.searchsorted(np.cumsum(sorted_weights), midpoint, side="left")
    return float(sorted_values[min(index, len(sorted_values) - 1)])


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
    global ocr, ocr_error

    try:
        print("Importing PaddleOCR...", flush=True)
        from paddleocr import PaddleOCR

        print("Loading OCR models...", flush=True)

        print(
            "OCR configuration: CPU, MKL-DNN disabled, 1 inference thread",
            flush=True,
        )
        
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
        print("PaddleOCR ready", flush=True)

    except Exception as error:
        ocr_error = error
        traceback.print_exc()
        print(
            f"PaddleOCR initialization failed: {error}",
            flush=True,
        )

    finally:
        ocr_ready.set()


@app.get("/health")
def health():
    # Flask itself is alive.
    return {
        "status": "alive"
    }


@app.get("/ready")
def ready():
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
    # Connection succeeds immediately because Flask is already running.
    # If PaddleOCR is still loading, this request waits here.
    if not ocr_ready.wait(timeout=300):
        return {
            "error": "OCR initialization timed out"
        }, 503

    if ocr_error is not None:
        return {
            "error": f"OCR initialization failed: {ocr_error}"
        }, 500

    if "image" not in request.files:
        return {
            "error": "No image supplied"
        }, 400

    image_bytes = request.files["image"].read()

    image = cv2.imdecode(
        np.frombuffer(image_bytes, dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )

    if image is None:
        return {
            "error": "Could not decode image"
        }, 400

    results = ocr.predict(image)

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

    text_sharpness = _text_region_sharpness(image, text_polygons)

    return jsonify({
        "text": "\n".join(lines),
        "lines": lines,
        "fragments": fragments,
        "text_sharpness": text_sharpness,
    })


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
