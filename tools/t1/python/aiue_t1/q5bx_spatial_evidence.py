from __future__ import annotations

from aiue_t1.slot_geometry import (
    aabb_payload,
    attach_location_payload,
    axis_value,
    bounds_debug_payload,
    bounds_extent,
    bounds_origin,
    bounds_payload,
    bounds_volume,
    clamp01,
    non_zero_bounds,
    vector_payload,
    vector_subtract,
)


DEFAULT_THRESHOLDS = {
    "anchor_vertical_ratio_min": 0.85,
    "anchor_vertical_ratio_max": 1.05,
    "anchor_lateral_ratio_max": 1.05,
    "anchor_surface_gap_z_min": -20.0,
    "anchor_surface_gap_z_max": 10.0,
    "slot_min_above_anchor_ratio_min": 5.0,
    "slot_min_above_anchor_ratio_max": 7.0,
    "slot_center_above_anchor_ratio_min": 6.5,
    "slot_center_above_anchor_ratio_max": 8.5,
    "body_top_band_ratio": 0.28,
    "body_lateral_envelope_scale": 1.10,
}


def _evidence_confidence(body_bounds: dict, slot_bounds: dict, attach_state: dict | None) -> dict:
    body_source = str(body_bounds.get("source") or "")
    slot_source = str(slot_bounds.get("source") or "")
    score = 1.0
    if body_source.endswith("fallback"):
        score -= 0.15
    if slot_source.endswith("fallback"):
        score -= 0.15
    if not bool((attach_state or {}).get("resolved_attach_socket_exists", True)):
        score -= 0.25
    score = clamp01(score)
    if score >= 0.85:
        label = "high"
    elif score >= 0.60:
        label = "medium"
    else:
        label = "low"
    return {
        "score": score,
        "label": label,
        "body_bounds_source": body_source,
        "slot_bounds_source": slot_source,
        "resolved_attach_socket_name": str((attach_state or {}).get("resolved_attach_socket_name") or ""),
        "attach_resolution_mode": str((attach_state or {}).get("attach_resolution_mode") or ""),
    }


def analyze_spatial_evidence(*, host_result: dict, thresholds: dict | None = None) -> dict:
    cfg = dict(DEFAULT_THRESHOLDS)
    cfg.update(dict(thresholds or {}))

    body_component = dict(host_result.get("body_component") or {})
    slot_component = dict(host_result.get("slot_component") or {})
    attach_state = dict(host_result.get("clothing_attach_state") or {})
    body_bounds = bounds_payload(body_component)
    slot_bounds = bounds_payload(slot_component)
    anchor_location = attach_location_payload(slot_component)

    failed_requirements: list[str] = []
    if not anchor_location:
        failed_requirements.append("anchor_frame_missing")
    if not non_zero_bounds(body_bounds):
        failed_requirements.append("body_envelope_invalid")
    if not non_zero_bounds(slot_bounds):
        failed_requirements.append("slot_relative_bounds_invalid")

    if failed_requirements:
        return {
            "status": "fail",
            "failed_requirements": sorted(set(failed_requirements)),
            "spatial_failure_class": failed_requirements[0],
            "anchor_frame": {},
            "body_top_band": {},
            "slot_bounds_world": {},
            "slot_bounds_relative_to_anchor": {},
            "per_axis_clearance": {},
            "fit_envelope": {"thresholds": dict(cfg)},
            "evidence_confidence": _evidence_confidence(body_bounds, slot_bounds, attach_state),
        }

    body_origin = bounds_origin(body_bounds)
    body_extent = bounds_extent(body_bounds)
    slot_origin = bounds_origin(slot_bounds)
    slot_extent = bounds_extent(slot_bounds)
    body_center_x = axis_value(body_origin, "x")
    body_center_y = axis_value(body_origin, "y")
    body_center_z = axis_value(body_origin, "z")
    body_extent_x = max(axis_value(body_extent, "x"), 1e-6)
    body_extent_y = max(axis_value(body_extent, "y"), 1e-6)
    body_extent_z = max(axis_value(body_extent, "z"), 1e-6)
    slot_extent_z = max(axis_value(slot_extent, "z"), 1e-6)
    anchor_x = axis_value(anchor_location, "x")
    anchor_y = axis_value(anchor_location, "y")
    anchor_z = axis_value(anchor_location, "z")
    slot_min_z = axis_value(slot_origin, "z") - axis_value(slot_extent, "z")
    slot_max_z = axis_value(slot_origin, "z") + axis_value(slot_extent, "z")
    body_min_z = body_center_z - body_extent_z
    body_max_z = body_center_z + body_extent_z
    body_height = max(body_max_z - body_min_z, 1e-6)
    anchor_vertical_ratio = (anchor_z - body_min_z) / body_height
    anchor_lateral_ratio_x = abs(anchor_x - body_center_x) / body_extent_x
    anchor_lateral_ratio_y = abs(anchor_y - body_center_y) / body_extent_y
    anchor_lateral_ratio_max = max(anchor_lateral_ratio_x, anchor_lateral_ratio_y)
    anchor_surface_gap_z = anchor_z - body_max_z
    slot_min_above_anchor_ratio = (slot_min_z - anchor_z) / slot_extent_z
    slot_center_above_anchor_ratio = (axis_value(slot_origin, "z") - anchor_z) / slot_extent_z

    lateral_envelope_extent = vector_payload(
        body_extent_x * float(cfg["body_lateral_envelope_scale"]),
        body_extent_y * float(cfg["body_lateral_envelope_scale"]),
        max(body_height * float(cfg["body_top_band_ratio"]), slot_extent_z * 1.25) / 2.0,
    )
    body_top_band_center = vector_payload(
        body_center_x,
        body_center_y,
        body_max_z - axis_value(lateral_envelope_extent, "z"),
    )
    body_top_band = aabb_payload(
        center=body_top_band_center,
        extent=lateral_envelope_extent,
        source="q5bx_body_top_band",
    )
    slot_world = bounds_debug_payload(slot_bounds)
    slot_relative = {
        "origin_delta": vector_subtract(slot_world["origin"], anchor_location),
        "min_delta": vector_subtract(slot_world["min"], anchor_location),
        "max_delta": vector_subtract(slot_world["max"], anchor_location),
        "extent": dict(slot_world["extent"]),
    }
    per_axis_clearance = {
        "x_to_body_envelope": float(body_top_band["extent"]["x"] - abs(axis_value(slot_origin, "x") - body_center_x)),
        "y_to_body_envelope": float(body_top_band["extent"]["y"] - abs(axis_value(slot_origin, "y") - body_center_y)),
        "anchor_surface_gap_z": float(anchor_surface_gap_z),
        "slot_min_above_anchor": float(slot_min_z - anchor_z),
        "slot_center_above_anchor": float(axis_value(slot_origin, "z") - anchor_z),
        "slot_max_above_body_top": float(slot_max_z - body_max_z),
    }
    fit_envelope = {
        "thresholds": {
            key: float(value) if isinstance(value, (int, float)) else value
            for key, value in cfg.items()
        },
        "expected_anchor_surface_gap_z": {
            "min": float(cfg["anchor_surface_gap_z_min"]),
            "max": float(cfg["anchor_surface_gap_z_max"]),
        },
        "expected_slot_min_above_anchor_ratio": {
            "min": float(cfg["slot_min_above_anchor_ratio_min"]),
            "max": float(cfg["slot_min_above_anchor_ratio_max"]),
        },
        "expected_slot_center_above_anchor_ratio": {
            "min": float(cfg["slot_center_above_anchor_ratio_min"]),
            "max": float(cfg["slot_center_above_anchor_ratio_max"]),
        },
    }
    anchor_frame = {
        "anchor_location": {
            axis: axis_value(anchor_location, axis)
            for axis in ("x", "y", "z")
        },
        "body_relative_anchor": vector_subtract(anchor_location, body_origin),
        "anchor_vertical_ratio": float(anchor_vertical_ratio),
        "anchor_lateral_ratio_x": float(anchor_lateral_ratio_x),
        "anchor_lateral_ratio_y": float(anchor_lateral_ratio_y),
        "anchor_lateral_ratio_max": float(anchor_lateral_ratio_max),
        "anchor_surface_gap_z": float(anchor_surface_gap_z),
    }

    if anchor_vertical_ratio < float(cfg["anchor_vertical_ratio_min"]) or anchor_vertical_ratio > float(cfg["anchor_vertical_ratio_max"]):
        failed_requirements.append("clearance_out_of_range")
    if anchor_lateral_ratio_max > float(cfg["anchor_lateral_ratio_max"]):
        failed_requirements.append("clearance_out_of_range")
    if anchor_surface_gap_z < float(cfg["anchor_surface_gap_z_min"]) or anchor_surface_gap_z > float(cfg["anchor_surface_gap_z_max"]):
        failed_requirements.append("clearance_out_of_range")
    if slot_min_above_anchor_ratio < float(cfg["slot_min_above_anchor_ratio_min"]) or slot_min_above_anchor_ratio > float(cfg["slot_min_above_anchor_ratio_max"]):
        failed_requirements.append("fit_envelope_mismatch")
    if slot_center_above_anchor_ratio < float(cfg["slot_center_above_anchor_ratio_min"]) or slot_center_above_anchor_ratio > float(cfg["slot_center_above_anchor_ratio_max"]):
        failed_requirements.append("fit_envelope_mismatch")
    if not body_top_band or not slot_relative:
        failed_requirements.append("spatial_evidence_incomplete")

    spatial_failure_class = failed_requirements[0] if failed_requirements else None
    return {
        "status": "pass" if not failed_requirements else "fail",
        "failed_requirements": sorted(set(failed_requirements)),
        "spatial_failure_class": spatial_failure_class,
        "anchor_frame": anchor_frame,
        "body_top_band": body_top_band,
        "slot_bounds_world": slot_world,
        "slot_bounds_relative_to_anchor": slot_relative,
        "per_axis_clearance": per_axis_clearance,
        "fit_envelope": fit_envelope,
        "evidence_confidence": _evidence_confidence(body_bounds, slot_bounds, attach_state),
    }
