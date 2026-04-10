from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from aiue_t1.q5a_visible_conflict import analyze_visible_conflict


def _write_image(path: Path, image_rgb: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR))


def _base_images(size: int = 200) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    body = np.zeros((size, size, 3), dtype=np.uint8)
    slot = np.zeros((size, size, 3), dtype=np.uint8)
    combined = np.zeros((size, size, 3), dtype=np.uint8)
    body[:, :] = (0, 255, 0)
    slot[50:150, 70:130] = (255, 0, 0)
    combined[:, :] = (0, 255, 0)
    combined[50:150, 70:130] = (255, 0, 0)
    return body, slot, combined


def test_visible_conflict_passes_with_clear_slot(tmp_path: Path):
    body, slot, combined = _base_images()
    body_path = tmp_path / "body.png"
    slot_path = tmp_path / "slot.png"
    combined_path = tmp_path / "combined.png"
    overlay_path = tmp_path / "overlay.png"
    _write_image(body_path, body)
    _write_image(slot_path, slot)
    _write_image(combined_path, combined)

    result = analyze_visible_conflict(
        body_only_image_path=body_path,
        slot_only_image_path=slot_path,
        combined_visible_image_path=combined_path,
        debug_overlay_path=overlay_path,
    )

    assert result["status"] == "pass"
    assert result["failed_requirements"] == []
    assert result["metrics"]["slot_core_pixels"] >= 400
    assert result["metrics"]["slot_visible_ratio_in_core"] >= 0.75
    assert Path(result["debug_overlay_path"]).exists()


def test_visible_conflict_detects_slot_core_too_small(tmp_path: Path):
    body, slot, combined = _base_images()
    slot[:, :] = 0
    combined[:, :] = (0, 255, 0)
    slot[90:105, 95:110] = (255, 0, 0)
    combined[90:105, 95:110] = (255, 0, 0)
    body_path = tmp_path / "body.png"
    slot_path = tmp_path / "slot.png"
    combined_path = tmp_path / "combined.png"
    _write_image(body_path, body)
    _write_image(slot_path, slot)
    _write_image(combined_path, combined)

    result = analyze_visible_conflict(
        body_only_image_path=body_path,
        slot_only_image_path=slot_path,
        combined_visible_image_path=combined_path,
    )

    assert result["status"] == "fail"
    assert "slot_core_too_small" in result["failed_requirements"]


def test_visible_conflict_detects_slot_visibility_insufficient(tmp_path: Path):
    body, slot, combined = _base_images()
    combined[50:150, 70:130] = (0, 255, 0)
    combined[50:150, 70:90] = (255, 0, 0)
    body_path = tmp_path / "body.png"
    slot_path = tmp_path / "slot.png"
    combined_path = tmp_path / "combined.png"
    _write_image(body_path, body)
    _write_image(slot_path, slot)
    _write_image(combined_path, combined)

    result = analyze_visible_conflict(
        body_only_image_path=body_path,
        slot_only_image_path=slot_path,
        combined_visible_image_path=combined_path,
    )

    assert result["status"] == "fail"
    assert "slot_visibility_insufficient" in result["failed_requirements"]


def test_visible_conflict_detects_body_intrusion(tmp_path: Path):
    body, slot, combined = _base_images()
    combined[50:150, 70:130] = (255, 0, 0)
    combined[75:145, 90:120] = (0, 255, 0)
    body_path = tmp_path / "body.png"
    slot_path = tmp_path / "slot.png"
    combined_path = tmp_path / "combined.png"
    _write_image(body_path, body)
    _write_image(slot_path, slot)
    _write_image(combined_path, combined)

    result = analyze_visible_conflict(
        body_only_image_path=body_path,
        slot_only_image_path=slot_path,
        combined_visible_image_path=combined_path,
    )

    assert result["status"] == "fail"
    assert "body_intrusion_exceeded" in result["failed_requirements"]


def test_visible_conflict_reports_missing_or_bad_images(tmp_path: Path):
    body, slot, combined = _base_images()
    body_path = tmp_path / "body.png"
    slot_path = tmp_path / "slot.png"
    combined_path = tmp_path / "combined.png"
    _write_image(body_path, body)
    _write_image(slot_path, slot)
    combined_path.write_text("not an image", encoding="utf-8")

    result = analyze_visible_conflict(
        body_only_image_path=body_path,
        slot_only_image_path=slot_path,
        combined_visible_image_path=combined_path,
    )

    assert result["status"] == "fail"
    assert "mask_decode_failed" in result["failed_requirements"]

    missing_result = analyze_visible_conflict(
        body_only_image_path=body_path,
        slot_only_image_path=slot_path,
        combined_visible_image_path=tmp_path / "missing.png",
    )
    assert missing_result["status"] == "fail"
    assert "mask_capture_failed" in missing_result["failed_requirements"]


def test_visible_conflict_falls_back_to_silhouette_masks(tmp_path: Path):
    size = 220
    background = np.full((size, size, 3), (96, 72, 160), dtype=np.uint8)
    body = background.copy()
    slot = background.copy()
    combined = background.copy()
    body[45:190, 75:145] = (0, 0, 0)
    slot[50:145, 130:185] = (0, 0, 0)
    combined[45:190, 75:145] = (0, 0, 0)
    combined[50:145, 130:185] = (0, 0, 0)

    body_path = tmp_path / "body.png"
    slot_path = tmp_path / "slot.png"
    combined_path = tmp_path / "combined.png"
    _write_image(body_path, body)
    _write_image(slot_path, slot)
    _write_image(combined_path, combined)

    result = analyze_visible_conflict(
        body_only_image_path=body_path,
        slot_only_image_path=slot_path,
        combined_visible_image_path=combined_path,
    )

    assert result["status"] == "pass"
    assert result["mask_extraction_mode"] == "silhouette_fallback"
    assert result["metrics"]["slot_mask_coverage_ratio"] >= 0.001
    assert result["metrics"]["slot_visible_ratio_in_core"] >= 0.75


def test_visible_conflict_detects_tonemapped_color_masks(tmp_path: Path):
    size = 220
    background = np.full((size, size, 3), (48, 36, 99), dtype=np.uint8)
    body = background.copy()
    slot = background.copy()
    combined = background.copy()
    body[45:190, 75:145] = (18, 117, 18)
    slot[50:145, 130:185] = (89, 18, 18)
    combined[45:190, 75:145] = (18, 117, 18)
    combined[50:145, 130:185] = (89, 18, 18)

    body_path = tmp_path / "body.png"
    slot_path = tmp_path / "slot.png"
    combined_path = tmp_path / "combined.png"
    _write_image(body_path, body)
    _write_image(slot_path, slot)
    _write_image(combined_path, combined)

    result = analyze_visible_conflict(
        body_only_image_path=body_path,
        slot_only_image_path=slot_path,
        combined_visible_image_path=combined_path,
    )

    assert result["status"] == "pass"
    assert result["mask_extraction_mode"] == "color_threshold"
    assert result["mask_extraction_signal"]["body_color_pixels"] > 0
    assert result["mask_extraction_signal"]["slot_color_pixels"] > 0
