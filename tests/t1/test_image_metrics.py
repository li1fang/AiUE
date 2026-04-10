from __future__ import annotations

from pathlib import Path

from aiue_t1.image_metrics import compute_image_metrics


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "images"


def test_compute_image_metrics_returns_python_engine():
    metrics = compute_image_metrics(
        FIXTURE_ROOT / "before.ppm",
        FIXTURE_ROOT / "after.ppm",
        sample_width=4,
        sample_height=4,
        histogram_bins=4,
    )
    assert metrics["engine"] == "python_cv2"
    assert metrics["histogram_l1"] > 0.0
    assert metrics["mean_abs_pixel_delta"] > 0.0
    assert metrics["ssim"] is not None
    assert metrics["ssim"] < 1.0


def test_compute_image_metrics_honors_mask():
    metrics = compute_image_metrics(
        FIXTURE_ROOT / "before.ppm",
        FIXTURE_ROOT / "after_outside_mask.ppm",
        sample_width=4,
        sample_height=4,
        histogram_bins=4,
        mask_path=FIXTURE_ROOT / "mask.pgm",
    )
    assert metrics["mask_pixel_count"] == 4
    assert metrics["mean_abs_pixel_delta"] == 0.0
    assert metrics["histogram_l1"] == 0.0
