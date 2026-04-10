from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity


def _resolve_crop_rect(image_width: int, image_height: int, crop_rect: dict | None) -> dict:
    full_rect = {"x": 0, "y": 0, "width": int(image_width), "height": int(image_height)}
    if not isinstance(crop_rect, dict):
        return full_rect
    try:
        requested_width = float(crop_rect.get("width", -1))
        requested_height = float(crop_rect.get("height", -1))
    except Exception:
        return full_rect
    if requested_width <= 1 or requested_height <= 1:
        return full_rect
    x0 = max(0, int(np.floor(float(crop_rect.get("x", 0)))))
    y0 = max(0, int(np.floor(float(crop_rect.get("y", 0)))))
    x1 = min(int(image_width), int(np.ceil(float(crop_rect.get("x", 0)) + requested_width)))
    y1 = min(int(image_height), int(np.ceil(float(crop_rect.get("y", 0)) + requested_height)))
    if x1 <= x0 or y1 <= y0:
        return full_rect
    return {
        "x": x0,
        "y": y0,
        "width": int(x1 - x0),
        "height": int(y1 - y0),
    }


def _load_color_image(path: str | Path) -> Image.Image:
    resolved = Path(path).expanduser().resolve()
    with Image.open(resolved) as handle:
        return handle.convert("RGB")


def _load_mask(path: str | Path, crop_rect: dict, sample_width: int, sample_height: int) -> tuple[np.ndarray, int]:
    resolved = Path(path).expanduser().resolve()
    with Image.open(resolved) as handle:
        mask = handle.convert("L")
        cropped = mask.crop(
            (
                crop_rect["x"],
                crop_rect["y"],
                crop_rect["x"] + crop_rect["width"],
                crop_rect["y"] + crop_rect["height"],
            )
        )
        resized = cropped.resize((sample_width, sample_height), Image.Resampling.NEAREST)
    binary = (np.asarray(resized) > 0).astype(np.uint8)
    return binary, int(np.count_nonzero(binary))


def _luma(image_rgb: np.ndarray) -> np.ndarray:
    r = image_rgb[:, :, 0].astype(np.float32)
    g = image_rgb[:, :, 1].astype(np.float32)
    b = image_rgb[:, :, 2].astype(np.float32)
    return np.rint((0.299 * r) + (0.587 * g) + (0.114 * b)).astype(np.float32)


def compute_image_metrics(
    before_path: str | Path,
    after_path: str | Path,
    *,
    sample_width: int = 160,
    sample_height: int = 90,
    histogram_bins: int = 32,
    crop_rect: dict | None = None,
    mask_path: str | Path | None = None,
) -> dict:
    before_resolved = Path(before_path).expanduser().resolve()
    after_resolved = Path(after_path).expanduser().resolve()
    before_image = _load_color_image(before_resolved)
    after_image = _load_color_image(after_resolved)
    original_width, original_height = before_image.size
    resolved_crop_rect = _resolve_crop_rect(original_width, original_height, crop_rect)

    crop_box = (
        resolved_crop_rect["x"],
        resolved_crop_rect["y"],
        resolved_crop_rect["x"] + resolved_crop_rect["width"],
        resolved_crop_rect["y"] + resolved_crop_rect["height"],
    )
    before_cropped = before_image.crop(crop_box)
    after_cropped = after_image.crop(crop_box)

    before_scaled = before_cropped.resize((sample_width, sample_height), Image.Resampling.BICUBIC)
    after_scaled = after_cropped.resize((sample_width, sample_height), Image.Resampling.BICUBIC)
    before_luma = _luma(np.asarray(before_scaled))
    after_luma = _luma(np.asarray(after_scaled))

    mask = None
    mask_pixel_count = 0
    if str(mask_path or "").strip():
        mask, mask_pixel_count = _load_mask(mask_path, resolved_crop_rect, sample_width, sample_height)
        active_mask = mask.astype(bool)
        before_luma = np.where(active_mask, before_luma, 0.0)
        after_luma = np.where(active_mask, after_luma, 0.0)
        active_before = before_luma[active_mask]
        active_after = after_luma[active_mask]
    else:
        active_before = before_luma.reshape(-1)
        active_after = after_luma.reshape(-1)

    histogram_bins = max(4, int(histogram_bins))
    pixel_count = int(sample_width * sample_height)
    effective_pixel_count = int(active_before.size)
    if effective_pixel_count <= 0:
        active_before = np.zeros((1,), dtype=np.float32)
        active_after = np.zeros((1,), dtype=np.float32)
        effective_pixel_count = 0

    hist_before, _ = np.histogram(active_before, bins=histogram_bins, range=(0.0, 256.0))
    hist_after, _ = np.histogram(active_after, bins=histogram_bins, range=(0.0, 256.0))
    normalization = float(max(effective_pixel_count, 1))
    histogram_l1 = float(np.abs((hist_before / normalization) - (hist_after / normalization)).sum())

    mean_abs_pixel_delta = float(np.abs(active_after - active_before).mean() / 255.0)
    mean_luma_before = float(active_before.mean()) if active_before.size else 0.0
    mean_luma_after = float(active_after.mean()) if active_after.size else 0.0

    ssim_value = None
    try:
        min_dimension = int(min(before_luma.shape[0], before_luma.shape[1]))
        win_size = min(7, min_dimension)
        if win_size % 2 == 0:
            win_size -= 1
        if win_size < 3:
            win_size = 3
        ssim_value = float(
            structural_similarity(
                before_luma / 255.0,
                after_luma / 255.0,
                data_range=1.0,
                win_size=win_size,
            )
        )
    except Exception:
        ssim_value = None

    return {
        "before_path": str(before_resolved),
        "after_path": str(after_resolved),
        "mask_path": str(Path(mask_path).expanduser().resolve()) if str(mask_path or "").strip() else "",
        "engine": "python_cv2",
        "crop_rect": resolved_crop_rect,
        "original_width": int(original_width),
        "original_height": int(original_height),
        "sample_width": int(sample_width),
        "sample_height": int(sample_height),
        "pixel_count": int(pixel_count),
        "effective_pixel_count": int(effective_pixel_count),
        "mask_pixel_count": int(mask_pixel_count),
        "mask_ratio": float(mask_pixel_count / pixel_count) if pixel_count else 0.0,
        "histogram_bins": int(histogram_bins),
        "histogram_l1": histogram_l1,
        "mean_abs_pixel_delta": mean_abs_pixel_delta,
        "mean_luma_before": mean_luma_before,
        "mean_luma_after": mean_luma_after,
        "ssim": ssim_value,
    }
