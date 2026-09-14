#!/usr/bin/env python3
"""Temporarily record a reproducible CPU baseline for the OCR service."""

import argparse
import hashlib
import json
import mimetypes
import platform
import statistics
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _request_json(request, timeout):
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"HTTP {error.code} from {request.full_url}: {detail}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Could not reach {request.full_url}: {error.reason}"
        ) from error


def _wait_until_ready(base_url, timeout):
    deadline = time.monotonic() + timeout
    ready_url = f"{base_url.rstrip('/')}/ready"
    last_error = "service has not responded"

    while time.monotonic() < deadline:
        request = urllib.request.Request(ready_url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if response.status == 200 and payload.get("status") == "ready":
                    return
        except urllib.error.HTTPError as error:
            last_error = f"HTTP {error.code}"
            if error.code != 503:
                detail = error.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"OCR readiness check failed: HTTP {error.code}: {detail}"
                ) from error
        except urllib.error.URLError as error:
            last_error = str(error.reason)

        time.sleep(2)

    raise TimeoutError(
        f"OCR service was not ready after {timeout:.0f} s: {last_error}"
    )


def _recognize(base_url, image_path, timeout):
    image_bytes = image_path.read_bytes()
    boundary = f"brailleq-{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; '
        f'filename="{image_path.name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8")
    body = header + image_bytes + f"\r\n--{boundary}--\r\n".encode("ascii")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/ocr",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    started = time.perf_counter()
    payload = _request_json(request, timeout)
    client_seconds = time.perf_counter() - started

    performance = payload.get("debug_performance")
    if not isinstance(performance, dict):
        raise RuntimeError(
            "The OCR response has no debug_performance object. "
            "Rebuild the instrumented PaddleOCR Brick before benchmarking."
        )

    return {
        "image": image_path.name,
        "image_sha256": hashlib.sha256(image_bytes).hexdigest(),
        "client_seconds": client_seconds,
        "text": payload.get("text", ""),
        "fragments": payload.get("fragments", []),
        "text_sharpness": payload.get("text_sharpness"),
        "server": performance,
    }


def _measurement(record, name):
    if name == "client":
        return float(record["client_seconds"])
    return float(record["server"]["seconds"][name])


def _summary(records):
    metric_names = (
        "client",
        "before_response",
        "predict",
        "decode",
        "result_extraction",
        "overlay",
        "text_sharpness",
    )
    summaries = {}

    for image_name in sorted({record["image"] for record in records}):
        image_records = [
            record for record in records if record["image"] == image_name
        ]
        metrics = {}
        for metric_name in metric_names:
            values = [
                _measurement(record, metric_name)
                for record in image_records
            ]
            metrics[metric_name] = {
                "minimum": min(values),
                "median": statistics.median(values),
                "mean": statistics.mean(values),
                "maximum": max(values),
            }

        latest = image_records[-1]
        summaries[image_name] = {
            "runs": len(image_records),
            "image_sha256": latest["image_sha256"],
            "image": latest["server"]["image"],
            "fragment_count": latest["server"]["fragment_count"],
            "polygon_count": latest["server"]["polygon_count"],
            "text": latest["text"],
            "text_sharpness": latest["text_sharpness"],
            "seconds": metrics,
        }

    return summaries


def _parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark the current PaddlePaddle CPU OCR service using a fixed "
            "set of images."
        )
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        required=True,
        help="Directory containing the baseline images.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:5000",
        help="OCR service URL (default: %(default)s).",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Measured runs per image (default: %(default)s).",
    )
    parser.add_argument(
        "--warmups",
        type=int,
        default=1,
        help="Unrecorded warm-up requests (default: %(default)s).",
    )
    parser.add_argument(
        "--ready-timeout",
        type=float,
        default=600,
        help="Seconds to wait for model initialization (default: %(default)s).",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=300,
        help="Timeout for one OCR request (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/captures/benchmarks/cpu_baseline.json"),
        help="Output JSON path (default: %(default)s).",
    )
    args = parser.parse_args()

    if args.runs <= 0:
        parser.error("--runs must be greater than zero")
    if args.warmups < 0:
        parser.error("--warmups cannot be negative")
    if args.ready_timeout <= 0 or args.request_timeout <= 0:
        parser.error("timeouts must be greater than zero")

    return args


def main():
    args = _parse_args()
    images = sorted(
        path
        for path in args.image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    if not images:
        raise SystemExit(f"No supported images found in {args.image_dir}")

    print(f"[BASELINE] Waiting for {args.base_url}", flush=True)
    _wait_until_ready(args.base_url, args.ready_timeout)

    for warmup_index in range(args.warmups):
        print(
            f"[BASELINE] Warm-up {warmup_index + 1}/{args.warmups}: "
            f"{images[0].name}",
            flush=True,
        )
        _recognize(args.base_url, images[0], args.request_timeout)

    records = []
    for run_index in range(args.runs):
        for image_path in images:
            record = _recognize(args.base_url, image_path, args.request_timeout)
            record["run"] = run_index + 1
            records.append(record)
            server = record["server"]
            print(
                f"[BASELINE] run={run_index + 1}/{args.runs} "
                f"image={image_path.name} "
                f"client={record['client_seconds']:.3f}s "
                f"predict={server['seconds']['predict']:.3f}s "
                f"fragments={server['fragment_count']} "
                f"polygons={server['polygon_count']}",
                flush=True,
            )

    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Temporary CPU baseline before GPU OCR migration",
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "base_url": args.base_url,
        },
        "configuration": {
            "runs": args.runs,
            "warmups": args.warmups,
            "image_directory": str(args.image_dir),
        },
        "summary_by_image": _summary(records),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[BASELINE] Report saved to {args.output}", flush=True)


if __name__ == "__main__":
    main()
