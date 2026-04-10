from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, make_failed_requirement, now_utc, repo_root_from_workspace, run_stamp
from _demo_common import default_named_verification_report_path, extract_quality_subject_report, resolve_report_path

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json

GATE_ID = "demo_shot_quality_gate_q1"
DEFAULT_D12_LATEST_NAME = "latest_demo_cross_bundle_regression_d12_report.json"
DEFAULT_D11_LATEST_NAME = "latest_demo_animation_stability_regression_d11_report.json"
FIXED_EXECUTION_PROFILE = {
    "require_all_phase_shots_to_pass": True,
    "require_subject_in_frame": True,
    "require_subject_center_in_frame": True,
    "require_line_of_sight_clear": True,
    "disallowed_warnings": ["subject_not_visible_in_camera_plan"],
    "disallowed_errors": ["out_of_frame", "occluded", "capture_failed"],
}

def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE Q1 demo shot quality gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--d12-report-path")
    parser.add_argument("--d11-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()

def default_latest_d12_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_D12_LATEST_NAME)

def default_latest_d11_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_D11_LATEST_NAME)

def resolve_source_report_path(workspace: dict, d12_report_path: str | None, d11_report_path: str | None) -> Path:
    if d12_report_path:
        candidate = Path(d12_report_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"D12 report path does not exist: {candidate}")
    default_d12 = default_latest_d12_report_path(workspace)
    if default_d12.exists():
        return default_d12
    if d11_report_path:
        candidate = Path(d11_report_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"D11 report path does not exist: {candidate}")
    default_d11 = default_latest_d11_report_path(workspace)
    if default_d11.exists():
        return default_d11
    raise FileNotFoundError("No latest_demo_cross_bundle_regression_d12_report.json or latest_demo_animation_stability_regression_d11_report.json could be resolved for Q1.")

def phase_shot_status(
    phase_report: dict,
    subject_min_screen_coverage: float,
    require_subject_in_frame: bool,
    require_subject_center_in_frame: bool,
    require_line_of_sight_clear: bool,
    disallowed_warnings: set[str],
    disallowed_errors: set[str],
) -> dict:
    subject_coverage = dict(phase_report.get("subject_coverage") or {})
    quality_gate = dict(phase_report.get("quality_gate") or {})
    warnings = [str(item) for item in (phase_report.get("warnings") or []) if str(item)]
    errors = [str(item) for item in (phase_report.get("errors") or []) if str(item)]
    image_path = str(phase_report.get("image_path") or "")
    image_exists = bool(image_path and Path(image_path).exists())
    subject_screen_coverage = float(phase_report.get("subject_screen_coverage") or subject_coverage.get("coverage_ratio") or 0.0)
    line_of_sight_clear = bool(
        quality_gate.get("line_of_sight_clear")
        if "line_of_sight_clear" in quality_gate
        else phase_report.get("line_of_sight_clear")
    )
    capture_succeeded = bool(quality_gate.get("capture_succeeded")) if "capture_succeeded" in quality_gate else image_exists
    subject_visible = bool(quality_gate.get("subject_visible")) if "subject_visible" in quality_gate else subject_screen_coverage >= subject_min_screen_coverage
    subject_in_frame = subject_coverage.get("in_frame")
    subject_center_in_frame = subject_coverage.get("center_in_frame")
    retained_warnings = sorted({item for item in warnings if item in disallowed_warnings})
    retained_errors = sorted({item for item in errors if item in disallowed_errors})
    failed_checks = []
    if phase_report.get("status") != "pass":
        failed_checks.append("phase_status_fail")
    if not capture_succeeded:
        failed_checks.append("capture_missing")
    if not image_exists:
        failed_checks.append("image_missing")
    if subject_screen_coverage < subject_min_screen_coverage:
        failed_checks.append("subject_coverage_below_threshold")
    if require_subject_in_frame and subject_in_frame is False:
        failed_checks.append("subject_outside_frame")
    if require_subject_center_in_frame and subject_center_in_frame is False:
        failed_checks.append("subject_center_outside_frame")
    if require_line_of_sight_clear and not line_of_sight_clear:
        failed_checks.append("line_of_sight_blocked")
    failed_checks.extend(f"retained_warning:{item}" for item in retained_warnings)
    failed_checks.extend(f"retained_error:{item}" for item in retained_errors)
    return {
        "status": "pass" if not failed_checks else "fail",
        "image_path": image_path,
        "image_exists": image_exists,
        "capture_succeeded": capture_succeeded,
        "subject_visible": subject_visible,
        "subject_screen_coverage": subject_screen_coverage,
        "subject_min_screen_coverage": subject_min_screen_coverage,
        "line_of_sight_clear": line_of_sight_clear,
        "subject_in_frame": subject_in_frame,
        "subject_center_in_frame": subject_center_in_frame,
        "retained_warnings": retained_warnings,
        "retained_errors": retained_errors,
        "failed_checks": failed_checks,
        "camera_plan_assessment": dict(phase_report.get("camera_plan_assessment") or {}),
        "quality_gate": quality_gate,
        "warnings": warnings,
        "errors": errors,
    }

def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    fixed_execution_profile = dict(FIXED_EXECUTION_PROFILE)
    failed_requirements: list[dict] = []
    source_report_path = resolve_source_report_path(workspace, args.d12_report_path, args.d11_report_path)
    source_report = load_json(source_report_path)
    quality_subject_report, source_metadata = extract_quality_subject_report(source_report, source_report_path)

    if quality_subject_report.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "quality_source_prerequisite",
                "Q1 requires a passing D11-like source report before enforcing strict shot quality.",
                source_report_path=str(source_report_path.resolve()),
                source_report_status=quality_subject_report.get("status"),
                source_report_gate_id=quality_subject_report.get("gate_id"),
            )
        )

    subject_min_screen_coverage = float(
        ((quality_subject_report.get("fixed_execution_profile") or {}).get("subject_min_screen_coverage"))
        or 0.015
    )
    fixed_execution_profile["subject_min_screen_coverage"] = subject_min_screen_coverage
    fixed_execution_profile["source_report_kind"] = source_metadata["source_report_kind"]
    fixed_execution_profile["source_gate_id"] = source_metadata["source_gate_id"]

    per_round_results = []
    if not failed_requirements:
        for round_result in list(quality_subject_report.get("per_round_results") or []):
            evaluated_round = {
                "round_index": round_result.get("round_index"),
                "status": "pass",
                "per_case_results": [],
                "failed_requirements": [],
            }
            for case_result in list(round_result.get("per_case_results") or []):
                evaluated_case = {
                    "family": case_result.get("family"),
                    "case_id": case_result.get("case_id"),
                    "animation_asset_path": case_result.get("animation_asset_path"),
                    "status": "pass",
                    "pair_results": [],
                    "failed_requirements": [],
                }
                for pair_shot in list(case_result.get("shots") or []):
                    phase_results = {}
                    pair_failed_checks = []
                    for phase_key in ("before", "after"):
                        phase_report = dict(pair_shot.get(phase_key) or {})
                        phase_results[phase_key] = phase_shot_status(
                            phase_report=phase_report,
                            subject_min_screen_coverage=subject_min_screen_coverage,
                            require_subject_in_frame=bool(FIXED_EXECUTION_PROFILE["require_subject_in_frame"]),
                            require_subject_center_in_frame=bool(FIXED_EXECUTION_PROFILE["require_subject_center_in_frame"]),
                            require_line_of_sight_clear=bool(FIXED_EXECUTION_PROFILE["require_line_of_sight_clear"]),
                            disallowed_warnings=set(FIXED_EXECUTION_PROFILE["disallowed_warnings"]),
                            disallowed_errors=set(FIXED_EXECUTION_PROFILE["disallowed_errors"]),
                        )
                        if phase_results[phase_key]["status"] != "pass":
                            pair_failed_checks.append(f"{phase_key}_phase_failed")

                    retained_pair_warnings = sorted(
                        {
                            item
                            for item in [str(item) for item in (pair_shot.get("warnings") or []) if str(item)]
                            if item in set(FIXED_EXECUTION_PROFILE["disallowed_warnings"])
                        }
                    )
                    retained_pair_errors = sorted(
                        {
                            item
                            for item in [str(item) for item in (pair_shot.get("errors") or []) if str(item)]
                            if item in set(FIXED_EXECUTION_PROFILE["disallowed_errors"])
                        }
                    )
                    pair_failed_checks.extend(f"pair_warning:{item}" for item in retained_pair_warnings)
                    pair_failed_checks.extend(f"pair_error:{item}" for item in retained_pair_errors)
                    evaluated_case["pair_results"].append(
                        {
                            "shot_id": pair_shot.get("shot_id"),
                            "camera_id": pair_shot.get("camera_id"),
                            "status": "pass" if not pair_failed_checks else "fail",
                            "failed_checks": pair_failed_checks,
                            "before": phase_results["before"],
                            "after": phase_results["after"],
                            "retained_pair_warnings": retained_pair_warnings,
                            "retained_pair_errors": retained_pair_errors,
                        }
                    )

                failing_pair_ids = [item.get("shot_id") for item in evaluated_case["pair_results"] if item.get("status") != "pass"]
                if failing_pair_ids:
                    evaluated_case["failed_requirements"].append(
                        make_failed_requirement(
                            "case_shot_quality_failure",
                            "Every before/after shot pair must satisfy the strict Q1 subject visibility gate.",
                            case_id=evaluated_case["case_id"],
                            failing_pair_ids=failing_pair_ids,
                        )
                    )
                    evaluated_case["status"] = "fail"
                evaluated_round["per_case_results"].append(evaluated_case)

            failing_case_ids = [item.get("case_id") for item in evaluated_round["per_case_results"] if item.get("status") != "pass"]
            if failing_case_ids:
                evaluated_round["failed_requirements"].append(
                    make_failed_requirement(
                        "round_shot_quality_failure",
                        "All cases in a Q1 round must pass the strict shot-quality gate.",
                        round_index=evaluated_round["round_index"],
                        failing_case_ids=failing_case_ids,
                    )
                )
                evaluated_round["status"] = "fail"
            per_round_results.append(evaluated_round)

    phase_results_flat = []
    retained_plan_warning_phase_count = 0
    below_threshold_phase_count = 0
    line_of_sight_failure_count = 0
    missing_image_phase_count = 0
    for round_result in per_round_results:
        for case_result in list(round_result.get("per_case_results") or []):
            for pair_result in list(case_result.get("pair_results") or []):
                for phase_key in ("before", "after"):
                    phase_result = dict(pair_result.get(phase_key) or {})
                    phase_result["round_index"] = round_result.get("round_index")
                    phase_result["case_id"] = case_result.get("case_id")
                    phase_result["family"] = case_result.get("family")
                    phase_result["shot_id"] = pair_result.get("shot_id")
                    phase_result["phase"] = phase_key
                    phase_results_flat.append(phase_result)
                    retained_plan_warning_phase_count += int("subject_not_visible_in_camera_plan" in list(phase_result.get("retained_warnings") or []))
                    below_threshold_phase_count += int("subject_coverage_below_threshold" in list(phase_result.get("failed_checks") or []))
                    line_of_sight_failure_count += int("line_of_sight_blocked" in list(phase_result.get("failed_checks") or []))
                    missing_image_phase_count += int("image_missing" in list(phase_result.get("failed_checks") or []))

    failing_round_indices = [item.get("round_index") for item in per_round_results if item.get("status") != "pass"]
    if failing_round_indices:
        failed_requirements.append(
            make_failed_requirement(
                "q1_round_failure",
                "Every round in the Q1 source report must satisfy the strict shot-quality gate.",
                failing_round_indices=failing_round_indices,
            )
        )
    if retained_plan_warning_phase_count:
        failed_requirements.append(
            make_failed_requirement(
                "retained_camera_plan_warning",
                "Q1 does not allow unresolved subject_not_visible_in_camera_plan warnings on passing demo shots.",
                retained_phase_warning_count=retained_plan_warning_phase_count,
            )
        )
    if below_threshold_phase_count:
        failed_requirements.append(
            make_failed_requirement(
                "subject_quality_insufficient",
                "Q1 requires every phase shot to keep the subject above the minimum screen-coverage threshold.",
                below_threshold_phase_count=below_threshold_phase_count,
                subject_min_screen_coverage=subject_min_screen_coverage,
            )
        )
    if line_of_sight_failure_count:
        failed_requirements.append(
            make_failed_requirement(
                "line_of_sight_failures",
                "Q1 requires a clear line of sight for every phase shot.",
                line_of_sight_failure_count=line_of_sight_failure_count,
            )
        )
    if missing_image_phase_count:
        failed_requirements.append(
            make_failed_requirement(
                "missing_image_artifacts",
                "Q1 requires every phase shot image to exist on disk.",
                missing_image_phase_count=missing_image_phase_count,
            )
        )

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(status, failed_requirements, previous_report, previous_report_path, 'q1_first_complete_pass')
    counts = {
        "evaluated_rounds": len(per_round_results),
        "passing_rounds": sum(1 for item in per_round_results if item.get("status") == "pass"),
        "evaluated_cases": sum(len(list(item.get("per_case_results") or [])) for item in per_round_results),
        "passing_cases": sum(
            1 for round_result in per_round_results for case_result in list(round_result.get("per_case_results") or []) if case_result.get("status") == "pass"
        ),
        "evaluated_shot_pairs": sum(
            len(list(case_result.get("pair_results") or []))
            for round_result in per_round_results
            for case_result in list(round_result.get("per_case_results") or [])
        ),
        "passing_shot_pairs": sum(
            1
            for round_result in per_round_results
            for case_result in list(round_result.get("per_case_results") or [])
            for pair_result in list(case_result.get("pair_results") or [])
            if pair_result.get("status") == "pass"
        ),
        "evaluated_phase_shots": len(phase_results_flat),
        "passing_phase_shots": sum(1 for item in phase_results_flat if item.get("status") == "pass"),
        "retained_plan_warning_phase_shots": retained_plan_warning_phase_count,
        "below_subject_threshold_phase_shots": below_threshold_phase_count,
        "line_of_sight_failure_phase_shots": line_of_sight_failure_count,
        "missing_image_phase_shots": missing_image_phase_count,
    }

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": args.workspace_config,
            "host_key": quality_subject_report.get("host_key"),
            "mode": quality_subject_report.get("mode"),
            "level_path": quality_subject_report.get("level_path"),
            "package_id": quality_subject_report.get("package_id"),
            "sample_id": quality_subject_report.get("sample_id"),
            "host_blueprint_asset": quality_subject_report.get("host_blueprint_asset"),
            "fixed_execution_profile": fixed_execution_profile,
            "source_report": source_metadata,
            "counts": counts,
            "failed_requirements": failed_requirements,
            "per_round_results": per_round_results,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "source_report_path": str(source_report_path.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
            },
        },
        "aiue_demo_shot_quality_gate_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_demo_shot_quality_gate_report",
            notes=["internal_demo_shot_quality_gate", "strict_subject_visibility", "d11_or_d12_source"],
        ),
    )
    report_path = output_root / "q1_demo_shot_quality_gate_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    print(f"Q1 demo shot quality gate report written to: {report_path}")
    raise SystemExit(0 if status == "pass" else 1)

if __name__ == "__main__":
    main()


