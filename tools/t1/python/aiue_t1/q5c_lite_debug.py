from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from aiue_t1.slot_geometry import axis_value


_PANEL_SPECS = [
    ("Front (Y/Z)", "y", "z"),
    ("Side (X/Z)", "x", "z"),
]

_BOX_STYLES = [
    ("body_bounds_world", (96, 96, 96), 2, None),
    ("local_fit_envelope", (72, 196, 120), 2, None),
    ("body_keepout_envelope", (72, 72, 220), 2, None),
    ("slot_bounds_world", (220, 200, 72), 2, (220, 200, 72, 0.12)),
    ("local_fit_intersection", (48, 220, 120), 1, (48, 220, 120, 0.22)),
    ("penetration_intersection", (0, 140, 255), 2, (0, 140, 255, 0.28)),
]


def _bounds_present(payload: dict | None) -> bool:
    return bool(dict(payload or {}).get("min")) and bool(dict(payload or {}).get("max"))


def _project_bounds(payload: dict | None, horizontal_axis: str, vertical_axis: str) -> tuple[float, float, float, float] | None:
    if not _bounds_present(payload):
        return None
    minimum = dict((payload or {}).get("min") or {})
    maximum = dict((payload or {}).get("max") or {})
    return (
        axis_value(minimum, horizontal_axis),
        axis_value(maximum, horizontal_axis),
        axis_value(minimum, vertical_axis),
        axis_value(maximum, vertical_axis),
    )


def _panel_world_bounds(analysis: dict, horizontal_axis: str, vertical_axis: str) -> tuple[float, float, float, float]:
    projected = []
    for key, *_ in _BOX_STYLES:
        rect = _project_bounds(dict(analysis.get(key) or {}), horizontal_axis, vertical_axis)
        if rect is not None:
            projected.append(rect)
    if not projected:
        return (-1.0, 1.0, -1.0, 1.0)
    min_h = min(item[0] for item in projected)
    max_h = max(item[1] for item in projected)
    min_v = min(item[2] for item in projected)
    max_v = max(item[3] for item in projected)
    span_h = max(max_h - min_h, 1.0)
    span_v = max(max_v - min_v, 1.0)
    pad_h = span_h * 0.16
    pad_v = span_v * 0.16
    return (
        min_h - pad_h,
        max_h + pad_h,
        min_v - pad_v,
        max_v + pad_v,
    )


def _world_to_pixel(
    value_h: float,
    value_v: float,
    *,
    panel_left: int,
    panel_top: int,
    panel_width: int,
    panel_height: int,
    world_bounds: tuple[float, float, float, float],
) -> tuple[int, int]:
    min_h, max_h, min_v, max_v = world_bounds
    span_h = max(max_h - min_h, 1e-6)
    span_v = max(max_v - min_v, 1e-6)
    normalized_h = (value_h - min_h) / span_h
    normalized_v = (value_v - min_v) / span_v
    pixel_x = int(round(panel_left + normalized_h * panel_width))
    pixel_y = int(round(panel_top + panel_height - (normalized_v * panel_height)))
    return pixel_x, pixel_y


def _draw_rect(
    canvas: np.ndarray,
    rect: tuple[float, float, float, float] | None,
    *,
    world_bounds: tuple[float, float, float, float],
    panel_left: int,
    panel_top: int,
    panel_width: int,
    panel_height: int,
    color: tuple[int, int, int],
    thickness: int,
    fill: tuple[int, int, int, float] | None = None,
) -> None:
    if rect is None:
        return
    min_h, max_h, min_v, max_v = rect
    x0, y1 = _world_to_pixel(
        min_h,
        min_v,
        panel_left=panel_left,
        panel_top=panel_top,
        panel_width=panel_width,
        panel_height=panel_height,
        world_bounds=world_bounds,
    )
    x1, y0 = _world_to_pixel(
        max_h,
        max_v,
        panel_left=panel_left,
        panel_top=panel_top,
        panel_width=panel_width,
        panel_height=panel_height,
        world_bounds=world_bounds,
    )
    left, right = min(x0, x1), max(x0, x1)
    top, bottom = min(y0, y1), max(y0, y1)
    if fill is not None:
        overlay = canvas.copy()
        fill_color = tuple(int(component) for component in fill[:3])
        alpha = float(fill[3])
        cv2.rectangle(overlay, (left, top), (right, bottom), fill_color, -1)
        cv2.addWeighted(overlay, alpha, canvas, 1.0 - alpha, 0.0, dst=canvas)
    cv2.rectangle(canvas, (left, top), (right, bottom), color, thickness)


def render_q5c_lite_debug_image(
    *,
    package_id: str,
    analysis: dict,
    output_path: str | Path,
    image_width: int = 1480,
    image_height: int = 900,
) -> dict:
    canvas = np.full((image_height, image_width, 3), 18, dtype=np.uint8)
    cv2.rectangle(canvas, (0, 0), (image_width - 1, image_height - 1), (56, 68, 86), 2)

    title = f"Q5C-lite Local Fit Debug | {package_id}"
    cv2.putText(canvas, title, (36, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (236, 241, 246), 2, cv2.LINE_AA)

    quality_class = str(analysis.get("quality_class") or "unknown")
    summary_lines = [
        f"Status: {str(analysis.get('status') or 'unknown').upper()}",
        f"Quality: {quality_class.upper()}",
        f"Diagnostic: {str(analysis.get('fit_diagnostic_class') or 'unknown')}",
        f"Embedding: {float(analysis.get('embedding_ratio') or 0.0):.3f}",
        f"Floating: {float(analysis.get('floating_ratio') or 0.0):.3f}",
        f"Penetration: {float(analysis.get('penetration_ratio') or 0.0):.3f}",
        f"Local Fit Volume: {float(analysis.get('local_fit_volume') or 0.0):.2f}",
    ]
    failed_requirements = [str(item) for item in list(analysis.get("failed_requirements") or []) if str(item).strip()]
    if failed_requirements:
        summary_lines.append("Fails: " + ", ".join(failed_requirements))

    for index, line in enumerate(summary_lines):
        cv2.putText(
            canvas,
            line,
            (38, 96 + (index * 28)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (196, 206, 219),
            1,
            cv2.LINE_AA,
        )

    legend_items = [
        ("Body Bounds", (96, 96, 96)),
        ("Local Fit Envelope", (72, 196, 120)),
        ("Body Keepout", (72, 72, 220)),
        ("Slot Bounds", (220, 200, 72)),
        ("Embedded Volume", (48, 220, 120)),
        ("Penetration", (0, 140, 255)),
    ]
    legend_x = 980
    legend_y = 44
    for index, (label, color) in enumerate(legend_items):
        row_y = legend_y + (index * 28)
        cv2.rectangle(canvas, (legend_x, row_y - 12), (legend_x + 18, row_y + 6), color, -1)
        cv2.putText(canvas, label, (legend_x + 28, row_y + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.54, (226, 232, 240), 1, cv2.LINE_AA)

    panel_margin_x = 36
    panel_top = 250
    panel_gap = 28
    panel_width = int((image_width - (panel_margin_x * 2) - panel_gap) / 2)
    panel_height = image_height - panel_top - 44

    for index, (panel_title, horizontal_axis, vertical_axis) in enumerate(_PANEL_SPECS):
        panel_left = panel_margin_x + (index * (panel_width + panel_gap))
        cv2.rectangle(canvas, (panel_left, panel_top), (panel_left + panel_width, panel_top + panel_height), (56, 68, 86), 1)
        cv2.putText(canvas, panel_title, (panel_left + 12, panel_top - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (236, 241, 246), 2, cv2.LINE_AA)
        world_bounds = _panel_world_bounds(analysis, horizontal_axis, vertical_axis)
        for key, color, thickness, fill in _BOX_STYLES:
            rect = _project_bounds(dict(analysis.get(key) or {}), horizontal_axis, vertical_axis)
            _draw_rect(
                canvas,
                rect,
                world_bounds=world_bounds,
                panel_left=panel_left,
                panel_top=panel_top,
                panel_width=panel_width,
                panel_height=panel_height,
                color=color,
                thickness=thickness,
                fill=fill,
            )

        axis_caption = f"{horizontal_axis.upper()} range [{world_bounds[0]:.1f}, {world_bounds[1]:.1f}] | {vertical_axis.upper()} range [{world_bounds[2]:.1f}, {world_bounds[3]:.1f}]"
        cv2.putText(
            canvas,
            axis_caption,
            (panel_left + 12, panel_top + panel_height + 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.46,
            (148, 163, 184),
            1,
            cv2.LINE_AA,
        )

    resolved_output_path = Path(output_path).expanduser().resolve()
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(resolved_output_path), canvas):
        raise RuntimeError(f"q5c_lite_debug_image_write_failed:{resolved_output_path}")
    return {
        "image_path": str(resolved_output_path),
        "image_width": image_width,
        "image_height": image_height,
        "panels": [
            {"title": title, "horizontal_axis": horizontal_axis, "vertical_axis": vertical_axis}
            for title, horizontal_axis, vertical_axis in _PANEL_SPECS
        ],
    }
