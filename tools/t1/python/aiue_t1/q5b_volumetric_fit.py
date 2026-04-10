from __future__ import annotations


DEFAULT_THRESHOLDS = {
    "anchor_vertical_ratio_min": 0.85,
    "anchor_vertical_ratio_max": 1.05,
    "anchor_lateral_ratio_max": 1.05,
    "anchor_surface_gap_z_min": -20.0,
    "anchor_surface_gap_z_max": 10.0,
    "slot_min_above_anchor_ratio_min": 5.0,
    "slot_min_above_anchor_ratio_max": 7.0,
}


def _bounds_payload(component_payload: dict | None) -> dict:
    return dict(((component_payload or {}).get("bounds")) or {})


def _attach_location_payload(component_payload: dict | None) -> dict:
    return dict((((component_payload or {}).get("attach")) or {}).get("world_transform") or {}).get("location") or {}


def _axis_value(payload: dict, axis: str) -> float:
    return float((payload or {}).get(axis) or 0.0)


def _non_zero_bounds(bounds: dict) -> bool:
    return bool(bounds.get("non_zero")) and any(abs(_axis_value(bounds.get("extent") or {}, axis)) > 1e-6 for axis in ("x", "y", "z"))


def analyze_volumetric_fit(*, host_result: dict, thresholds: dict | None = None) -> dict:
    cfg = dict(DEFAULT_THRESHOLDS)
    cfg.update(dict(thresholds or {}))

    body_component = dict(host_result.get("body_component") or {})
    slot_component = dict(host_result.get("slot_component") or {})
    body_bounds = _bounds_payload(body_component)
    slot_bounds = _bounds_payload(slot_component)
    anchor_location = _attach_location_payload(slot_component)

    failed_requirements: list[str] = []
    if not _non_zero_bounds(body_bounds):
        failed_requirements.append("body_bounds_missing")
    if not _non_zero_bounds(slot_bounds):
        failed_requirements.append("slot_bounds_missing")
    if not anchor_location:
        failed_requirements.append("attach_transform_missing")

    if failed_requirements:
        return {
            "status": "fail",
            "metrics": {},
            "failed_requirements": sorted(set(failed_requirements)),
            "thresholds": cfg,
        }

    body_origin = dict(body_bounds.get("origin") or {})
    body_extent = dict(body_bounds.get("extent") or {})
    slot_origin = dict(slot_bounds.get("origin") or {})
    slot_extent = dict(slot_bounds.get("extent") or {})

    body_center_x = _axis_value(body_origin, "x")
    body_center_y = _axis_value(body_origin, "y")
    body_center_z = _axis_value(body_origin, "z")
    body_extent_x = max(_axis_value(body_extent, "x"), 1e-6)
    body_extent_y = max(_axis_value(body_extent, "y"), 1e-6)
    body_extent_z = max(_axis_value(body_extent, "z"), 1e-6)

    anchor_x = _axis_value(anchor_location, "x")
    anchor_y = _axis_value(anchor_location, "y")
    anchor_z = _axis_value(anchor_location, "z")

    body_min_z = body_center_z - body_extent_z
    body_max_z = body_center_z + body_extent_z
    body_height = max(body_max_z - body_min_z, 1e-6)
    slot_min_z = _axis_value(slot_origin, "z") - _axis_value(slot_extent, "z")
    slot_extent_z = max(_axis_value(slot_extent, "z"), 1e-6)

    anchor_vertical_ratio = (anchor_z - body_min_z) / body_height
    anchor_lateral_ratio_x = abs(anchor_x - body_center_x) / body_extent_x
    anchor_lateral_ratio_y = abs(anchor_y - body_center_y) / body_extent_y
    anchor_lateral_ratio_max = max(anchor_lateral_ratio_x, anchor_lateral_ratio_y)
    anchor_surface_gap_z = anchor_z - body_max_z
    slot_min_above_anchor_ratio = (slot_min_z - anchor_z) / slot_extent_z
    slot_center_above_anchor_ratio = (_axis_value(slot_origin, "z") - anchor_z) / slot_extent_z

    if anchor_vertical_ratio < float(cfg["anchor_vertical_ratio_min"]) or anchor_vertical_ratio > float(cfg["anchor_vertical_ratio_max"]):
        failed_requirements.append("anchor_vertical_band_mismatch")
    if anchor_lateral_ratio_max > float(cfg["anchor_lateral_ratio_max"]):
        failed_requirements.append("anchor_outside_lateral_envelope")
    if anchor_surface_gap_z < float(cfg["anchor_surface_gap_z_min"]) or anchor_surface_gap_z > float(cfg["anchor_surface_gap_z_max"]):
        failed_requirements.append("anchor_surface_gap_out_of_range")
    if (
        slot_min_above_anchor_ratio < float(cfg["slot_min_above_anchor_ratio_min"])
        or slot_min_above_anchor_ratio > float(cfg["slot_min_above_anchor_ratio_max"])
    ):
        failed_requirements.append("slot_offset_out_of_range")

    return {
        "status": "pass" if not failed_requirements else "fail",
        "metrics": {
            "anchor_vertical_ratio": float(anchor_vertical_ratio),
            "anchor_lateral_ratio_x": float(anchor_lateral_ratio_x),
            "anchor_lateral_ratio_y": float(anchor_lateral_ratio_y),
            "anchor_lateral_ratio_max": float(anchor_lateral_ratio_max),
            "anchor_surface_gap_z": float(anchor_surface_gap_z),
            "slot_min_above_anchor_ratio": float(slot_min_above_anchor_ratio),
            "slot_center_above_anchor_ratio": float(slot_center_above_anchor_ratio),
            "body_bounds_source": str(body_bounds.get("source") or ""),
            "slot_bounds_source": str(slot_bounds.get("source") or ""),
        },
        "failed_requirements": sorted(set(failed_requirements)),
        "thresholds": {
            "anchor_vertical_ratio_min": float(cfg["anchor_vertical_ratio_min"]),
            "anchor_vertical_ratio_max": float(cfg["anchor_vertical_ratio_max"]),
            "anchor_lateral_ratio_max": float(cfg["anchor_lateral_ratio_max"]),
            "anchor_surface_gap_z_min": float(cfg["anchor_surface_gap_z_min"]),
            "anchor_surface_gap_z_max": float(cfg["anchor_surface_gap_z_max"]),
            "slot_min_above_anchor_ratio_min": float(cfg["slot_min_above_anchor_ratio_min"]),
            "slot_min_above_anchor_ratio_max": float(cfg["slot_min_above_anchor_ratio_max"]),
        },
    }
