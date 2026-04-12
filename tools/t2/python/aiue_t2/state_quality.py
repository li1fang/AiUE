from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aiue_t2.state_models import (
    CATEGORY_ORDER,
    ErrorRecord,
    GovernanceBalanceRecord,
    Pv1SignoffRecord,
    PreviewImageRecord,
    ReportRecord,
    TestGovernanceRecord,
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_path(pack_root: Path, relative_path: str) -> Path:
    return (pack_root / Path(relative_path)).resolve()


def load_report_categories(
    *,
    manifest: dict[str, Any],
    pack_root: Path,
    errors: list[ErrorRecord],
) -> tuple[dict[str, list[ReportRecord]], dict[str, ReportRecord]]:
    report_artifacts = list((manifest.get("artifacts") or {}).get("reports") or [])
    artifact_paths_by_gate_id = {
        str(item.get("gate_id") or ""): _artifact_path(pack_root, str(item.get("relative_path") or ""))
        for item in report_artifacts
        if str(item.get("gate_id") or "") and str(item.get("relative_path") or "")
    }
    categories_payload = dict((manifest.get("report_index") or {}).get("categories") or {})
    report_categories: dict[str, list[ReportRecord]] = {key: [] for key in CATEGORY_ORDER}
    reports_by_gate_id: dict[str, ReportRecord] = {}

    for category in CATEGORY_ORDER:
        for entry in list(categories_payload.get(category) or []):
            gate_id = str(entry.get("gate_id") or "")
            artifact_path = artifact_paths_by_gate_id.get(gate_id)
            report_payload: dict[str, Any] = {}
            if artifact_path is None or not artifact_path.exists():
                missing_path = artifact_path or Path(str(entry.get("report_path") or ""))
                errors.append(
                    ErrorRecord(
                        code="artifact_missing",
                        message=f"Missing report artifact for gate '{gate_id or entry.get('name') or 'unknown'}'.",
                        path=str(missing_path),
                    )
                )
            else:
                try:
                    report_payload = _load_json(artifact_path)
                except json.JSONDecodeError as exc:
                    errors.append(
                        ErrorRecord(
                            code="artifact_missing",
                            message=f"Unreadable report artifact JSON for gate '{gate_id or entry.get('name') or 'unknown'}': {exc}",
                            path=str(artifact_path),
                        )
                    )
            record = ReportRecord(
                gate_id=gate_id,
                name=str(entry.get("name") or gate_id or "report"),
                category=category,
                status=str(entry.get("status") or report_payload.get("status") or "unknown"),
                generated_at_utc=str(entry.get("generated_at_utc") or report_payload.get("generated_at_utc") or ""),
                report_artifact_path=str(artifact_path or ""),
                report_source_path=str(entry.get("report_path") or ""),
                report_payload=report_payload,
            )
            report_categories[category].append(record)
            if gate_id:
                reports_by_gate_id[gate_id] = record

    return report_categories, reports_by_gate_id


def load_preview_images(
    *,
    manifest: dict[str, Any],
    pack_root: Path,
    errors: list[ErrorRecord],
) -> list[PreviewImageRecord]:
    preview_images = []
    for entry in list((manifest.get("artifacts") or {}).get("preview_images") or []):
        image_path = _artifact_path(pack_root, str(entry.get("relative_path") or ""))
        if not image_path.exists():
            errors.append(
                ErrorRecord(
                    code="artifact_missing",
                    message=f"Missing preview image '{entry.get('title') or entry.get('key') or 'image'}'.",
                    path=str(image_path),
                )
            )
        preview_images.append(
            PreviewImageRecord(
                key=str(entry.get("key") or ""),
                title=str(entry.get("title") or entry.get("key") or "image"),
                section=str(entry.get("section") or ""),
                image_path=str(image_path),
                source_path=str(entry.get("source_path") or ""),
            )
        )
    return preview_images


def extract_r3_metrics(reports_by_gate_id: dict[str, ReportRecord]) -> list[dict[str, Any]]:
    record = reports_by_gate_id.get("live_fx_visual_quality_r3")
    if not record or not record.report_payload:
        return []
    metrics_rows: list[dict[str, Any]] = []
    for package in list(record.report_payload.get("per_package_results") or []):
        package_id = str(package.get("package_id") or "")
        for shot in list(package.get("shot_results") or []):
            crop_metrics = dict(shot.get("crop_metrics") or {})
            full_metrics = dict(shot.get("full_frame_metrics") or {})
            metrics_rows.append(
                {
                    "package_id": package_id,
                    "shot_id": str(shot.get("shot_id") or ""),
                    "status": str(shot.get("status") or ""),
                    "crop_histogram_l1": float(crop_metrics.get("histogram_l1") or 0.0),
                    "crop_mean_abs_pixel_delta": float(crop_metrics.get("mean_abs_pixel_delta") or 0.0),
                    "full_histogram_l1": float(full_metrics.get("histogram_l1") or 0.0),
                    "full_mean_abs_pixel_delta": float(full_metrics.get("mean_abs_pixel_delta") or 0.0),
                }
            )
    return metrics_rows


def load_quality_summaries(
    *,
    manifest: dict[str, Any],
    pack_root: Path,
    reports_by_gate_id: dict[str, ReportRecord],
    preview_images: list[PreviewImageRecord],
) -> dict[str, Any]:
    payload = dict(manifest.get("quality_summaries") or {})
    diversity_summary = dict(payload.get("diversity_matrix") or {})
    q5c_summary = dict(payload.get("q5c_lite") or {})
    m1_summary = dict(payload.get("m1_material_proof") or {})
    preview_by_key = {
        str(record.key or ""): record
        for record in preview_images
        if str(record.key or "")
    }
    q5c_contrast_summary = _load_q5c_contrast_summary(
        reports_by_gate_id=reports_by_gate_id,
        preview_by_key=preview_by_key,
    )
    if not q5c_summary:
        return {
            "diversity_matrix": diversity_summary or {"status": "missing", "coverage_axes": []},
            "m1_material_proof": m1_summary or {"status": "missing", "packages": []},
            "q5c_lite": {"status": "missing", "packages": [], "diagnostic_class_counts": {}},
            "q5c_contrast": q5c_contrast_summary,
        }

    normalized_packages = []
    for package in list(q5c_summary.get("packages") or []):
        normalized_package = dict(package)
        artifact_rel = str(package.get("artifact_image_relative_path") or "")
        normalized_package["artifact_image_path"] = str(_artifact_path(pack_root, artifact_rel)) if artifact_rel else ""
        normalized_packages.append(normalized_package)
    return {
        "diversity_matrix": diversity_summary or {"status": "missing", "coverage_axes": []},
        "m1_material_proof": m1_summary or {"status": "missing", "packages": []},
        "q5c_lite": {
            **q5c_summary,
            "packages": normalized_packages,
        },
        "q5c_contrast": q5c_contrast_summary,
    }


def _load_q5c_contrast_summary(
    *,
    reports_by_gate_id: dict[str, ReportRecord],
    preview_by_key: dict[str, PreviewImageRecord],
) -> dict[str, Any]:
    record = reports_by_gate_id.get("q5c_lite_contrast_lab")
    if not record or not record.report_payload:
        return {
            "status": "missing",
            "gate_id": "q5c_lite_contrast_lab",
            "report_source_path": "",
            "package_count": 0,
            "passing_package_count": 0,
            "required_case_ids": [],
            "available_case_id_counts": {},
            "packages": [],
        }

    report_payload = dict(record.report_payload or {})
    execution_profile = dict(report_payload.get("fixed_execution_profile") or {})
    required_case_ids = [
        str(item)
        for item in list(execution_profile.get("required_reference_cases") or [])
        if str(item)
    ]
    case_order = {case_id: index for index, case_id in enumerate(required_case_ids)}
    package_rows = []
    available_case_id_counts: dict[str, int] = {}
    for package in list(report_payload.get("per_package_results") or []):
        package_id = str(package.get("package_id") or "")
        case_rows = []
        for case in list(package.get("case_results") or []):
            case_id = str(case.get("case_id") or "")
            if case_id:
                available_case_id_counts[case_id] = available_case_id_counts.get(case_id, 0) + 1
            debug_image_key = f"q5c_contrast_{package_id}_{case_id}" if package_id and case_id else ""
            preview_record = preview_by_key.get(debug_image_key)
            analysis = dict(case.get("analysis") or {})
            case_rows.append(
                {
                    "case_id": case_id,
                    "status": str(case.get("status") or ""),
                    "fit_diagnostic_class": str(case.get("fit_diagnostic_class") or ""),
                    "risk_band": str(case.get("risk_band") or ""),
                    "risk_reason": str(case.get("risk_reason") or ""),
                    "delta_z": float(case.get("delta_z") or 0.0),
                    "closest_margin_metric": str(case.get("closest_margin_metric") or ""),
                    "closest_margin_value": float(case.get("closest_margin_value") or 0.0),
                    "quality_class": str(analysis.get("quality_class") or case.get("quality_class") or ""),
                    "embedding_ratio": _optional_float(analysis.get("embedding_ratio"), fallback=case.get("embedding_ratio")),
                    "floating_ratio": _optional_float(analysis.get("floating_ratio"), fallback=case.get("floating_ratio")),
                    "penetration_ratio": _optional_float(
                        analysis.get("penetration_ratio"),
                        fallback=case.get("penetration_ratio"),
                    ),
                    "local_fit_volume": _optional_float(
                        analysis.get("local_fit_volume"),
                        fallback=case.get("local_fit_volume"),
                    ),
                    "debug_image_key": debug_image_key,
                    "debug_image_path": str(preview_record.image_path if preview_record else ""),
                    "debug_image_source_path": str(preview_record.source_path if preview_record else ""),
                }
            )
        case_rows.sort(key=lambda item: (case_order.get(str(item.get("case_id") or ""), 999), str(item.get("case_id") or "")))
        package_rows.append(
            {
                "package_id": package_id,
                "status": str(package.get("status") or ""),
                "selected_case_ids": [str(item.get("case_id") or "") for item in case_rows if str(item.get("case_id") or "")],
                "search_summary": dict(package.get("search_summary") or {}),
                "cases": case_rows,
            }
        )

    return {
        "status": str(report_payload.get("status") or record.status or "unknown"),
        "gate_id": "q5c_lite_contrast_lab",
        "report_source_path": record.report_source_path,
        "package_count": len(package_rows),
        "passing_package_count": sum(1 for item in package_rows if str(item.get("status") or "") == "pass"),
        "required_case_ids": required_case_ids,
        "available_case_id_counts": available_case_id_counts,
        "packages": package_rows,
    }


def _optional_float(value: Any, *, fallback: Any = None) -> float | None:
    for candidate in (value, fallback):
        if candidate is None:
            continue
        if isinstance(candidate, str) and not candidate.strip():
            continue
        try:
            return float(candidate)
        except (TypeError, ValueError):
            continue
    return None


def _metric_delta(from_case: dict[str, Any], to_case: dict[str, Any], metric_name: str) -> float | None:
    from_value = _optional_float(from_case.get(metric_name))
    to_value = _optional_float(to_case.get(metric_name))
    if from_value is None or to_value is None:
        return None
    return to_value - from_value


def _format_delta(value: float | None, *, precision: int = 4) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.{precision}f}"


def _build_q5c_contrast_compare_rows(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    case_map = {
        str(case.get("case_id") or ""): dict(case)
        for case in cases
        if str(case.get("case_id") or "")
    }
    ordered_pairs = [
        ("baseline_current", "best_pass_reference"),
        ("baseline_current", "closest_fail_reference"),
        ("best_pass_reference", "closest_fail_reference"),
    ]
    compare_rows: list[dict[str, Any]] = []
    for from_case_id, to_case_id in ordered_pairs:
        from_case = case_map.get(from_case_id)
        to_case = case_map.get(to_case_id)
        if not from_case or not to_case:
            continue
        delta_z_change = _metric_delta(from_case, to_case, "delta_z")
        closest_margin_change = _metric_delta(from_case, to_case, "closest_margin_value")
        embedding_ratio_change = _metric_delta(from_case, to_case, "embedding_ratio")
        floating_ratio_change = _metric_delta(from_case, to_case, "floating_ratio")
        penetration_ratio_change = _metric_delta(from_case, to_case, "penetration_ratio")
        local_fit_volume_change = _metric_delta(from_case, to_case, "local_fit_volume")
        status_transition = f"{str(from_case.get('status') or 'unknown')} -> {str(to_case.get('status') or 'unknown')}"
        risk_transition = (
            f"{str(from_case.get('risk_band') or 'unknown')} -> {str(to_case.get('risk_band') or 'unknown')}"
        )
        diagnostic_transition = (
            f"{str(from_case.get('fit_diagnostic_class') or 'unknown')} -> "
            f"{str(to_case.get('fit_diagnostic_class') or 'unknown')}"
        )
        key_delta_parts = []
        if floating_ratio_change is not None:
            key_delta_parts.append(f"floating {_format_delta(floating_ratio_change)}")
        if penetration_ratio_change is not None:
            key_delta_parts.append(f"penetration {_format_delta(penetration_ratio_change)}")
        if embedding_ratio_change is not None:
            key_delta_parts.append(f"embedding {_format_delta(embedding_ratio_change)}")
        if local_fit_volume_change is not None:
            key_delta_parts.append(f"fit_volume {_format_delta(local_fit_volume_change, precision=1)}")
        if not key_delta_parts and closest_margin_change is not None:
            key_delta_parts.append(f"margin {_format_delta(closest_margin_change)}")
        if not key_delta_parts and delta_z_change is not None:
            key_delta_parts.append(f"delta_z {_format_delta(delta_z_change, precision=1)}")
        summary_parts = [
            f"{from_case_id} -> {to_case_id}",
            f"status {status_transition}",
            f"risk {risk_transition}",
        ]
        if delta_z_change is not None:
            summary_parts.append(f"delta_z {_format_delta(delta_z_change, precision=1)}")
        if closest_margin_change is not None:
            summary_parts.append(f"margin {_format_delta(closest_margin_change)}")
        if key_delta_parts:
            summary_parts.append("; ".join(key_delta_parts))
        compare_rows.append(
            {
                "pair_id": f"{from_case_id}_to_{to_case_id}",
                "pair_label": f"{from_case_id} -> {to_case_id}",
                "from_case_id": from_case_id,
                "to_case_id": to_case_id,
                "status_transition": status_transition,
                "risk_transition": risk_transition,
                "diagnostic_transition": diagnostic_transition,
                "delta_z_change": delta_z_change,
                "closest_margin_change": closest_margin_change,
                "embedding_ratio_change": embedding_ratio_change,
                "floating_ratio_change": floating_ratio_change,
                "penetration_ratio_change": penetration_ratio_change,
                "local_fit_volume_change": local_fit_volume_change,
                "key_delta_text": ", ".join(key_delta_parts) if key_delta_parts else "n/a",
                "summary_text": " | ".join(summary_parts),
            }
        )
    return compare_rows


def build_q5c_contrast_focus(
    quality_summaries: dict[str, Any],
    *,
    selected_package_id: str | None,
) -> dict[str, Any]:
    summary = dict((quality_summaries or {}).get("q5c_contrast") or {})
    if not summary or str(summary.get("status") or "missing") == "missing":
        return {
            "status": "missing",
            "selected_package_id": selected_package_id,
            "available_package_ids": [],
            "case_count": 0,
            "case_ids": [],
            "recommended_preview_image_key": None,
            "compare_mode_status": "missing",
            "compare_summary_text": "",
            "compare_rows": [],
            "cases": [],
        }

    packages = list(summary.get("packages") or [])
    selected_package = next(
        (item for item in packages if str(item.get("package_id") or "") == str(selected_package_id or "")),
        None,
    )
    if selected_package is None and packages:
        selected_package = dict(packages[0])
    if selected_package is None:
        return {
            "status": str(summary.get("status") or "unknown"),
            "selected_package_id": selected_package_id,
            "available_package_ids": [],
            "case_count": 0,
            "case_ids": [],
            "recommended_preview_image_key": None,
            "compare_mode_status": "missing",
            "compare_summary_text": "",
            "compare_rows": [],
            "cases": [],
        }

    case_priority = {
        "baseline_current": 0,
        "best_pass_reference": 1,
        "closest_fail_reference": 2,
    }
    cases = sorted(
        [dict(item) for item in list(selected_package.get("cases") or [])],
        key=lambda item: (case_priority.get(str(item.get("case_id") or ""), 999), str(item.get("case_id") or "")),
    )
    recommended_preview_image_key = next(
        (
            str(item.get("debug_image_key") or "")
            for item in cases
            if str(item.get("debug_image_key") or "")
            and str(item.get("case_id") or "") in {"baseline_current", "best_pass_reference", "closest_fail_reference"}
        ),
        "",
    ) or None
    compare_rows = _build_q5c_contrast_compare_rows(cases)
    preferred_compare_row = next(
        (
            row
            for row in compare_rows
            if str(row.get("from_case_id") or "") == "baseline_current"
            and str(row.get("to_case_id") or "") == "closest_fail_reference"
        ),
        compare_rows[0] if compare_rows else None,
    )
    resolved_package_id = str(selected_package.get("package_id") or "") or selected_package_id
    return {
        "status": str(summary.get("status") or "unknown"),
        "selected_package_id": resolved_package_id,
        "available_package_ids": [str(item.get("package_id") or "") for item in packages if str(item.get("package_id") or "")],
        "case_count": len(cases),
        "case_ids": [str(item.get("case_id") or "") for item in cases if str(item.get("case_id") or "")],
        "required_case_ids": [str(item) for item in list(summary.get("required_case_ids") or []) if str(item)],
        "recommended_preview_image_key": recommended_preview_image_key,
        "compare_mode_status": "pass" if compare_rows else "missing",
        "compare_summary_text": str((preferred_compare_row or {}).get("summary_text") or ""),
        "compare_rows": compare_rows,
        "cases": cases,
    }


def extract_governance_balance(reports_by_gate_id: dict[str, ReportRecord]) -> GovernanceBalanceRecord:
    record = reports_by_gate_id.get("dynamic_balance_governance_progress")
    if not record or not record.report_payload:
        return GovernanceBalanceRecord(status="missing")
    report_payload = dict(record.report_payload or {})
    pressure_summary = dict(report_payload.get("pressure_summary") or {})
    recommendation = dict(report_payload.get("recommendation") or {})
    discussion_signal = dict(report_payload.get("discussion_signal") or {})
    repo_state = dict(report_payload.get("repo_state") or {})
    hotspots = [
        str(item.get("relative_path") or "")
        for item in list(repo_state.get("hotspots") or [])
        if str(item.get("relative_path") or "")
    ]
    return GovernanceBalanceRecord(
        status=str(report_payload.get("status") or "unknown"),
        recommended_next_round_kind=str(recommendation.get("next_round_kind") or "") or None,
        discussion_reason=str(discussion_signal.get("reason") or "") or None,
        stability_pressure=str((pressure_summary.get("stability_pressure") or {}).get("level") or "unknown"),
        governance_pressure=str((pressure_summary.get("governance_pressure") or {}).get("level") or "unknown"),
        progress_pressure=str((pressure_summary.get("progress_pressure") or {}).get("level") or "unknown"),
        hotspot_paths=hotspots,
        report_gate_id=record.gate_id,
        report_source_path=record.report_source_path,
    )


def extract_test_governance(reports_by_gate_id: dict[str, ReportRecord]) -> TestGovernanceRecord:
    record = reports_by_gate_id.get("test_governance_round1")
    if not record or not record.report_payload:
        return TestGovernanceRecord(status="missing")

    report_payload = dict(record.report_payload or {})
    executed_lane_results = list(report_payload.get("executed_lane_results") or [])
    checkpoint_readiness = dict(report_payload.get("checkpoint_readiness") or {})
    required_lane_ids = [
        str(item)
        for item in list(report_payload.get("required_lane_ids") or [])
        if str(item)
    ]
    executed_lane_ids = [
        str(item.get("lane_id") or "")
        for item in executed_lane_results
        if str(item.get("lane_id") or "")
    ]
    failed_lane_ids = [
        str(item.get("lane_id") or "")
        for item in executed_lane_results
        if str(item.get("lane_id") or "") and str(item.get("status") or "unknown") != "pass"
    ]
    known_blind_spots = [dict(item) for item in list(report_payload.get("known_blind_spots") or [])]
    high_priority_blind_spot_ids = [
        str(item)
        for item in list(checkpoint_readiness.get("high_priority_blind_spot_ids") or [])
        if str(item)
    ]
    if not high_priority_blind_spot_ids:
        high_priority_blind_spot_ids = [
            str(item.get("axis_id") or "")
            for item in known_blind_spots
            if str(item.get("axis_id") or "") and str(item.get("priority") or "").lower() == "high"
        ]
    high_priority_automation_blind_spot_ids = [
        str(item)
        for item in list(checkpoint_readiness.get("high_priority_automation_blind_spot_ids") or [])
        if str(item)
    ]
    high_priority_signoff_blind_spot_ids = [
        str(item)
        for item in list(checkpoint_readiness.get("high_priority_signoff_blind_spot_ids") or [])
        if str(item)
    ]
    if not high_priority_automation_blind_spot_ids and not high_priority_signoff_blind_spot_ids:
        for item in known_blind_spots:
            axis_id = str(item.get("axis_id") or "")
            if not axis_id or str(item.get("priority") or "").lower() != "high":
                continue
            readiness_domain = str(item.get("readiness_domain") or "").strip().lower()
            if readiness_domain == "manual_signoff" or axis_id == "manual_playable_demo_validation":
                high_priority_signoff_blind_spot_ids.append(axis_id)
            else:
                high_priority_automation_blind_spot_ids.append(axis_id)
    automation_checkpoint_ready = bool(
        checkpoint_readiness.get("automation_checkpoint_ready", checkpoint_readiness.get("ready"))
    )
    signoff_checkpoint_ready = bool(
        checkpoint_readiness.get("signoff_checkpoint_ready", checkpoint_readiness.get("ready"))
    )

    return TestGovernanceRecord(
        status=str(report_payload.get("status") or "unknown"),
        checkpoint_ready=bool(checkpoint_readiness.get("ready")),
        automation_checkpoint_ready=automation_checkpoint_ready,
        signoff_checkpoint_ready=signoff_checkpoint_ready,
        required_lane_ids=required_lane_ids,
        executed_lane_ids=executed_lane_ids,
        failed_lane_ids=failed_lane_ids,
        high_priority_blind_spot_ids=high_priority_blind_spot_ids,
        high_priority_automation_blind_spot_ids=high_priority_automation_blind_spot_ids,
        high_priority_signoff_blind_spot_ids=high_priority_signoff_blind_spot_ids,
        report_gate_id=record.gate_id,
        report_source_path=record.report_source_path,
    )


def extract_pv1_signoff(reports_by_gate_id: dict[str, ReportRecord]) -> Pv1SignoffRecord:
    record = reports_by_gate_id.get("manual_playable_demo_validation_pv1")
    if not record or not record.report_payload:
        return Pv1SignoffRecord(status="missing")

    report_payload = dict(record.report_payload or {})
    checked_packages = [dict(item) for item in list(report_payload.get("checked_packages") or [])]
    checked_package_ids = [
        str(item.get("package_id") or "")
        for item in checked_packages
        if str(item.get("package_id") or "")
    ]
    return Pv1SignoffRecord(
        status=str(report_payload.get("status") or "unknown"),
        requested_signoff_status=str(report_payload.get("requested_signoff_status") or ""),
        operator=str(report_payload.get("operator") or ""),
        notes=str(report_payload.get("notes") or ""),
        success=bool(report_payload.get("success")),
        checked_package_ids=checked_package_ids,
        checked_package_count=len(checked_package_ids),
        source_session_manifest=str(report_payload.get("source_session_manifest") or ""),
        source_e2b_report=str(report_payload.get("source_e2b_report") or ""),
        report_gate_id=record.gate_id,
        report_source_path=record.report_source_path,
    )
