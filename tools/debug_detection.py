#!/usr/bin/env python3
"""Inspect the raw PP-OCRv5 text-detection probability map.

This tool runs only the detection model. It intentionally stops before
DBPostProcess so the saved ``probability_map.npy`` contains the exact values
produced by the neural network.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
import paddle.inference as paddle_infer


DEFAULT_THRESHOLDS = (0.01, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
MEAN = np.asarray((0.485, 0.456, 0.406), dtype=np.float32)
STD = np.asarray((0.229, 0.224, 0.225), dtype=np.float32)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run PP-OCRv5_mobile_det without DBPostProcess and export its "
            "raw probability map and visualizations."
        )
    )
    parser.add_argument("image", type=Path, help="Input image to analyse")
    parser.add_argument(
        "--model-dir",
        type=Path,
        help=(
            "Directory containing inference.json (or inference.pdmodel) and "
            "inference.pdiparams. If omitted, common PaddleOCR cache paths "
            "and PADDLEOCR_DET_MODEL_DIR are checked."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory (default: debug_output/<image-name>)",
    )
    parser.add_argument(
        "--thresholds",
        type=float,
        nargs="+",
        default=list(DEFAULT_THRESHOLDS),
        help=(
            "Threshold masks to export "
            "(default: 0.01 0.05 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8)"
        ),
    )
    parser.add_argument(
        "--limit-side-len",
        type=int,
        default=960,
        help="Maximum image side used by the detector (default: 960)",
    )
    parser.add_argument(
        "--max-side-limit",
        type=int,
        default=4000,
        help="Absolute maximum resized side (default: 4000)",
    )
    parser.add_argument(
        "--cpu-threads",
        type=int,
        default=4,
        help="CPU inference threads (default: 4)",
    )
    parser.add_argument(
        "--sharpness-mask-threshold",
        type=float,
        default=0.3,
        help=(
            "Detection probability used to select text pixels for the "
            "text-region sharpness metric (default: 0.3)"
        ),
    )
    return parser.parse_args()


def find_model_dir(explicit: Path | None) -> Path:
    if explicit is not None:
        candidates = [explicit.expanduser()]
    else:
        candidates = []
        environment_path = os.environ.get("PADDLEOCR_DET_MODEL_DIR")
        if environment_path:
            candidates.append(Path(environment_path).expanduser())
        candidates.extend(
            [
                Path.home()
                / "paddleocr_models"
                / "PP-OCRv5_mobile_det_infer",
                Path.home()
                / ".paddlex"
                / "official_models"
                / "PP-OCRv5_mobile_det",
                Path("/models/official_models/PP-OCRv5_mobile_det"),
                Path("/models/PP-OCRv5_mobile_det"),
            ]
        )

    for candidate in candidates:
        if (
            candidate.is_dir()
            and (candidate / "inference.pdiparams").is_file()
            and (
                (candidate / "inference.json").is_file()
                or (candidate / "inference.pdmodel").is_file()
            )
        ):
            return candidate.resolve()

    searched = "\n".join(f"  - {path}" for path in candidates)
    raise FileNotFoundError(
        "Could not find the PP-OCRv5 detection model. Checked:\n"
        f"{searched}\n"
        "Pass its directory explicitly with --model-dir."
    )


def resize_for_detection(
    image: np.ndarray,
    limit_side_len: int,
    max_side_limit: int,
) -> tuple[np.ndarray, tuple[float, float]]:
    """Match PaddleX DetResizeForTest with limit_type='max'."""
    original_height, original_width = image.shape[:2]
    working_image = image

    if original_height + original_width < 64:
        padded_height = max(32, original_height)
        padded_width = max(32, original_width)
        working_image = np.zeros(
            (padded_height, padded_width, image.shape[2]), dtype=np.uint8
        )
        working_image[:original_height, :original_width] = image

    height, width = working_image.shape[:2]
    ratio = min(1.0, float(limit_side_len) / max(height, width))
    resize_height = int(height * ratio)
    resize_width = int(width * ratio)

    if max(resize_height, resize_width) > max_side_limit:
        ratio = float(max_side_limit) / max(resize_height, resize_width)
        resize_height = int(resize_height * ratio)
        resize_width = int(resize_width * ratio)

    resize_height = max(int(round(resize_height / 32) * 32), 32)
    resize_width = max(int(round(resize_width / 32) * 32), 32)

    if (resize_height, resize_width) == (height, width):
        resized = working_image
    else:
        resized = cv2.resize(working_image, (resize_width, resize_height))

    ratio_height = resize_height / float(original_height)
    ratio_width = resize_width / float(original_width)
    return resized, (ratio_height, ratio_width)


def prepare_input(image: np.ndarray) -> np.ndarray:
    normalized = image.astype(np.float32) / 255.0
    normalized = (normalized - MEAN) / STD
    return np.ascontiguousarray(normalized.transpose(2, 0, 1)[None, ...])


def create_predictor(model_dir: Path, cpu_threads: int):
    model_file = model_dir / "inference.json"
    if not model_file.is_file():
        model_file = model_dir / "inference.pdmodel"

    config = paddle_infer.Config(
        str(model_file),
        str(model_dir / "inference.pdiparams"),
    )
    config.disable_gpu()
    config.disable_mkldnn()
    config.set_cpu_math_library_num_threads(cpu_threads)
    config.disable_glog_info()
    return paddle_infer.create_predictor(config)


def run_detector(predictor, tensor: np.ndarray) -> tuple[np.ndarray, str, str]:
    input_names = predictor.get_input_names()
    output_names = predictor.get_output_names()
    if len(input_names) != 1 or len(output_names) != 1:
        raise RuntimeError(
            "Expected one model input and one output, got "
            f"inputs={input_names}, outputs={output_names}"
        )

    input_name = input_names[0]
    output_name = output_names[0]
    predictor.get_input_handle(input_name).copy_from_cpu(tensor)
    predictor.run()
    output = np.asarray(
        predictor.get_output_handle(output_name).copy_to_cpu()
    )

    if output.ndim == 4 and output.shape[0] == 1 and output.shape[1] == 1:
        probability_map = output[0, 0]
    elif output.ndim == 3 and output.shape[0] == 1:
        probability_map = output[0]
    else:
        raise RuntimeError(
            "Unexpected detector output shape: "
            f"{output.shape}; expected [1, 1, H, W]"
        )

    return probability_map.astype(np.float32, copy=False), input_name, output_name


def write_image(path: Path, image: np.ndarray) -> None:
    if not cv2.imwrite(str(path), image):
        raise OSError(f"Could not write image: {path}")


def threshold_filename(threshold: float) -> str:
    return f"threshold_{round(threshold * 100):03d}.png"


def export_debug_files(
    output_dir: Path,
    original: np.ndarray,
    resized: np.ndarray,
    probability_map: np.ndarray,
    thresholds: Sequence[float],
    sharpness_mask_threshold: float,
    metadata: dict,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    np.save(output_dir / "probability_map.npy", probability_map)
    write_image(output_dir / "detector_input.png", resized)

    display_probability = np.clip(probability_map, 0.0, 1.0)
    grayscale = np.rint(display_probability * 255).astype(np.uint8)
    write_image(output_dir / "probability_map.png", grayscale)

    original_height, original_width = original.shape[:2]
    probability_original_size = cv2.resize(
        display_probability,
        (original_width, original_height),
        interpolation=cv2.INTER_LINEAR,
    )

    gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    global_sharpness = float(laplacian.var())
    text_mask = probability_original_size >= sharpness_mask_threshold
    detected_text_sharpness = (
        float(laplacian[text_mask].var())
        if np.any(text_mask)
        else None
    )

    absolute_laplacian = np.abs(laplacian)
    visualization_limit = float(np.percentile(absolute_laplacian, 99.5))
    if visualization_limit > 0:
        sharpness_map = np.clip(
            absolute_laplacian * (255.0 / visualization_limit),
            0,
            255,
        ).astype(np.uint8)
    else:
        sharpness_map = np.zeros_like(gray)
    write_image(output_dir / "sharpness_map.png", sharpness_map)

    heatmap = cv2.applyColorMap(
        np.rint(probability_original_size * 255).astype(np.uint8),
        cv2.COLORMAP_JET,
    )
    overlay = cv2.addWeighted(original, 0.60, heatmap, 0.40, 0.0)
    write_image(output_dir / "probability_heatmap.png", heatmap)
    write_image(output_dir / "overlay.png", overlay)

    threshold_statistics = {}
    for threshold in thresholds:
        mask = (probability_map >= threshold).astype(np.uint8) * 255
        mask_original_size = cv2.resize(
            mask,
            (original_width, original_height),
            interpolation=cv2.INTER_NEAREST,
        )
        filename = threshold_filename(threshold)
        write_image(output_dir / filename, mask_original_size)
        selected = int(np.count_nonzero(mask))
        threshold_statistics[f"{threshold:.6g}"] = {
            "selected_pixels": selected,
            "selected_percent": 100.0 * selected / mask.size,
            "file": filename,
        }

    values = probability_map.astype(np.float64, copy=False)
    metadata["probability_statistics"] = {
        "minimum": float(values.min()),
        "maximum": float(values.max()),
        "mean": float(values.mean()),
        "standard_deviation": float(values.std()),
        "percentiles": {
            str(percentile): float(np.percentile(values, percentile))
            for percentile in (1, 5, 25, 50, 75, 95, 99)
        },
        "thresholds": threshold_statistics,
    }
    metadata["sharpness"] = {
        "method": "variance_of_laplacian",
        "global": global_sharpness,
        "detected_text_regions": detected_text_sharpness,
        "text_mask_probability_threshold": sharpness_mask_threshold,
        "text_mask_selected_pixels": int(np.count_nonzero(text_mask)),
        "text_mask_selected_percent": (
            100.0 * np.count_nonzero(text_mask) / text_mask.size
        ),
        "visualization": "sharpness_map.png",
        "note": (
            "Values are camera- and resolution-dependent; compare images "
            "captured with the same setup."
        ),
    }

    with (output_dir / "metadata.json").open("w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2, ensure_ascii=False)
        file.write("\n")

    return metadata["probability_statistics"]


def main() -> None:
    args = parse_args()

    if args.limit_side_len <= 0 or args.max_side_limit <= 0:
        raise ValueError("Image-size limits must be positive")
    if args.cpu_threads <= 0:
        raise ValueError("--cpu-threads must be positive")
    if any(not 0.0 <= threshold <= 1.0 for threshold in args.thresholds):
        raise ValueError("All thresholds must be between 0 and 1")
    if not 0.0 <= args.sharpness_mask_threshold <= 1.0:
        raise ValueError("--sharpness-mask-threshold must be between 0 and 1")

    image_path = args.image.expanduser().resolve()
    original = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if original is None:
        raise ValueError(f"Could not decode input image: {image_path}")

    model_dir = find_model_dir(args.model_dir)
    output_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir is not None
        else (Path.cwd() / "debug_output" / image_path.stem).resolve()
    )

    resized, resize_ratios = resize_for_detection(
        original,
        limit_side_len=args.limit_side_len,
        max_side_limit=args.max_side_limit,
    )
    tensor = prepare_input(resized)
    predictor = create_predictor(model_dir, args.cpu_threads)
    probability_map, input_name, output_name = run_detector(predictor, tensor)

    metadata = {
        "image": str(image_path),
        "model_directory": str(model_dir),
        "model_input_name": input_name,
        "model_output_name": output_name,
        "original_shape_hwc": list(original.shape),
        "detector_input_shape_nchw": list(tensor.shape),
        "probability_map_shape_hw": list(probability_map.shape),
        "resize_ratio_height_width": list(resize_ratios),
        "preprocessing": {
            "colour_order": "BGR",
            "limit_type": "max",
            "limit_side_len": args.limit_side_len,
            "max_side_limit": args.max_side_limit,
            "dimension_multiple": 32,
            "mean": MEAN.tolist(),
            "standard_deviation": STD.tolist(),
            "scale": "1/255",
        },
    }
    statistics = export_debug_files(
        output_dir,
        original,
        resized,
        probability_map,
        args.thresholds,
        args.sharpness_mask_threshold,
        metadata,
    )

    print(f"Debug output: {output_dir}")
    print(f"Probability-map shape: {tuple(probability_map.shape)}")
    print(
        "Probability range: "
        f"{statistics['minimum']:.6f} .. {statistics['maximum']:.6f}"
    )
    print(f"Mean probability: {statistics['mean']:.6f}")
    sharpness = metadata["sharpness"]
    print(f"Global sharpness (Laplacian variance): {sharpness['global']:.3f}")
    if sharpness["detected_text_regions"] is None:
        print("Detected-text sharpness: unavailable (empty text mask)")
    else:
        print(
            "Detected-text sharpness "
            f"(probability >= {args.sharpness_mask_threshold:g}): "
            f"{sharpness['detected_text_regions']:.3f}"
        )
    for threshold, values in statistics["thresholds"].items():
        print(
            f"Pixels >= {threshold}: "
            f"{values['selected_percent']:.3f}%"
        )


if __name__ == "__main__":
    main()
