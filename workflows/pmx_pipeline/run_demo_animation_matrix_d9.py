from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, make_failed_requirement, now_utc, repo_root_from_workspace, run_stamp
from _demo_common import animation_label, evaluate_animation_result, run_animation_preview

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json
from aiue_unreal.host_bridge import run_host_auto_ue_cli

GATE_ID = "demo_animation_matrix_d9"
DEMO_HOST_KEY = "demo"
REQUIRED_MODE = "editor_rendered"
DEFAULT_LEVEL_PATH = "/Game/Levels/DefaultLevel"
DEFAULT_ANIMATION_ASSET_PATHS = [
    "/Game/CombatMagicAnims/Demo/Mannequins/Anims/Unarmed/Attack/MM_Attack_01",
    "/Game/CombatMagicAnims/Demo/Mannequins/Anims/Unarmed/Attack/MM_Attack_02",
    "/Game/CombatMagicAnims/Demo/Mannequins/Anims/Unarmed/Attack/MM_Attack_03",
]
SHOT_ORDER = ["front", "side"]
DEFAULT_SPAWN_LOCATION = {"x": 0.0, "y": 0.0, "z": 120.0}
DEFAULT_SPAWN_ROTATION = {"pitch": 0.0, "yaw": 180.0, "roll": 0.0}
FIXED_EXECUTION_PROFILE = {
    "host_key": DEMO_HOST_KEY,
    "mode": REQUIRED_MODE,
    "level_path": DEFAULT_LEVEL_PATH,
    "shot_order": list(SHOT_ORDER),
    "camera_mode": "explicit_pose",
    "capture_width": 1280,
    "capture_height": 720,
    "capture_delay_seconds": 0.2,
    "subject_min_screen_coverage": 0.015,
    "weapon_min_screen_coverage": 0.001,
    "animation_sample_time_seconds": 0.65,
    "animation_settle_seconds": 0.1,
    "histogram_l1_threshold": 0.015,
    "mean_abs_pixel_delta_threshold": 0.005,
    "required_engine_pass_shots_per_animation": 1,
    "required_external_motion_shots_per_animation": 1,
}

def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE D9 demo animation matrix gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--d8-report-path")
    parser.add_argument("--animation-asset-path", action="append", dest="animation_asset_paths")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()

def default_latest_d8_report_path(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace, REPO_ROOT) / "Saved" / "verification" / "latest_demo_retargeted_animation_preview_d8_report.json"

def resolve_d8_report_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"D8 report path does not exist: {candidate}")
    candidate = default_latest_d8_report_path(workspace)
    if candidate.exists():
        return candidate
    raise FileNotFoundError("No latest_demo_retargeted_animation_preview_d8_report.json could be resolved for D9.")

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
                "D9 requires a passing D8 retargeted animation preview report.",
                d8_report_path=str(d8_report_path),
                d8_status=d8_report.get("status"),
            )
        )

    requested_animation_asset_paths = list(args.animation_asset_paths or DEFAULT_ANIMATION_ASSET_PATHS)
    fixed_execution_profile = dict(FIXED_EXECUTION_PROFILE)
    fixed_execution_profile["level_path"] = str(d8_report.get("level_path") or DEFAULT_LEVEL_PATH)
    fixed_execution_profile["animation_asset_paths"] = list(requested_animation_asset_paths)
    for key in (
        "retarget_source_ik_rig_asset_path",
        "retarget_target_ik_rig_asset_path",
        "retarget_source_mesh_asset_path",
        "retarget_target_mesh_asset_path",
        "pose_probe_bone_names",
    ):
        fixed_execution_profile[key] = (d8_report.get("fixed_execution_profile") or {}).get(key)

    per_animation_results = []
    if not failed_requirements:
        for animation_asset_path in requested_animation_asset_paths:
            host_result, host_invocation_error, result_path = run_animation_preview(
                workspace=workspace,
                output_root=output_root,
                d8_report=d8_report,
                fixed_execution_profile=fixed_execution_profile,
                animation_asset_path=animation_asset_path,
                host_key=DEMO_HOST_KEY,
                mode=REQUIRED_MODE,
                spawn_location=DEFAULT_SPAWN_LOCATION,
                spawn_rotation=DEFAULT_SPAWN_ROTATION,
            )
            per_animation_results.append(
                evaluate_animation_result(
                    repo_root=repo_root,
                    animation_asset_path=animation_asset_path,
                    host_result=host_result,
                    host_invocation_error=host_invocation_error,
                    result_path=result_path,
                    fixed_execution_profile=fixed_execution_profile,
                    required_engine_pass_key="required_engine_pass_shots_per_animation",
                    required_external_motion_key="required_external_motion_shots_per_animation",
                    host_failure_id="animation_preview_host",
                    host_failure_message="The demo host animation-preview command did not complete successfully for this D9 animation run.",
                )
            )

    failing_animations = [item["animation_id"] for item in per_animation_results if item.get("status") != "pass"]
    if failing_animations:
        failed_requirements.append(
            make_failed_requirement(
                "animation_matrix_incomplete",
                "All requested D9 animations must pass retargeted preview and external motion validation.",
                requested_animation_count=len(requested_animation_asset_paths),
                passing_animation_count=len(per_animation_results) - len(failing_animations),
                failing_animation_ids=failing_animations,
            )
        )

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(status, failed_requirements, previous_report, previous_report_path, "d9_first_complete_pass")
    counts = {
        "requested_animations": len(requested_animation_asset_paths),
        "resolved_animations": len(per_animation_results),
        "passing_animations": sum(1 for item in per_animation_results if item.get("status") == "pass"),
        "passing_engine_animations": sum(1 for item in per_animation_results if int(item.get("counts", {}).get("passing_engine_shots") or 0) >= int(FIXED_EXECUTION_PROFILE["required_engine_pass_shots_per_animation"])),
        "passing_external_motion_animations": sum(1 for item in per_animation_results if int(item.get("counts", {}).get("passing_external_motion_shots") or 0) >= int(FIXED_EXECUTION_PROFILE["required_external_motion_shots_per_animation"])),
        "captured_shot_pairs_total": sum(int(item.get("counts", {}).get("captured_shot_pairs") or 0) for item in per_animation_results),
    }

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": args.workspace_config,
            "host_key": DEMO_HOST_KEY,
            "level_path": fixed_execution_profile["level_path"],
            "package_id": d8_report.get("package_id"),
            "sample_id": d8_report.get("sample_id"),
            "host_blueprint_asset": d8_report.get("host_blueprint_asset"),
            "fixed_execution_profile": fixed_execution_profile,
            "requested_animation_asset_paths": requested_animation_asset_paths,
            "counts": counts,
            "failed_requirements": failed_requirements,
            "per_animation_results": per_animation_results,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "d8_report_path": str(d8_report_path.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
            },
        },
        "aiue_demo_animation_matrix_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_demo_animation_matrix_report",
            notes=["internal_demo_animation_matrix_gate", "demo_host_only", "retargeted_multi_animation_evidence"],
        ),
    )
    report_path = output_root / "d9_demo_animation_matrix_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    print(f"D9 demo animation matrix report written to: {report_path}")
    raise SystemExit(0 if status == "pass" else 1)

if __name__ == "__main__":
    main()


