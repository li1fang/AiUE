from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


DEFAULT_THRESHOLDS = {
    "body_green_min": 70,
    "slot_red_min": 70,
    "channel_other_max": 80,
    "dominance_margin_primary": 25,
    "dominance_margin_secondary": 15,
    "silhouette_delta_min": 12,
    "slot_mask_coverage_ratio_min": 0.001,
    "slot_core_pixels_min": 400,
    "slot_visible_ratio_in_core_min": 0.75,
    "body_intrusion_ratio_in_core_max": 0.05,
    "close_kernel_px": 9,
    "erode_kernel_px": 7,
}


def _load_bgr_image(path: str | Path) -> tuple[np.ndarray | None, str | None]:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        return None, "mask_capture_failed"
    image = cv2.imread(str(resolved), cv2.IMREAD_COLOR)
    if image is None:
        return None, "mask_decode_failed"
    return image, None


def _color_mask(image_bgr: np.ndarray, *, red: bool = False, green: bool = False, thresholds: dict | None = None) -> np.ndarray:
    cfg = dict(DEFAULT_THRESHOLDS)
    cfg.update(dict(thresholds or {}))
    blue = image_bgr[:, :, 0]
    green_channel = image_bgr[:, :, 1]
    red_channel = image_bgr[:, :, 2]
    if green:
        strict_green = (
            (green_channel >= int(cfg["body_green_min"]))
            & (red_channel <= int(cfg["channel_other_max"]))
            & (blue <= int(cfg["channel_other_max"]))
        )
        dominant_green = (
            (green_channel >= int(cfg["body_green_min"]))
            & (green_channel >= (red_channel + int(cfg["dominance_margin_primary"])))
            & (green_channel >= (blue + int(cfg["dominance_margin_secondary"])))
        )
        return (strict_green | dominant_green).astype(np.uint8)
    if red:
        strict_red = (
            (red_channel >= int(cfg["slot_red_min"]))
            & (green_channel <= int(cfg["channel_other_max"]))
            & (blue <= int(cfg["channel_other_max"]))
        )
        dominant_red = (
            (red_channel >= int(cfg["slot_red_min"]))
            & (red_channel >= (green_channel + int(cfg["dominance_margin_primary"])))
            & (red_channel >= (blue + int(cfg["dominance_margin_secondary"])))
        )
        return (strict_red | dominant_red).astype(np.uint8)
    return np.zeros(image_bgr.shape[:2], dtype=np.uint8)


def _morph_slot_core(slot_mask: np.ndarray, thresholds: dict | None = None) -> np.ndarray:
    cfg = dict(DEFAULT_THRESHOLDS)
    cfg.update(dict(thresholds or {}))
    close_kernel = np.ones((int(cfg["close_kernel_px"]), int(cfg["close_kernel_px"])), dtype=np.uint8)
    erode_kernel = np.ones((int(cfg["erode_kernel_px"]), int(cfg["erode_kernel_px"])), dtype=np.uint8)
    closed = cv2.morphologyEx(slot_mask.astype(np.uint8), cv2.MORPH_CLOSE, close_kernel)
    return cv2.erode(closed, erode_kernel, iterations=1)


def _silhouette_foreground_mask(image_bgr: np.ndarray, background_bgr: np.ndarray, thresholds: dict | None = None) -> np.ndarray:
    cfg = dict(DEFAULT_THRESHOLDS)
    cfg.update(dict(thresholds or {}))
    diff = np.max(np.abs(image_bgr.astype(np.int16) - background_bgr.astype(np.int16)), axis=2)
    return (diff >= int(cfg["silhouette_delta_min"])).astype(np.uint8)


def _derive_mask_payload(
    *,
    body_only_bgr: np.ndarray,
    slot_only_bgr: np.ndarray,
    combined_visible_bgr: np.ndarray,
    thresholds: dict | None = None,
) -> dict:
    body_mask = _color_mask(body_only_bgr, green=True, thresholds=thresholds)
    slot_mask = _color_mask(slot_only_bgr, red=True, thresholds=thresholds)
    combined_body_mask = _color_mask(combined_visible_bgr, green=True, thresholds=thresholds)
    combined_slot_mask = _color_mask(combined_visible_bgr, red=True, thresholds=thresholds)
    color_signal = {
        "body_color_pixels": int(np.count_nonzero(body_mask)),
        "slot_color_pixels": int(np.count_nonzero(slot_mask)),
        "combined_body_color_pixels": int(np.count_nonzero(combined_body_mask)),
        "combined_slot_color_pixels": int(np.count_nonzero(combined_slot_mask)),
    }
    if any(np.count_nonzero(mask) > 0 for mask in (body_mask, slot_mask, combined_body_mask, combined_slot_mask)):
        return {
            "mode": "color_threshold",
            "body_mask": body_mask,
            "slot_mask": slot_mask,
            "combined_body_mask": combined_body_mask,
            "combined_slot_mask": combined_slot_mask,
            "signal": color_signal,
        }

    background_bgr = np.maximum(np.maximum(body_only_bgr, slot_only_bgr), combined_visible_bgr)
    body_mask = _silhouette_foreground_mask(body_only_bgr, background_bgr, thresholds=thresholds)
    slot_mask = _silhouette_foreground_mask(slot_only_bgr, background_bgr, thresholds=thresholds)
    combined_foreground_mask = _silhouette_foreground_mask(combined_visible_bgr, background_bgr, thresholds=thresholds)
    combined_slot_mask = ((combined_foreground_mask > 0) & (body_mask == 0)).astype(np.uint8)
    combined_body_mask = ((combined_foreground_mask > 0) & (body_mask > 0)).astype(np.uint8)
    return {
        "mode": "silhouette_fallback",
        "body_mask": body_mask,
        "slot_mask": slot_mask,
        "combined_body_mask": combined_body_mask,
        "combined_slot_mask": combined_slot_mask,
        "signal": {
            **color_signal,
            "silhouette_body_pixels": int(np.count_nonzero(body_mask)),
            "silhouette_slot_pixels": int(np.count_nonzero(slot_mask)),
            "silhouette_combined_body_pixels": int(np.count_nonzero(combined_body_mask)),
            "silhouette_combined_slot_pixels": int(np.count_nonzero(combined_slot_mask)),
        },
    }


def _write_debug_overlay(
    combined_visible_bgr: np.ndarray,
    *,
    slot_core_mask: np.ndarray,
    combined_slot_mask: np.ndarray,
    combined_body_mask: np.ndarray,
    output_path: str | Path | None,
) -> str:
    if not str(output_path or "").strip():
        return ""
    resolved = Path(output_path).expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    overlay = combined_visible_bgr.copy()

    slot_core_edges = cv2.morphologyEx(slot_core_mask.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), dtype=np.uint8))
    overlay[slot_core_edges > 0] = (255, 0, 0)
    overlay[(combined_slot_mask > 0) & (slot_core_mask > 0)] = (255, 255, 0)
    overlay[(combined_body_mask > 0) & (slot_core_mask > 0)] = (0, 255, 255)
    cv2.imwrite(str(resolved), overlay)
    return str(resolved)


def analyze_visible_conflict(
    *,
    body_only_image_path: str | Path,
    slot_only_image_path: str | Path,
    combined_visible_image_path: str | Path,
    debug_overlay_path: str | Path | None = None,
    thresholds: dict | None = None,
) -> dict:
    cfg = dict(DEFAULT_THRESHOLDS)
    cfg.update(dict(thresholds or {}))
    body_only_bgr, body_error = _load_bgr_image(body_only_image_path)
    slot_only_bgr, slot_error = _load_bgr_image(slot_only_image_path)
    combined_visible_bgr, combined_error = _load_bgr_image(combined_visible_image_path)

    load_errors = [error for error in (body_error, slot_error, combined_error) if error]
    if load_errors:
        return {
            "status": "fail",
            "metrics": {},
            "failed_requirements": sorted(set(load_errors)),
            "debug_overlay_path": "",
        }

    total_pixels = int(body_only_bgr.shape[0] * body_only_bgr.shape[1]) if body_only_bgr is not None else 0
    mask_payload = _derive_mask_payload(
        body_only_bgr=body_only_bgr,
        slot_only_bgr=slot_only_bgr,
        combined_visible_bgr=combined_visible_bgr,
        thresholds=cfg,
    )
    body_mask = mask_payload["body_mask"]
    slot_mask = mask_payload["slot_mask"]
    combined_body_mask = mask_payload["combined_body_mask"]
    combined_slot_mask = mask_payload["combined_slot_mask"]
    slot_core_mask = _morph_slot_core(slot_mask, thresholds=cfg)

    body_pixels = int(np.count_nonzero(body_mask))
    slot_pixels = int(np.count_nonzero(slot_mask))
    slot_core_pixels = int(np.count_nonzero(slot_core_mask))
    slot_visible_pixels_in_core = int(np.count_nonzero((combined_slot_mask > 0) & (slot_core_mask > 0)))
    body_intrusion_pixels_in_core = int(np.count_nonzero((combined_body_mask > 0) & (slot_core_mask > 0)))

    body_mask_coverage_ratio = float(body_pixels / total_pixels) if total_pixels else 0.0
    slot_mask_coverage_ratio = float(slot_pixels / total_pixels) if total_pixels else 0.0
    slot_visible_ratio_in_core = float(slot_visible_pixels_in_core / slot_core_pixels) if slot_core_pixels else 0.0
    body_intrusion_ratio_in_core = float(body_intrusion_pixels_in_core / slot_core_pixels) if slot_core_pixels else 0.0

    failed_requirements = []
    if body_pixels <= 0:
        failed_requirements.append("body_mask_missing")
    if slot_pixels <= 0:
        failed_requirements.append("slot_mask_missing")
    if slot_mask_coverage_ratio < float(cfg["slot_mask_coverage_ratio_min"]):
        failed_requirements.append("slot_mask_missing")
    if slot_core_pixels < int(cfg["slot_core_pixels_min"]):
        failed_requirements.append("slot_core_too_small")
    if slot_core_pixels > 0 and slot_visible_ratio_in_core < float(cfg["slot_visible_ratio_in_core_min"]):
        failed_requirements.append("slot_visibility_insufficient")
    if slot_core_pixels > 0 and body_intrusion_ratio_in_core > float(cfg["body_intrusion_ratio_in_core_max"]):
        failed_requirements.append("body_intrusion_exceeded")

    debug_overlay = _write_debug_overlay(
        combined_visible_bgr,
        slot_core_mask=slot_core_mask,
        combined_slot_mask=combined_slot_mask,
        combined_body_mask=combined_body_mask,
        output_path=debug_overlay_path,
    )

    return {
        "status": "pass" if not failed_requirements else "fail",
        "mask_extraction_mode": str(mask_payload.get("mode") or "color_threshold"),
        "mask_extraction_signal": dict(mask_payload.get("signal") or {}),
        "metrics": {
            "body_mask_coverage_ratio": body_mask_coverage_ratio,
            "slot_mask_coverage_ratio": slot_mask_coverage_ratio,
            "slot_core_pixels": slot_core_pixels,
            "slot_visible_ratio_in_core": slot_visible_ratio_in_core,
            "body_intrusion_pixels_in_core": body_intrusion_pixels_in_core,
            "body_intrusion_ratio_in_core": body_intrusion_ratio_in_core,
        },
        "failed_requirements": sorted(set(failed_requirements)),
        "debug_overlay_path": debug_overlay,
        "thresholds": {
            "body_green_min": int(cfg["body_green_min"]),
            "slot_red_min": int(cfg["slot_red_min"]),
            "channel_other_max": int(cfg["channel_other_max"]),
            "dominance_margin_primary": int(cfg["dominance_margin_primary"]),
            "dominance_margin_secondary": int(cfg["dominance_margin_secondary"]),
            "silhouette_delta_min": int(cfg["silhouette_delta_min"]),
            "slot_mask_coverage_ratio_min": float(cfg["slot_mask_coverage_ratio_min"]),
            "slot_core_pixels_min": int(cfg["slot_core_pixels_min"]),
            "slot_visible_ratio_in_core_min": float(cfg["slot_visible_ratio_in_core_min"]),
            "body_intrusion_ratio_in_core_max": float(cfg["body_intrusion_ratio_in_core_max"]),
            "close_kernel_px": int(cfg["close_kernel_px"]),
            "erode_kernel_px": int(cfg["erode_kernel_px"]),
        },
    }
