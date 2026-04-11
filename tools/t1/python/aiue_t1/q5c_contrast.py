from __future__ import annotations

from copy import deepcopy

from aiue_t1.q5c_lite import (
    analyze_q5c_lite,
    closest_margin_info,
    margin_to_failure_by_metric,
    risk_band_for_q5c_lite,
    risk_reason_for_q5c_lite,
)


DEFAULT_SEARCH_OFFSETS = [float(value) for value in range(-80, 82, 2)]


def apply_slot_origin_z_delta(*, host_result: dict, delta_z: float) -> dict:
    mutated = deepcopy(host_result)
    slot_component = dict(mutated.get("slot_component") or {})
    bounds = dict(slot_component.get("bounds") or {})
    origin = dict(bounds.get("origin") or {})
    origin["z"] = float(origin.get("z") or 0.0) + float(delta_z)
    bounds["origin"] = origin
    slot_component["bounds"] = bounds
    mutated["slot_component"] = slot_component
    return mutated


def build_q5c_contrast_case(*, host_result: dict, delta_z: float) -> dict:
    candidate_host_result = apply_slot_origin_z_delta(host_result=host_result, delta_z=delta_z)
    analysis = analyze_q5c_lite(host_result=candidate_host_result)
    threshold_deltas = dict(analysis.get("threshold_deltas") or {})
    margin_map = margin_to_failure_by_metric(threshold_deltas=threshold_deltas)
    closest_margin_metric, closest_margin_value = closest_margin_info(threshold_deltas=threshold_deltas)
    risk_band = risk_band_for_q5c_lite(
        status=str(analysis.get("status") or ""),
        fit_diagnostic_class=str(analysis.get("fit_diagnostic_class") or ""),
        closest_margin_value=float(closest_margin_value),
    )
    risk_reason = risk_reason_for_q5c_lite(
        risk_band=risk_band,
        fit_diagnostic_class=str(analysis.get("fit_diagnostic_class") or ""),
        closest_margin_metric=closest_margin_metric,
        closest_margin_value=float(closest_margin_value),
    )
    return {
        "delta_z": float(delta_z),
        "status": str(analysis.get("status") or ""),
        "fit_diagnostic_class": str(analysis.get("fit_diagnostic_class") or ""),
        "risk_band": risk_band,
        "risk_reason": risk_reason,
        "closest_margin_metric": closest_margin_metric,
        "closest_margin_value": float(closest_margin_value),
        "margin_to_failure_by_metric": margin_map,
        "analysis": analysis,
    }


def _choose_best_pass_reference(candidates: list[dict]) -> dict | None:
    pass_candidates = [item for item in candidates if str(item.get("status") or "") == "pass"]
    if not pass_candidates:
        return None
    return max(
        pass_candidates,
        key=lambda item: (
            float(item.get("closest_margin_value") or 0.0),
            abs(float(item.get("delta_z") or 0.0)),
        ),
    )


def _choose_closest_fail_reference(candidates: list[dict]) -> dict | None:
    fail_candidates = [item for item in candidates if str(item.get("status") or "") == "fail"]
    if not fail_candidates:
        return None
    return min(
        fail_candidates,
        key=lambda item: (
            abs(float(item.get("delta_z") or 0.0)),
            float(item.get("closest_margin_value") or 0.0),
        ),
    )


def _choose_penetration_fail_reference(candidates: list[dict]) -> dict | None:
    fail_candidates = [
        item
        for item in candidates
        if str(item.get("fit_diagnostic_class") or "") in {"penetration_keepout_overlap", "mixed_penetration_and_floating"}
    ]
    if not fail_candidates:
        return None
    return min(
        fail_candidates,
        key=lambda item: (
            abs(float(item.get("delta_z") or 0.0)),
            float(item.get("closest_margin_value") or 0.0),
        ),
    )


def _choose_floating_fail_reference(candidates: list[dict]) -> dict | None:
    fail_candidates = [
        item
        for item in candidates
        if str(item.get("fit_diagnostic_class") or "") == "floating_fit_out_of_range"
    ]
    if not fail_candidates:
        return None
    return min(
        fail_candidates,
        key=lambda item: (
            abs(float(item.get("delta_z") or 0.0)),
            float(item.get("closest_margin_value") or 0.0),
        ),
    )


def generate_q5c_contrast_suite(*, host_result: dict, search_offsets: list[float] | None = None) -> dict:
    offsets = list(search_offsets or DEFAULT_SEARCH_OFFSETS)
    if 0.0 not in offsets:
        offsets.append(0.0)
    ordered_offsets = []
    seen_offsets: set[float] = set()
    for value in offsets:
        normalized = float(value)
        if normalized in seen_offsets:
            continue
        seen_offsets.add(normalized)
        ordered_offsets.append(normalized)

    explored_cases = [build_q5c_contrast_case(host_result=host_result, delta_z=offset) for offset in ordered_offsets]
    baseline_case = next((item for item in explored_cases if float(item.get("delta_z") or 0.0) == 0.0), explored_cases[0])
    non_baseline_cases = [item for item in explored_cases if float(item.get("delta_z") or 0.0) != 0.0]

    selected_cases = []
    seen_case_signatures: set[tuple[float, str, str]] = set()

    def _append_case(case_id: str, payload: dict | None) -> None:
        if not payload:
            return
        signature = (
            float(payload.get("delta_z") or 0.0),
            str(payload.get("fit_diagnostic_class") or ""),
            str(payload.get("risk_band") or ""),
        )
        if signature in seen_case_signatures:
            return
        seen_case_signatures.add(signature)
        selected_cases.append(
            {
                "case_id": case_id,
                **payload,
            }
        )

    _append_case("baseline_current", baseline_case)
    _append_case("best_pass_reference", _choose_best_pass_reference(non_baseline_cases))
    _append_case("closest_fail_reference", _choose_closest_fail_reference(non_baseline_cases))
    _append_case("penetration_fail_reference", _choose_penetration_fail_reference(non_baseline_cases))
    _append_case("floating_fail_reference", _choose_floating_fail_reference(non_baseline_cases))

    risk_band_counts: dict[str, int] = {}
    for item in explored_cases:
        risk_band = str(item.get("risk_band") or "unknown")
        risk_band_counts[risk_band] = risk_band_counts.get(risk_band, 0) + 1

    return {
        "baseline_case_id": "baseline_current",
        "selected_case_ids": [str(item.get("case_id") or "") for item in selected_cases],
        "selected_cases": selected_cases,
        "search_summary": {
            "explored_case_count": len(explored_cases),
            "pass_case_count": sum(1 for item in explored_cases if str(item.get("status") or "") == "pass"),
            "fail_case_count": sum(1 for item in explored_cases if str(item.get("status") or "") == "fail"),
            "risk_band_counts": risk_band_counts,
            "best_pass_reference_found": any(str(item.get("case_id") or "") == "best_pass_reference" for item in selected_cases),
            "closest_fail_reference_found": any(str(item.get("case_id") or "") == "closest_fail_reference" for item in selected_cases),
            "penetration_fail_reference_found": any(str(item.get("case_id") or "") == "penetration_fail_reference" for item in selected_cases),
            "floating_fail_reference_found": any(str(item.get("case_id") or "") == "floating_fail_reference" for item in selected_cases),
        },
    }
