from __future__ import annotations

from typing import Any


DIVERSITY_AXIS_THRESHOLDS = {
    "character_variant_diversity": {"covered": 2, "partial": 1},
    "weapon_variant_diversity": {"covered": 2, "partial": 1},
    "clothing_fixture_diversity": {"covered": 2, "partial": 1},
    "fx_fixture_diversity": {"covered": 2, "partial": 1},
    "action_variation": {"covered": 2, "partial": 1},
    "animation_variation": {"covered": 2, "partial": 1},
}

DIVERSITY_MATRIX_GATE_IDS = [
    "diversity_matrix_dv2",
    "diversity_matrix_dv1",
]


def diversity_status_for_count(axis_id: str, distinct_count: int) -> str:
    thresholds = dict(DIVERSITY_AXIS_THRESHOLDS.get(axis_id) or {})
    covered_threshold = int(thresholds.get("covered") or 0)
    partial_threshold = int(thresholds.get("partial") or 0)
    if distinct_count >= covered_threshold and covered_threshold > 0:
        return "covered"
    if distinct_count >= partial_threshold and partial_threshold > 0:
        return "partial"
    return "missing"


def build_diversity_axis(
    axis_id: str,
    observed_values: list[str],
    *,
    noun_phrase: str,
    gate_label: str = "DV1",
) -> dict[str, Any]:
    distinct_values = sorted({str(item) for item in observed_values if str(item)})
    distinct_count = len(distinct_values)
    status = diversity_status_for_count(axis_id, distinct_count)
    thresholds = dict(DIVERSITY_AXIS_THRESHOLDS.get(axis_id) or {})
    summary = (
        f"{gate_label} currently verifies {distinct_count} distinct {noun_phrase} on the automated demo-ready path."
    )
    return {
        "axis_id": axis_id,
        "status": status,
        "distinct_count": distinct_count,
        "covered_threshold": int(thresholds.get("covered") or 0),
        "partial_threshold": int(thresholds.get("partial") or 0),
        "observed_values": distinct_values,
        "summary": summary,
    }


def latest_diversity_matrix_entry(report_index: dict) -> tuple[str, dict[str, Any], dict[str, Any]]:
    reports_by_gate_id = dict(report_index.get("reports_by_gate_id") or {})
    for gate_id in DIVERSITY_MATRIX_GATE_IDS:
        entry = dict(reports_by_gate_id.get(gate_id) or {})
        report_payload = dict(entry.get("report") or {})
        if report_payload:
            return gate_id, entry, report_payload
    return DIVERSITY_MATRIX_GATE_IDS[0], {}, {}


def build_diversity_matrix_quality_summary(report_index: dict) -> dict[str, Any]:
    gate_id, entry, report_payload = latest_diversity_matrix_entry(report_index)
    if not report_payload:
        return {
            "status": "missing",
            "gate_id": gate_id,
            "report_source_path": "",
            "covered_axis_count": 0,
            "partial_axis_count": 0,
            "missing_axis_count": 0,
            "distinct_counts": {},
            "coverage_axes": [],
            "packages": [],
        }

    coverage_axes = [dict(item) for item in list(report_payload.get("coverage_axes") or [])]
    distinct_counts = dict(report_payload.get("distinct_counts") or {})
    return {
        "status": str(report_payload.get("status") or entry.get("status") or "unknown"),
        "gate_id": gate_id,
        "report_source_path": str(entry.get("report_path") or ""),
        "covered_axis_count": sum(1 for item in coverage_axes if str(item.get("status") or "") == "covered"),
        "partial_axis_count": sum(1 for item in coverage_axes if str(item.get("status") or "") == "partial"),
        "missing_axis_count": sum(1 for item in coverage_axes if str(item.get("status") or "") == "missing"),
        "distinct_counts": {
            str(key): int(value or 0)
            for key, value in distinct_counts.items()
            if str(key)
        },
        "coverage_axes": coverage_axes,
        "packages": [dict(item) for item in list(report_payload.get("per_package_results") or [])],
    }
