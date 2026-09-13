# Text-detection probability-map debugger

`debug_detection.py` runs the raw `PP-OCRv5_mobile_det` inference model and
stops before `DBPostProcess`. It therefore exposes the per-pixel probability
map that is normally hidden by PaddleOCR's high-level `predict()` API.

Run it from the repository root with the PaddleOCR virtual environment:

```sh
/home/li/venvs/paddleocr/bin/python tools/debug_detection.py IMAGE.jpg
```

The script automatically checks the model location currently used on this
machine. A different model directory can be supplied explicitly:

```sh
/home/li/venvs/paddleocr/bin/python tools/debug_detection.py IMAGE.jpg \
  --model-dir /path/to/PP-OCRv5_mobile_det_infer
```

To compare other binarization thresholds:

```sh
/home/li/venvs/paddleocr/bin/python tools/debug_detection.py IMAGE.jpg \
  --thresholds 0.1 0.2 0.3 0.4 0.5
```

By default, files are written to `debug_output/<image-name>/`:

- `probability_map.npy`: exact `float32` model output, before postprocessing.
- `probability_map.png`: grayscale visualization at detector resolution.
- `probability_heatmap.png`: colour visualization resized to the photograph.
- `overlay.png`: heatmap over the original photograph.
- `threshold_NNN.png`: binary masks for the requested thresholds.
- `detector_input.png`: resized image actually passed to the model.
- `sharpness_map.png`: visualization of edges measured by the Laplacian.
- `metadata.json`: preprocessing details, shapes, statistics and percentiles.

The default binary masks use thresholds `0.01`, `0.05`, `0.1`, `0.2`, `0.3`,
`0.4`, `0.5`, `0.6`, `0.7` and `0.8`.

The PNG files are visual aids. Use `probability_map.npy` when analysing exact
values because resizing and conversion to 8-bit images alter the data.

The terminal and `metadata.json` also report two sharpness measurements using
the variance of the Laplacian:

- `global`: calculated over the complete photograph.
- `detected_text_regions`: calculated only where the detection probability is
  at least `0.3` by default.

Higher values normally indicate sharper edges. These values depend heavily on
the camera, resolution, lighting, noise and text size, so the acceptance
threshold must be calibrated using good and bad photographs from the same
capture setup. Change the text-region mask with
`--sharpness-mask-threshold VALUE`.

For example, inspect the saved array with:

```python
import numpy as np

probabilities = np.load("debug_output/IMAGE/probability_map.npy")
print(probabilities.shape)
print(probabilities.min(), probabilities.max(), probabilities.mean())
print(probabilities[100, 200])
```
