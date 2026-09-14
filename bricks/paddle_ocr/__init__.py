import time

import requests


BASE_URL = "http://paddle_ocr_service:5000"


def wait_until_ready(timeout: float = 600) -> None:
    deadline = time.monotonic() + timeout
    last_status = "Service has not responded"
    previous_status = None

    while time.monotonic() < deadline:
        try:
            response = requests.get(
                f"{BASE_URL}/ready",
                timeout=(3, 5),
            )
        except (requests.ConnectionError, requests.Timeout) as error:
            last_status = f"Waiting for OCR service: {error}"
        else:
            if response.status_code == 200:
                return

            if response.status_code != 503:
                raise RuntimeError(
                    "OCR service failed its readiness check: "
                    f"HTTP {response.status_code}: {response.text}"
                )

            last_status = f"OCR is initializing: {response.text.strip()}"

        if last_status != previous_status:
            print(last_status, flush=True)
            previous_status = last_status

        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(2, remaining))

    raise TimeoutError(
        f"OCR service did not become ready within {timeout}s. "
        f"Last status: {last_status}"
    )


def recognize(image: bytes) -> tuple[str, float | None]:
    # TEMPORARY PERFORMANCE DIAGNOSTICS: remove after OCR profiling.
    total_started = time.perf_counter()

    phase_started = time.perf_counter()
    wait_until_ready()
    print(
        "[PERF] OCR client - readiness check: "
        f"{time.perf_counter() - phase_started:.3f} s",
        flush=True,
    )

    phase_started = time.perf_counter()
    response = requests.post(
        f"{BASE_URL}/ocr",
        files={
            "image": (
                "image.jpg",
                image,
                "image/jpeg",
            )
        },
        timeout=(5, 300),
    )
    print(
        "[PERF] OCR client - HTTP request including server processing: "
        f"{time.perf_counter() - phase_started:.3f} s",
        flush=True,
    )

    if not response.ok:
        raise RuntimeError(
            f"OCR request failed: HTTP {response.status_code}: "
            f"{response.text}"
        )

    phase_started = time.perf_counter()
    data = response.json()
    print(
        "[PERF] OCR client - JSON response decode: "
        f"{time.perf_counter() - phase_started:.3f} s",
        flush=True,
    )

    for fragment in data.get("fragments", []):
        text = fragment["text"]
        confidence = fragment["confidence"]
        print(
            f'[OCR] {confidence:.1%} | "{text}"',
            flush=True,
        )

    text_sharpness = data.get("text_sharpness")
    if text_sharpness is not None:
        text_sharpness = float(text_sharpness)

    print(
        "[PERF] OCR client - total: "
        f"{time.perf_counter() - total_started:.3f} s",
        flush=True,
    )

    return data["text"], text_sharpness
