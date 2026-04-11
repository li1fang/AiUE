from __future__ import annotations

from aiue_t1.slot_geometry import (
    aabb_intersection,
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
)


DEFAULT_THRESHOLDS = {
    "local_envelope_extent_x_scale": 1.55,
    "local_envelope_extent_y_scale": 1.60,
    "local_envelope_extent_z_scale": 1.85,
    "local_envelope_center_z_ratio": 6.85,
    "body_keepout_height_ratio": 0.08,
    "min_embedding_ratio": 0.82,
    "max_floating_ratio": 0.18,
    "max_penetration_ratio": 0.02,
}


def _threshold_deltas(*, embedding_ratio: float, floating_ratio: float, penetration_ratio: float, thresholds: dict) -> dict:
    return {
        "embedding_ratio_delta_to_min": float(embedding_ratio - float(thresholds["min_embedding_ratio"])),
        "floating_ratio_delta_to_max": float(floating_ratio - float(thresholds["max_floating_ratio"])),
        "penetration_ratio_delta_to_max": float(penetration_ratio - float(thresholds["max_penetration_ratio"])),
    }


def _diagnostic_signals(
    *,
    embedding_ratio: float,
    floating_ratio: float,
    penetration_ratio: float,
    thresholds: dict,
) -> dict:
    embedding_ratio_below_threshold = bool(embedding_ratio < float(thresholds["min_embedding_ratio"]))
    floating_ratio_exceeded = bool(floating_ratio > float(thresholds["max_floating_ratio"]))
    penetration_ratio_exceeded = bool(penetration_ratio > float(thresholds["max_penetration_ratio"]))
    borderline_fit = bool(
        not embedding_ratio_below_threshold
        and not floating_ratio_exceeded
        and not penetration_ratio_exceeded
        and (
            embedding_ratio < float(thresholds["min_embedding_ratio"]) + 0.05
            or floating_ratio > float(thresholds["max_floating_ratio"]) * 0.75
        )
    )
    return {
        "embedding_ratio_below_threshold": embedding_ratio_below_threshold,
        "floating_ratio_exceeded": floating_ratio_exceeded,
        "penetration_ratio_exceeded": penetration_ratio_exceeded,
        "borderline_fit": borderline_fit,
    }


def _fit_diagnostic_class(*, input_invalid: bool, diagnostic_signals: dict) -> str:
    if input_invalid:
        return "input_invalid"
    if bool(diagnostic_signals.get("penetration_ratio_exceeded")) and (
        bool(diagnostic_signals.get("floating_ratio_exceeded"))
        or bool(diagnostic_signals.get("embedding_ratio_below_threshold"))
    ):
        return "mixed_penetration_and_floating"
    if bool(diagnostic_signals.get("penetration_ratio_exceeded")):
        return "penetration_keepout_overlap"
    if bool(diagnostic_signals.get("floating_ratio_exceeded")) or bool(diagnostic_signals.get("embedding_ratio_below_threshold")):
        return "floating_fit_out_of_range"
    if bool(diagnostic_signals.get("borderline_fit")):
        return "pass_borderline"
    return "pass_stable"


def margin_to_failure_by_metric(*, threshold_deltas: dict) -> dict:
    deltas = dict(threshold_deltas or {})
    return {
        "embedding_ratio_margin_to_failure": float(deltas.get("embedding_ratio_delta_to_min") or 0.0),
        "floating_ratio_margin_to_failure": -float(deltas.get("floating_ratio_delta_to_max") or 0.0),
        "penetration_ratio_margin_to_failure": -float(deltas.get("penetration_ratio_delta_to_max") or 0.0),
    }


def closest_margin_info(*, threshold_deltas: dict) -> tuple[str, float]:
    margins = margin_to_failure_by_metric(threshold_deltas=threshold_deltas)
    metric, value = min(margins.items(), key=lambda item: float(item[1]))
    return str(metric), float(value)


def risk_band_for_q5c_lite(*, status: str, fit_diagnostic_class: str, closest_margin_value: float) -> str:
    diagnostic = str(fit_diagnostic_class or "")
    if str(status or "") != "pass" or diagnostic in {
        "input_invalid",
        "floating_fit_out_of_range",
        "penetration_keepout_overlap",
        "mixed_penetration_and_floating",
    }:
        return "fail"
    if float(closest_margin_value) <= 0.0:
        return "fail"
    if diagnostic == "pass_borderline" or float(closest_margin_value) <= 0.01:
        return "borderline"
    if float(closest_margin_value) <= 0.05:
        return "watch"
    return "stable"


def risk_reason_for_q5c_lite(
    *,
    risk_band: str,
    fit_diagnostic_class: str,
    closest_margin_metric: str,
    closest_margin_value: float,
) -> str:
    if risk_band == "fail":
        return str(fit_diagnostic_class or closest_margin_metric or "fail")
    if risk_band in {"borderline", "watch"}:
        return f"{closest_margin_metric}:{float(closest_margin_value):.4f}"
    return ""


def analyze_q5c_lite(*, host_result: dict, thresholds: dict | None = None) -> dict:
    cfg = dict(DEFAULT_THRESHOLDS)
    cfg.update(dict(thresholds or {}))

    body_component = dict(host_result.get("body_component") or {})
    slot_component = dict(host_result.get("slot_component") or {})
    body_bounds = bounds_payload(body_component)
    slot_bounds = bounds_payload(slot_component)
    anchor_location = attach_location_payload(slot_component)

    failed_requirements: list[str] = []
    if not non_zero_bounds(body_bounds):
        failed_requirements.append("body_envelope_invalid")
    if not non_zero_bounds(slot_bounds):
        failed_requirements.append("slot_relative_bounds_invalid")
    if not anchor_location:
        failed_requirements.append("anchor_frame_missing")

    if failed_requirements:
        return {
            "status": "fail",
            "failed_requirements": sorted(set(failed_requirements)),
            "fit_diagnostic_class": _fit_diagnostic_class(input_invalid=True, diagnostic_signals={}),
            "diagnostic_signals": {
                "embedding_ratio_below_threshold": False,
                "floating_ratio_exceeded": True,
                "penetration_ratio_exceeded": False,
                "borderline_fit": False,
            },
            "threshold_deltas": {
                "embedding_ratio_delta_to_min": float(0.0 - float(cfg["min_embedding_ratio"])),
                "floating_ratio_delta_to_max": float(1.0 - float(cfg["max_floating_ratio"])),
                "penetration_ratio_delta_to_max": float(0.0 - float(cfg["max_penetration_ratio"])),
            },
            "embedding_ratio": 0.0,
            "floating_ratio": 1.0,
            "penetration_clusters": [],
            "local_fit_volume": 0.0,
            "quality_class": "fail",
            "body_bounds_world": {},
            "local_fit_envelope": {},
            "body_keepout_envelope": {},
            "slot_bounds_world": {},
            "local_fit_intersection": {},
            "penetration_intersection": {},
        }

    slot_world = bounds_debug_payload(slot_bounds)
    body_world = bounds_debug_payload(body_bounds)
    slot_extent = bounds_extent(slot_bounds)
    slot_origin = bounds_origin(slot_bounds)
    body_origin = bounds_origin(body_bounds)
    body_extent = bounds_extent(body_bounds)

    slot_volume = max(bounds_volume(slot_bounds), 1e-6)
    body_height = max(axis_value(body_extent, "z") * 2.0, 1e-6)
    local_fit_envelope = aabb_payload(
        center=vector_payload(
            axis_value(slot_origin, "x"),
            axis_value(slot_origin, "y"),
            axis_value(anchor_location, "z") + (axis_value(slot_extent, "z") * float(cfg["local_envelope_center_z_ratio"])),
        ),
        extent=vector_payload(
            axis_value(slot_extent, "x") * float(cfg["local_envelope_extent_x_scale"]),
            axis_value(slot_extent, "y") * float(cfg["local_envelope_extent_y_scale"]),
            axis_value(slot_extent, "z") * float(cfg["local_envelope_extent_z_scale"]),
        ),
        source="q5c_local_fit_envelope",
    )
    body_keepout_envelope = aabb_payload(
        center=vector_payload(
            axis_value(body_origin, "x"),
            axis_value(body_origin, "y"),
            axis_value(body_origin, "z") + axis_value(body_extent, "z") - (body_height * float(cfg["body_keepout_height_ratio"]) * 0.5),
        ),
        extent=vector_payload(
            axis_value(body_extent, "x") * 1.02,
            axis_value(body_extent, "y") * 1.02,
            max(body_height * float(cfg["body_keepout_height_ratio"]) * 0.5, axis_value(slot_extent, "z") * 0.4),
        ),
        source="q5c_body_keepout_envelope",
    )
    local_fit_intersection = aabb_intersection(slot_world, local_fit_envelope, source="q5c_local_fit_intersection")
    penetration_intersection = aabb_intersection(slot_world, body_keepout_envelope, source="q5c_penetration_intersection")
    embedding_ratio = clamp01(float(local_fit_intersection["volume"]) / slot_volume)
    floating_ratio = clamp01(1.0 - embedding_ratio)
    penetration_ratio = clamp01(float(penetration_intersection["volume"]) / slot_volume)
    diagnostic_signals = _diagnostic_signals(
        embedding_ratio=embedding_ratio,
        floating_ratio=floating_ratio,
        penetration_ratio=penetration_ratio,
        thresholds=cfg,
    )
    threshold_deltas = _threshold_deltas(
        embedding_ratio=embedding_ratio,
        floating_ratio=floating_ratio,
        penetration_ratio=penetration_ratio,
        thresholds=cfg,
    )
    penetration_clusters = []
    if bool(diagnostic_signals["penetration_ratio_exceeded"]):
        penetration_clusters.append(
            {
                "cluster_id": "body_top_keepout_overlap",
                "cluster_class": "body_keepout_overlap",
                "source_envelope": "q5c_body_keepout_envelope",
                "severity": "fail",
                "volume_ratio": float(penetration_ratio),
                "overlap_volume": float(penetration_intersection["volume"]),
                "threshold_ratio": float(cfg["max_penetration_ratio"]),
                "excess_ratio": float(max(penetration_ratio - float(cfg["max_penetration_ratio"]), 0.0)),
                "intersection": penetration_intersection,
            }
        )

    if bool(diagnostic_signals["embedding_ratio_below_threshold"]):
        failed_requirements.append("fit_envelope_mismatch")
    if bool(diagnostic_signals["floating_ratio_exceeded"]):
        failed_requirements.append("floating_ratio_exceeded")
    if penetration_clusters:
        failed_requirements.append("penetration_clusters_present")

    fit_diagnostic_class = _fit_diagnostic_class(
        input_invalid=False,
        diagnostic_signals=diagnostic_signals,
    )

    if failed_requirements:
        quality_class = "fail"
    elif bool(diagnostic_signals["borderline_fit"]):
        quality_class = "warn"
    else:
        quality_class = "pass"

    return {
        "status": "pass" if not failed_requirements else "fail",
        "failed_requirements": sorted(set(failed_requirements)),
        "fit_diagnostic_class": fit_diagnostic_class,
        "diagnostic_signals": diagnostic_signals,
        "threshold_deltas": threshold_deltas,
        "embedding_ratio": float(embedding_ratio),
        "floating_ratio": float(floating_ratio),
        "penetration_clusters": penetration_clusters,
        "local_fit_volume": float(local_fit_intersection["volume"]),
        "quality_class": quality_class,
        "body_bounds_world": body_world,
        "slot_bounds_world": slot_world,
        "local_fit_envelope": local_fit_envelope,
        "body_keepout_envelope": body_keepout_envelope,
        "local_fit_intersection": local_fit_intersection,
        "penetration_intersection": penetration_intersection,
        "penetration_ratio": float(penetration_ratio),
        "thresholds": {
            key: float(value) if isinstance(value, (int, float)) else value
            for key, value in cfg.items()
        },
    }
