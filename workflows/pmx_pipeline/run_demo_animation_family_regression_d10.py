from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, make_failed_requirement, now_utc, repo_root_from_workspace, run_stamp
from _demo_common import evaluate_animation_result, run_animation_preview

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json
from run_demo_animation_matrix_d9 import (
    DEMO_HOST_KEY,
    REQUIRED_MODE,
    FIXED_EXECUTION_PROFILE as D9_FIXED_EXECUTION_PROFILE,
    resolve_d8_report_path,
)

GATE_ID = "demo_animation_family_regression_d10"
DEFAULT_ANIMATION_CASES = [
    {
        "family": "idle",
        "case_id": "idle_loop",
        "animation_asset_path": "/Game/CombatMagicAnims/Demo/Mannequins/Anims/Unarmed/MM_Idle",
        "animation_sample_time_seconds": 0.65,
    },
    {
        "family": "attack",
        "case_id": "attack_primary",
        "animation_asset_path": "/Game/CombatMagicAnims/Demo/Mannequins/Anims/Unarmed/Attack/MM_Attack_01",
        "animation_sample_time_seconds": 0.65,
    },
    {
        "family": "locomotion",
        "case_id": "jog_forward",
        "animation_asset_path": "/Game/CombatMagicAnims/Demo/Mannequins/Anims/Unarmed/Jog/MF_Unarmed_Jog_Fwd",
        "animation_sample_time_seconds": 0.65,
    },
]
FIXED_EXECUTION_PROFILE = {
    **D9_FIXED_EXECUTION_PROFILE,
    "required_engine_pass_shots_per_case": 1,
    "required_external_motion_shots_per_case": 1,
}

def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE D10 mixed-family demo animation regression gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--d8-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()

def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict] = []
    d8_report_path = resolve_d8_report_path(workspace, args.d8_report_path)
    d8_report = load_json(d8_report_path)
    if d8_report.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "d8_prerequisite",
                "D10 requires a passing D8 retargeted animation preview report.",
                d8_report_path=str(d8_report_path),
                d8_status=d8_report.get("status"),
            )
        )

    fixed_execution_profile = dict(FIXED_EXECUTION_PROFILE)
    fixed_execution_profile["level_path"] = str(d8_report.get("level_path") or D9_FIXED_EXECUTION_PROFILE["level_path"])
    fixed_execution_profile["animation_cases"] = [dict(item) for item in DEFAULT_ANIMATION_CASES]
    for key in (
        "retarget_source_ik_rig_asset_path",
        "retarget_target_ik_rig_asset_path",
        "retarget_source_mesh_asset_path",
        "retarget_target_mesh_asset_path",
        "pose_probe_bone_names",
    ):
        fixed_execution_profile[key] = (d8_report.get("fixed_execution_profile") or {}).get(key)

    per_case_results = []
    if not failed_requirements:
        for index, case in enumerate(DEFAULT_ANIMATION_CASES, start=1):
            case_profile = dict(fixed_execution_profile)
            case_profile["animation_sample_time_seconds"] = float(case["animation_sample_time_seconds"])
            case_output_root = output_root / f"{index:03d}_{case['family']}_{case['case_id']}"
            host_result, host_invocation_error, result_path = run_animation_preview(
                workspace=workspace,
                output_root=case_output_root,
                d8_report=d8_report,
                fixed_execution_profile=case_profile,
                animation_asset_path=str(case["animation_asset_path"]),
                host_key=DEMO_HOST_KEY,
                mode=REQUIRED_MODE,
                spawn_location={"x": 0.0, "y": 0.0, "z": 120.0},
                spawn_rotation={"pitch": 0.0, "yaw": 180.0, "roll": 0.0},
            )
            case_result = evaluate_animation_result(
                repo_root=repo_root,
                animation_asset_path=str(case["animation_asset_path"]),
                host_result=host_result,
                host_invocation_error=host_invocation_error,
                result_path=result_path,
                fixed_execution_profile=case_profile,
                required_engine_pass_key="required_engine_pass_shots_per_case",
                required_external_motion_key="required_external_motion_shots_per_case",
                host_failure_id="animation_preview_host",
                host_failure_message="The demo host animation-preview command did not complete successfully for this D10 animation run.",
            )
            case_result["family"] = case["family"]
            case_result["case_id"] = case["case_id"]
            case_result["animation_sample_time_seconds"] = float(case["animation_sample_time_seconds"])
            per_case_results.append(case_result)

    failed_case_ids = [item["case_id"] for item in per_case_results if item.get("status") != "pass"]
    if failed_case_ids:
        failed_requirements.append(
            make_failed_requirement(
                "animation_family_regression_incomplete",
                "All D10 mixed-family animation cases must pass retarget preview and external motion validation.",
                requested_case_count=len(DEFAULT_ANIMATION_CASES),
                passing_case_count=len(per_case_results) - len(failed_case_ids),
                failing_case_ids=failed_case_ids,
            )
        )

    expected_families = sorted({item["family"] for item in DEFAULT_ANIMATION_CASES})
    passed_families = sorted({item["family"] for item in per_case_results if item.get("status") == "pass"})
    missing_families = [family for family in expected_families if family not in passed_families]
    if missing_families:
        failed_requirements.append(
            make_failed_requirement(
                "motion_family_coverage_missing",
                "D10 requires passing coverage across idle, attack, and locomotion families.",
                expected_families=expected_families,
                passing_families=passed_families,
                missing_families=missing_families,
            )
        )

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(status, failed_requirements, previous_report, previous_report_path, "d10_first_complete_pass")
    counts = {
        "requested_cases": len(DEFAULT_ANIMATION_CASES),
        "resolved_cases": len(per_case_results),
        "passing_cases": sum(1 for item in per_case_results if item.get("status") == "pass"),
        "passing_families": len(passed_families),
        "captured_shot_pairs_total": sum(int(item.get("counts", {}).get("captured_shot_pairs") or 0) for item in per_case_results),
        "passing_engine_cases": sum(
            1
            for item in per_case_results
            if int(item.get("counts", {}).get("passing_engine_shots") or 0) >= int(FIXED_EXECUTION_PROFILE["required_engine_pass_shots_per_case"])
        ),
        "passing_external_motion_cases": sum(
            1
            for item in per_case_results
            if int(item.get("counts", {}).get("passing_external_motion_shots") or 0) >= int(FIXED_EXECUTION_PROFILE["required_external_motion_shots_per_case"])
        ),
    }

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": args.workspace_config,
            "host_key": DEMO_HOST_KEY,
            "mode": REQUIRED_MODE,
            "level_path": fixed_execution_profile["level_path"],
            "package_id": d8_report.get("package_id"),
            "sample_id": d8_report.get("sample_id"),
            "host_blueprint_asset": d8_report.get("host_blueprint_asset"),
            "fixed_execution_profile": fixed_execution_profile,
            "expected_families": expected_families,
            "counts": counts,
            "failed_requirements": failed_requirements,
            "per_case_results": per_case_results,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "d8_report_path": str(d8_report_path.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
            },
        },
        "aiue_demo_animation_family_regression_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_demo_animation_family_regression_report",
            notes=["internal_demo_animation_family_regression_gate", "demo_host_only", "mixed_family_retarget_preview"],
        ),
    )
    report_path = output_root / "d10_demo_animation_family_regression_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    print(f"D10 demo animation family regression report written to: {report_path}")
    raise SystemExit(0 if status == "pass" else 1)

if __name__ == "__main__":
    main()



