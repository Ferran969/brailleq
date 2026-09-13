from flask import Flask, request, jsonify

import cv2
import numpy as np
import threading
import traceback


app = Flask(__name__)

ocr = None
ocr_error = None
ocr_ready = threading.Event()


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

    return jsonify({
        "text": "\n".join(lines),
        "lines": lines,
        "fragments": fragments,
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
