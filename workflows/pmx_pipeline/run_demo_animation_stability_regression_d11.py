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
)

GATE_ID = "demo_animation_stability_regression_d11"
ROUND_COUNT = 2
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
    {
        "family": "locomotion",
        "case_id": "walk_forward",
        "animation_asset_path": "/Game/CombatMagicAnims/Demo/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd",
        "animation_sample_time_seconds": 0.65,
    },
]
FIXED_EXECUTION_PROFILE = {
    **D9_FIXED_EXECUTION_PROFILE,
    "required_engine_pass_shots_per_case": 1,
    "required_external_motion_shots_per_case": 1,
    "required_stable_rounds": ROUND_COUNT,
}

def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE D11 demo animation stability regression gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--d10-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()

def default_latest_d10_report_path(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace, REPO_ROOT) / "Saved" / "verification" / "latest_demo_animation_family_regression_d10_report.json"

def resolve_d10_report_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"D10 report path does not exist: {candidate}")
    candidate = default_latest_d10_report_path(workspace)
    if candidate.exists():
        return candidate
    raise FileNotFoundError("No latest_demo_animation_family_regression_d10_report.json could be resolved for D11.")

def build_case_stability_summary(per_round_results: list[dict]) -> list[dict]:
    by_case: dict[str, list[dict]] = {}
    for round_result in per_round_results:
        for case in list(round_result.get("per_case_results") or []):
            by_case.setdefault(str(case.get("case_id") or ""), []).append(case)

    summary = []
    for case_id, entries in sorted(by_case.items()):
        resolved_animation_asset_paths = sorted({str(item.get("resolved_animation_asset_path") or "") for item in entries if str(item.get("resolved_animation_asset_path") or "")})
        retargeted_animation_asset_paths = sorted(
            {
                str((item.get("retarget_generation_summary") or {}).get("retargeted_animation_asset_path") or "")
                for item in entries
                if str((item.get("retarget_generation_summary") or {}).get("retargeted_animation_asset_path") or "")
            }
        )
        retargeter_asset_paths = sorted(
            {
                str((item.get("retarget_generation_summary") or {}).get("retargeter_asset_path") or "")
                for item in entries
                if str((item.get("retarget_generation_summary") or {}).get("retargeter_asset_path") or "")
            }
        )
        summary.append(
            {
                "case_id": case_id,
                "family": entries[0].get("family"),
                "animation_asset_path": entries[0].get("animation_asset_path"),
                "round_count": len(entries),
                "passed_round_count": sum(1 for item in entries if item.get("status") == "pass"),
                "passing_engine_round_count": sum(
                    1
                    for item in entries
                    if int(item.get("counts", {}).get("passing_engine_shots") or 0) >= int(FIXED_EXECUTION_PROFILE["required_engine_pass_shots_per_case"])
                ),
                "passing_external_motion_round_count": sum(
                    1
                    for item in entries
                    if int(item.get("counts", {}).get("passing_external_motion_shots") or 0) >= int(FIXED_EXECUTION_PROFILE["required_external_motion_shots_per_case"])
                ),
                "resolved_animation_asset_paths": resolved_animation_asset_paths,
                "retargeted_animation_asset_paths": retargeted_animation_asset_paths,
                "retargeter_asset_paths": retargeter_asset_paths,
                "stable_resolved_animation_asset_path": len(resolved_animation_asset_paths) == 1,
                "stable_retargeted_animation_asset_path": len(retargeted_animation_asset_paths) == 1,
                "stable_retargeter_asset_path": len(retargeter_asset_paths) == 1,
            }
        )
    return summary

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
    d10_report_path = resolve_d10_report_path(workspace, args.d10_report_path)
    d10_report = load_json(d10_report_path)
    if d10_report.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "d10_prerequisite",
                "D11 requires a passing D10 mixed-family regression report.",
                d10_report_path=str(d10_report_path),
                d10_status=d10_report.get("status"),
            )
        )

    fixed_execution_profile = dict(FIXED_EXECUTION_PROFILE)
    fixed_execution_profile["level_path"] = str(d10_report.get("level_path") or D9_FIXED_EXECUTION_PROFILE["level_path"])
    fixed_execution_profile["round_count"] = ROUND_COUNT
    fixed_execution_profile["animation_cases"] = [dict(item) for item in DEFAULT_ANIMATION_CASES]
    for key in (
        "retarget_source_ik_rig_asset_path",
        "retarget_target_ik_rig_asset_path",
        "retarget_source_mesh_asset_path",
        "retarget_target_mesh_asset_path",
        "pose_probe_bone_names",
    ):
        fixed_execution_profile[key] = (d10_report.get("fixed_execution_profile") or {}).get(key)

    per_round_results = []
    if not failed_requirements:
        for round_index in range(1, ROUND_COUNT + 1):
            round_result = {
                "round_index": round_index,
                "status": "pass",
                "per_case_results": [],
                "failed_requirements": [],
            }
            round_root = output_root / f"round_{round_index:02d}"
            for case_index, case in enumerate(DEFAULT_ANIMATION_CASES, start=1):
                case_profile = dict(fixed_execution_profile)
                case_profile["animation_sample_time_seconds"] = float(case["animation_sample_time_seconds"])
                case_output_root = round_root / f"{case_index:03d}_{case['family']}_{case['case_id']}"
                host_result, host_invocation_error, result_path = run_animation_preview(
                    workspace=workspace,
                    output_root=case_output_root,
                    d8_report=d10_report,
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
                    host_failure_message="The demo host animation-preview command did not complete successfully for this D11 animation run.",
                )
                case_result["family"] = case["family"]
                case_result["case_id"] = case["case_id"]
                case_result["animation_sample_time_seconds"] = float(case["animation_sample_time_seconds"])
                round_result["per_case_results"].append(case_result)

            failing_case_ids = [item["case_id"] for item in round_result["per_case_results"] if item.get("status") != "pass"]
            if failing_case_ids:
                round_result["failed_requirements"].append(
                    make_failed_requirement(
                        "round_case_failure",
                        "All D11 animation cases must pass within each stability round.",
                        round_index=round_index,
                        failing_case_ids=failing_case_ids,
                    )
                )
                round_result["status"] = "fail"
            per_round_results.append(round_result)

    stability_summary = build_case_stability_summary(per_round_results)
    failing_round_indices = [item["round_index"] for item in per_round_results if item.get("status") != "pass"]
    if failing_round_indices:
        failed_requirements.append(
            make_failed_requirement(
                "round_regression_failure",
                "Every D11 stability round must pass the full fixed animation set.",
                required_round_count=ROUND_COUNT,
                passing_round_count=ROUND_COUNT - len(failing_round_indices),
                failing_round_indices=failing_round_indices,
            )
        )

    unstable_case_ids = [
        item["case_id"]
        for item in stability_summary
        if not (
            item.get("stable_resolved_animation_asset_path")
            and item.get("stable_retargeted_animation_asset_path")
            and item.get("stable_retargeter_asset_path")
        )
    ]
    if unstable_case_ids:
        failed_requirements.append(
            make_failed_requirement(
                "retarget_cache_path_drift",
                "D11 requires resolved animation assets and retarget outputs to remain path-stable across repeated runs.",
                unstable_case_ids=unstable_case_ids,
                stability_summary=stability_summary,
            )
        )

    insufficient_round_case_ids = [
        item["case_id"]
        for item in stability_summary
        if int(item.get("passed_round_count") or 0) < ROUND_COUNT
        or int(item.get("passing_engine_round_count") or 0) < ROUND_COUNT
        or int(item.get("passing_external_motion_round_count") or 0) < ROUND_COUNT
    ]
    if insufficient_round_case_ids:
        failed_requirements.append(
            make_failed_requirement(
                "repeated_motion_proof_insufficient",
                "D11 requires every fixed case to pass engine and external motion proof across both rounds.",
                required_round_count=ROUND_COUNT,
                unstable_case_ids=insufficient_round_case_ids,
            )
        )

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(status, failed_requirements, previous_report, previous_report_path, 'd11_first_complete_pass')
    counts = {
        "requested_rounds": ROUND_COUNT,
        "requested_cases_per_round": len(DEFAULT_ANIMATION_CASES),
        "resolved_rounds": len(per_round_results),
        "passing_rounds": sum(1 for item in per_round_results if item.get("status") == "pass"),
        "resolved_case_runs": sum(len(list(item.get("per_case_results") or [])) for item in per_round_results),
        "passing_case_runs": sum(
            1 for round_result in per_round_results for case in list(round_result.get("per_case_results") or []) if case.get("status") == "pass"
        ),
        "stable_case_count": sum(
            1
            for item in stability_summary
            if item.get("stable_resolved_animation_asset_path")
            and item.get("stable_retargeted_animation_asset_path")
            and item.get("stable_retargeter_asset_path")
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
            "package_id": d10_report.get("package_id"),
            "sample_id": d10_report.get("sample_id"),
            "host_blueprint_asset": d10_report.get("host_blueprint_asset"),
            "fixed_execution_profile": fixed_execution_profile,
            "counts": counts,
            "failed_requirements": failed_requirements,
            "per_round_results": per_round_results,
            "stability_summary": stability_summary,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "d10_report_path": str(d10_report_path.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
            },
        },
        "aiue_demo_animation_stability_regression_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_demo_animation_stability_regression_report",
            notes=["internal_demo_animation_stability_regression_gate", "demo_host_only", "repeated_retarget_preview_stability"],
        ),
    )
    report_path = output_root / "d11_demo_animation_stability_regression_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    print(f"D11 demo animation stability regression report written to: {report_path}")
    raise SystemExit(0 if status == "pass" else 1)

if __name__ == "__main__":
    main()



