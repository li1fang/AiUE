from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()
T1_PYTHON_ROOT = REPO_ROOT / "tools" / "t1" / "python"

import sys

if str(T1_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(T1_PYTHON_ROOT))

from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, make_failed_requirement, now_utc, write_report_pair

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config
from aiue_t1.q5b_volumetric_fit import analyze_volumetric_fit

GATE_ID = "volumetric_fit_inspection_q5b"
DEFAULT_Q5A_LATEST_NAME = "latest_visible_conflict_inspection_q5a_report.json"
FIXED_EXECUTION_PROFILE = {
    "source_gate": "visible_conflict_inspection_q5a",
    "required_package_count": 2,
    "require_color_threshold_only": True,
    "target_slot_name": "clothing",
    "fixture_scope": "p2_echo_hair_fixture",
    "anchor_vertical_ratio_min": 0.85,
    "anchor_vertical_ratio_max": 1.05,
    "anchor_lateral_ratio_max": 1.05,
    "anchor_surface_gap_z_min": -20.0,
    "anchor_surface_gap_z_max": 10.0,
    "slot_min_above_anchor_ratio_min": 5.0,
    "slot_min_above_anchor_ratio_max": 7.0,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE Q5B volumetric fit inspection gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--q5a-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def default_latest_q5a_report_path(workspace: dict) -> Path:
    return Path(workspace["paths"]["aiue_repo_root"]).expanduser().resolve() / "Saved" / "verification" / DEFAULT_Q5A_LATEST_NAME


def resolve_report_path(explicit_path: str | None, fallback_path: Path, missing_message: str) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Report path does not exist: {candidate}")
    if fallback_path.exists():
        return fallback_path
    raise FileNotFoundError(missing_message)


def host_result_payload(package_result: dict) -> tuple[dict | None, str]:
    host_result_path = Path(str(((package_result.get("artifacts") or {}).get("result_path")) or "")).expanduser()
    if not str(host_result_path):
        return None, ""
    if not host_result_path.exists():
        return None, str(host_result_path.resolve())
    payload = load_json(host_result_path)
    return dict(payload.get("result") or {}), str(host_result_path.resolve())


def evaluate_package(package_result: dict) -> tuple[dict, list[dict]]:
    package_id = str(package_result.get("package_id") or "")
    failed_requirements: list[dict] = []
    host_result, host_result_path = host_result_payload(package_result)
    if not host_result:
        failed_requirements.append(
            make_failed_requirement(
                "q5b_host_result_missing",
                "Q5B requires the Q5A host result artifact for each passing package.",
                package_id=package_id,
                host_result_path=host_result_path,
            )
        )
        return (
            {
                "package_id": package_id,
                "sample_id": package_result.get("sample_id"),
                "host_blueprint_asset": package_result.get("host_blueprint_asset"),
                "status": "fail",
                "metrics": {},
                "failed_requirements": failed_requirements,
                "artifacts": {"q5a_host_result_path": host_result_path},
            },
            failed_requirements,
        )

    analysis = analyze_volumetric_fit(
        host_result=host_result,
        thresholds={key: value for key, value in FIXED_EXECUTION_PROFILE.items() if key.endswith(("_min", "_max"))},
    )
    shot_results = list(package_result.get("shot_results") or [])
    if FIXED_EXECUTION_PROFILE["require_color_threshold_only"]:
        non_color_shots = [shot.get("shot_id") for shot in shot_results if str(shot.get("mask_extraction_mode") or "") != "color_threshold"]
        if non_color_shots:
            failed_requirements.append(
                make_failed_requirement(
                    "q5b_requires_color_threshold_source",
                    "Q5B requires the Q5A prerequisite shots to use the stabilized color-threshold path.",
                    package_id=package_id,
                    non_color_shot_ids=non_color_shots,
                )
            )

    for requirement_id in list(analysis.get("failed_requirements") or []):
        failed_requirements.append(
            make_failed_requirement(
                requirement_id,
                "The volumetric fit heuristic did not meet the fixed Q5B range for this clothing fixture.",
                package_id=package_id,
                metrics=dict(analysis.get("metrics") or {}),
            )
        )

    q5a_metrics = {
        "max_body_intrusion_ratio_in_core": max(float((shot.get("metrics") or {}).get("body_intrusion_ratio_in_core") or 0.0) for shot in shot_results) if shot_results else 0.0,
        "min_slot_visible_ratio_in_core": min(float((shot.get("metrics") or {}).get("slot_visible_ratio_in_core") or 0.0) for shot in shot_results) if shot_results else 0.0,
        "shot_modes": [str(shot.get("mask_extraction_mode") or "") for shot in shot_results],
    }

    return (
        {
            "package_id": package_id,
            "sample_id": package_result.get("sample_id"),
            "host_blueprint_asset": package_result.get("host_blueprint_asset"),
            "clothing_binding": dict(package_result.get("clothing_binding") or {}),
            "clothing_attach_state": dict(package_result.get("clothing_attach_state") or {}),
            "status": "pass" if not failed_requirements else "fail",
            "metrics": dict(analysis.get("metrics") or {}),
            "thresholds": dict(analysis.get("thresholds") or {}),
            "q5a_supporting_metrics": q5a_metrics,
            "failed_requirements": failed_requirements,
            "artifacts": {"q5a_host_result_path": host_result_path},
        },
        failed_requirements,
    )


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict] = []
    q5a_report_path = resolve_report_path(
        args.q5a_report_path,
        default_latest_q5a_report_path(workspace),
        "No latest_visible_conflict_inspection_q5a_report.json could be resolved for Q5B.",
    )
    q5a_report = load_json(q5a_report_path)
    if q5a_report.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "q5b_prerequisite_q5a_failed",
                "Q5B requires a passing Q5A visible conflict inspection report.",
                source_report=str(q5a_report_path),
                source_status=q5a_report.get("status"),
            )
        )

    passing_packages = [dict(item) for item in list(q5a_report.get("per_package_results") or []) if item.get("status") == "pass"]
    resolved_package_ids = [str(item.get("package_id") or "") for item in passing_packages if item.get("package_id")]
    if len(passing_packages) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
        failed_requirements.append(
            make_failed_requirement(
                "q5b_required_package_count_mismatch",
                "Q5B requires exactly two passing Q5A packages for the fixed hair fixture.",
                required_package_count=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                resolved_package_ids=resolved_package_ids,
            )
        )

    per_package_results = []
    for package_result in passing_packages:
        evaluation, package_failures = evaluate_package(package_result)
        per_package_results.append(evaluation)
        failed_requirements.extend(package_failures)

    counts = {
        "required_package_count": int(FIXED_EXECUTION_PROFILE["required_package_count"]),
        "resolved_package_count": len(resolved_package_ids),
        "packages": len(per_package_results),
        "passing_packages": sum(1 for item in per_package_results if item.get("status") == "pass"),
        "color_threshold_source_packages": sum(1 for item in per_package_results if all(mode == "color_threshold" for mode in list((item.get("q5a_supporting_metrics") or {}).get("shot_modes") or []))),
    }
    status = "pass" if not failed_requirements and counts["packages"] == counts["passing_packages"] == int(FIXED_EXECUTION_PROFILE["required_package_count"]) else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        first_pass_reason="first_complete_q5b_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_report": str(q5a_report_path.resolve()),
            "fixed_execution_profile": FIXED_EXECUTION_PROFILE,
            "counts": counts,
            "failed_requirements": failed_requirements,
            "resolved_package_ids": resolved_package_ids,
            "per_package_results": per_package_results,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
            },
        },
        "aiue_volumetric_fit_inspection_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_volumetric_fit_inspection_report",
            notes=[
                "internal_q5b_gate",
                "attach_and_bounds_fit_heuristic",
            ],
        ),
    )
    report_path = output_root / f"{GATE_ID}_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)


if __name__ == "__main__":
    main()
