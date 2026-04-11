from __future__ import annotations

import argparse
import math
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _demo_common import default_named_verification_report_path, evaluate_external_motion, resolve_report_path
from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, make_failed_requirement, now_utc, write_report_pair

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config
from aiue_unreal.host_bridge import run_host_auto_ue_cli

GATE_ID = "showcase_demo_e1"
DEFAULT_Q4_LATEST_NAME = "latest_multi_slot_quality_gate_q4_report.json"
DEFAULT_R3_LATEST_NAME = "latest_live_fx_visual_quality_r3_report.json"
DEFAULT_D8_LATEST_NAME = "latest_demo_retargeted_animation_preview_d8_report.json"
DEFAULT_D12_LATEST_NAME = "latest_demo_cross_bundle_regression_d12_report.json"

FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "required_package_count": 2,
    "level_path": "/Game/Levels/DefaultLevel",
    "shot_order": ["front", "side", "top"],
    "spawn_location": {"x": 0.0, "y": 0.0, "z": 120.0},
    "spawn_rotation": {"pitch": 0.0, "yaw": 180.0, "roll": 0.0},
    "target_location": {"x": 0.0, "y": 0.0, "z": 240.0},
    "shot_locations": {
        "front": {"x": 265.0, "y": -24.0, "z": 350.0},
        "side": {"x": -90.0, "y": -335.0, "z": 350.0},
        "top": {"x": 92.0, "y": -82.0, "z": 620.0},
    },
    "capture_width": 1280,
    "capture_height": 720,
    "capture_delay_seconds": 0.2,
    "subject_min_screen_coverage": 0.015,
    "weapon_min_screen_coverage": 0.001,
    "clothing_min_screen_coverage": 0.0005,
    "fx_min_screen_coverage": 0.03,
    "hero_subject_min_screen_coverage": 0.03,
    "hero_weapon_min_screen_coverage": 0.0025,
    "hero_clothing_min_screen_coverage": 0.0005,
    "hero_fx_min_screen_coverage": 0.03,
    "hero_shot_id": "top",
    "required_full_stack_before_shots": 2,
    "required_full_stack_after_shots": 1,
    "required_engine_pass_shots": 2,
    "required_external_motion_shots": 1,
    "histogram_l1_threshold": 0.015,
    "mean_abs_pixel_delta_threshold": 0.005,
    "action_kind": "root_translate_and_turn",
    "action_distance": 85.0,
    "action_yaw_delta": 24.0,
    "action_settle_seconds": 0.2,
    "min_distance_delta": 40.0,
    "min_yaw_delta": 10.0,
    "scene_capture_source": "SCS_FINAL_COLOR_HDR",
    "scene_capture_warmup_count": 4,
    "scene_capture_warmup_delay_seconds": 0.08,
    "niagara_desired_age_seconds": 0.08,
    "niagara_seek_delta_seconds": 1.0 / 60.0,
    "niagara_advance_step_count": 4,
    "niagara_advance_step_delta_seconds": 1.0 / 60.0,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE E1 showcase demo gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--q4-report-path")
    parser.add_argument("--r3-report-path")
    parser.add_argument("--d8-report-path")
    parser.add_argument("--d12-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def default_latest_q4_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_Q4_LATEST_NAME)


def default_latest_r3_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_R3_LATEST_NAME)


def default_latest_d8_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_D8_LATEST_NAME)


def default_latest_d12_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_D12_LATEST_NAME)


def look_at_rotation(camera_location: dict, target_location: dict) -> dict:
    dx = float(target_location["x"]) - float(camera_location["x"])
    dy = float(target_location["y"]) - float(camera_location["y"])
    dz = float(target_location["z"]) - float(camera_location["z"])
    horizontal = max((dx * dx + dy * dy) ** 0.5, 1e-6)
    return {
        "pitch": math.degrees(math.atan2(dz, horizontal)),
        "yaw": math.degrees(math.atan2(dy, dx)),
        "roll": 0.0,
    }


def fixed_shot_plans() -> list[dict]:
    target_location = dict(FIXED_EXECUTION_PROFILE["target_location"])
    payload = []
    for shot_id in FIXED_EXECUTION_PROFILE["shot_order"]:
        camera_location = dict(FIXED_EXECUTION_PROFILE["shot_locations"][shot_id])
        payload.append(
            {
                "shot_id": shot_id,
                "camera_id": shot_id,
                "camera_source": "explicit_pose",
                "camera_location": camera_location,
                "camera_rotation": look_at_rotation(camera_location, target_location),
                "target_location": target_location,
            }
        )
    return payload


def passing_q4_packages(q4_report: dict) -> dict[str, dict]:
    return {
        str(item.get("package_id") or ""): dict(item)
        for item in list(q4_report.get("per_package_results") or [])
        if item.get("status") == "pass" and item.get("package_id")
    }


def passing_r3_packages(r3_report: dict) -> dict[str, dict]:
    return {
        str(item.get("package_id") or ""): dict(item)
        for item in list(r3_report.get("per_package_results") or [])
        if item.get("status") == "pass" and item.get("package_id")
    }


def tracked_slot_coverage(phase: dict, slot_name: str) -> float:
    return float((((phase.get("tracked_slot_coverages") or {}).get(slot_name) or {}).get("coverage_ratio") or 0.0))


def is_full_stack_phase(phase: dict) -> bool:
    return bool(
        phase.get("status") == "pass"
        and float(phase.get("subject_screen_coverage") or 0.0) >= float(FIXED_EXECUTION_PROFILE["subject_min_screen_coverage"])
        and float(phase.get("weapon_screen_coverage") or 0.0) >= float(FIXED_EXECUTION_PROFILE["weapon_min_screen_coverage"])
        and tracked_slot_coverage(phase, "clothing") >= float(FIXED_EXECUTION_PROFILE["clothing_min_screen_coverage"])
        and tracked_slot_coverage(phase, "fx") >= float(FIXED_EXECUTION_PROFILE["fx_min_screen_coverage"])
        and bool(phase.get("line_of_sight_clear"))
    )


def is_hero_phase(phase: dict) -> bool:
    return bool(
        phase.get("status") == "pass"
        and float(phase.get("subject_screen_coverage") or 0.0) >= float(FIXED_EXECUTION_PROFILE["hero_subject_min_screen_coverage"])
        and float(phase.get("weapon_screen_coverage") or 0.0) >= float(FIXED_EXECUTION_PROFILE["hero_weapon_min_screen_coverage"])
        and tracked_slot_coverage(phase, "clothing") >= float(FIXED_EXECUTION_PROFILE["hero_clothing_min_screen_coverage"])
        and tracked_slot_coverage(phase, "fx") >= float(FIXED_EXECUTION_PROFILE["hero_fx_min_screen_coverage"])
        and bool(phase.get("line_of_sight_clear"))
    )


def run_action_preview_for_package(workspace: dict, output_root: Path, package_id: str, q4_package: dict, r3_package: dict, shot_plans: list[dict]) -> tuple[dict, str | None, Path]:
    result_path = output_root / f"{package_id}_showcase_action_preview_result.json"
    host_result = {}
    host_invocation_error = None
    try:
        host_payload = run_host_auto_ue_cli(
            workspace_or_config=workspace,
            mode=str(FIXED_EXECUTION_PROFILE["mode"]),
            command="action-preview",
            params={
                "package_id": package_id,
                "sample_id": q4_package.get("sample_id"),
                "host_blueprint_asset_path": q4_package.get("host_blueprint_asset"),
                "level_path": str(FIXED_EXECUTION_PROFILE["level_path"]),
                "location": dict(FIXED_EXECUTION_PROFILE["spawn_location"]),
                "rotation": dict(FIXED_EXECUTION_PROFILE["spawn_rotation"]),
                "output_root": str((output_root / package_id / "captures").resolve()),
                "shot_order": list(FIXED_EXECUTION_PROFILE["shot_order"]),
                "shot_plans": shot_plans,
                "capture_width": int(FIXED_EXECUTION_PROFILE["capture_width"]),
                "capture_height": int(FIXED_EXECUTION_PROFILE["capture_height"]),
                "capture_delay_seconds": float(FIXED_EXECUTION_PROFILE["capture_delay_seconds"]),
                "subject_min_screen_coverage": float(FIXED_EXECUTION_PROFILE["subject_min_screen_coverage"]),
                "weapon_min_screen_coverage": float(FIXED_EXECUTION_PROFILE["weapon_min_screen_coverage"]),
                "action_kind": str(FIXED_EXECUTION_PROFILE["action_kind"]),
                "action_distance": float(FIXED_EXECUTION_PROFILE["action_distance"]),
                "action_yaw_delta": float(FIXED_EXECUTION_PROFILE["action_yaw_delta"]),
                "action_settle_seconds": float(FIXED_EXECUTION_PROFILE["action_settle_seconds"]),
                "min_distance_delta": float(FIXED_EXECUTION_PROFILE["min_distance_delta"]),
                "min_yaw_delta": float(FIXED_EXECUTION_PROFILE["min_yaw_delta"]),
                "slot_binding_overrides": [
                    dict(q4_package.get("clothing_binding") or {}),
                    dict(r3_package.get("fx_binding") or {}),
                ],
                "tracked_slots": ["clothing", "fx"],
                "scene_capture_source": str(FIXED_EXECUTION_PROFILE["scene_capture_source"]),
                "scene_capture_warmup_count": int(FIXED_EXECUTION_PROFILE["scene_capture_warmup_count"]),
                "scene_capture_warmup_delay_seconds": float(FIXED_EXECUTION_PROFILE["scene_capture_warmup_delay_seconds"]),
                "prime_niagara_before_capture": True,
                "niagara_desired_age_seconds": float(FIXED_EXECUTION_PROFILE["niagara_desired_age_seconds"]),
                "niagara_seek_delta_seconds": float(FIXED_EXECUTION_PROFILE["niagara_seek_delta_seconds"]),
                "niagara_advance_step_count": int(FIXED_EXECUTION_PROFILE["niagara_advance_step_count"]),
                "niagara_advance_step_delta_seconds": float(FIXED_EXECUTION_PROFILE["niagara_advance_step_delta_seconds"]),
                "niagara_flush_world": True,
            },
            output_path=str(result_path.resolve()),
            host_key=str(FIXED_EXECUTION_PROFILE["host_key"]),
        )
        host_result = dict((host_payload.get("payload") or {}).get("result") or {})
    except Exception as exc:
        host_invocation_error = str(exc)
        if result_path.exists():
            host_result = dict((load_json(result_path).get("result") or {}))
    return host_result, host_invocation_error, result_path


def evaluate_showcase_package(repo_root: Path, package_id: str, q4_package: dict, r3_package: dict, host_result: dict, host_invocation_error: str | None, result_path: Path) -> tuple[dict, list[dict]]:
    failed_requirements: list[dict] = []
    if host_result.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e1_action_preview_failed",
                "E1 requires a passing action-preview capture for each showcase package.",
                package_id=package_id,
                host_invocation_error=host_invocation_error,
                host_errors=list(host_result.get("errors") or []),
                result_path=str(result_path.resolve()),
            )
        )

    shots = list(host_result.get("shots") or [])
    passing_engine_shots = sum(1 for shot in shots if shot.get("status") == "pass")
    if passing_engine_shots < int(FIXED_EXECUTION_PROFILE["required_engine_pass_shots"]):
        failed_requirements.append(
            make_failed_requirement(
                "e1_engine_shots_insufficient",
                "E1 requires at least two passing engine-side showcase shots.",
                package_id=package_id,
                required_engine_pass_shots=int(FIXED_EXECUTION_PROFILE["required_engine_pass_shots"]),
                actual_passing_engine_shots=passing_engine_shots,
            )
        )

    external_motion_evidence, passing_external_motion_shots = evaluate_external_motion(
        repo_root,
        shots,
        capture_width=int(FIXED_EXECUTION_PROFILE["capture_width"]),
        capture_height=int(FIXED_EXECUTION_PROFILE["capture_height"]),
        histogram_l1_threshold=float(FIXED_EXECUTION_PROFILE["histogram_l1_threshold"]),
        mean_abs_pixel_delta_threshold=float(FIXED_EXECUTION_PROFILE["mean_abs_pixel_delta_threshold"]),
    )
    if passing_external_motion_shots < int(FIXED_EXECUTION_PROFILE["required_external_motion_shots"]):
        failed_requirements.append(
            make_failed_requirement(
                "e1_external_motion_insufficient",
                "E1 requires at least one fixed shot to show external motion evidence.",
                package_id=package_id,
                required_external_motion_shots=int(FIXED_EXECUTION_PROFILE["required_external_motion_shots"]),
                actual_external_motion_shots=passing_external_motion_shots,
            )
        )

    motion_by_shot = {str(item.get("shot_id") or ""): dict(item) for item in external_motion_evidence}
    shot_results = []
    full_stack_before_count = 0
    full_stack_after_count = 0
    hero_front_pass = False
    required_shot_ids = set(FIXED_EXECUTION_PROFILE["shot_order"])
    seen_shot_ids = set()
    for shot in shots:
        shot_id = str(shot.get("shot_id") or "")
        seen_shot_ids.add(shot_id)
        before = dict(shot.get("before") or {})
        after = dict(shot.get("after") or {})
        motion = dict(motion_by_shot.get(shot_id) or {})
        before_full_stack = is_full_stack_phase(before)
        after_full_stack = is_full_stack_phase(after)
        hero_front = shot_id == str(FIXED_EXECUTION_PROFILE["hero_shot_id"]) and is_hero_phase(before)
        full_stack_before_count += int(before_full_stack)
        full_stack_after_count += int(after_full_stack)
        hero_front_pass = hero_front_pass or hero_front
        shot_results.append(
            {
                "shot_id": shot_id,
                "engine_status": str(shot.get("status") or "fail"),
                "external_motion_status": str(motion.get("status") or "fail"),
                "before_image_path": str((before.get("image_path") or "")),
                "after_image_path": str((after.get("image_path") or "")),
                "before_subject_screen_coverage": float(before.get("subject_screen_coverage") or 0.0),
                "after_subject_screen_coverage": float(after.get("subject_screen_coverage") or 0.0),
                "before_weapon_screen_coverage": float(before.get("weapon_screen_coverage") or 0.0),
                "after_weapon_screen_coverage": float(after.get("weapon_screen_coverage") or 0.0),
                "before_clothing_screen_coverage": tracked_slot_coverage(before, "clothing"),
                "after_clothing_screen_coverage": tracked_slot_coverage(after, "clothing"),
                "before_fx_screen_coverage": tracked_slot_coverage(before, "fx"),
                "after_fx_screen_coverage": tracked_slot_coverage(after, "fx"),
                "before_full_stack": before_full_stack,
                "after_full_stack": after_full_stack,
                "hero_front": hero_front,
                "line_of_sight_before": bool(before.get("line_of_sight_clear")),
                "line_of_sight_after": bool(after.get("line_of_sight_clear")),
                "motion_metrics": dict(motion.get("metrics") or {}),
                "motion_errors": list(motion.get("errors") or []),
            }
        )

    missing_shots = sorted(required_shot_ids - seen_shot_ids)
    if missing_shots:
        failed_requirements.append(
            make_failed_requirement(
                "e1_required_shots_missing",
                "E1 requires all three fixed showcase shots to be present.",
                package_id=package_id,
                missing_shot_ids=missing_shots,
            )
        )
    if not hero_front_pass:
        failed_requirements.append(
            make_failed_requirement(
                "e1_hero_shot_failed",
                "E1 requires the fixed hero shot to show subject, weapon, clothing, and FX together.",
                package_id=package_id,
                hero_shot_id=str(FIXED_EXECUTION_PROFILE["hero_shot_id"]),
            )
        )
    if full_stack_before_count < int(FIXED_EXECUTION_PROFILE["required_full_stack_before_shots"]):
        failed_requirements.append(
            make_failed_requirement(
                "e1_before_full_stack_insufficient",
                "E1 requires at least two fixed shots to preserve the full stack before motion playback.",
                package_id=package_id,
                required_full_stack_before_shots=int(FIXED_EXECUTION_PROFILE["required_full_stack_before_shots"]),
                actual_full_stack_before_shots=full_stack_before_count,
            )
        )
    if full_stack_after_count < int(FIXED_EXECUTION_PROFILE["required_full_stack_after_shots"]):
        failed_requirements.append(
            make_failed_requirement(
                "e1_after_full_stack_insufficient",
                "E1 requires at least one fixed shot to preserve the full stack after motion playback.",
                package_id=package_id,
                required_full_stack_after_shots=int(FIXED_EXECUTION_PROFILE["required_full_stack_after_shots"]),
                actual_full_stack_after_shots=full_stack_after_count,
            )
        )

    return (
        {
            "package_id": package_id,
            "sample_id": q4_package.get("sample_id"),
            "host_blueprint_asset": q4_package.get("host_blueprint_asset"),
            "status": "pass" if not failed_requirements else "fail",
            "action_kind": str(host_result.get("action_kind") or FIXED_EXECUTION_PROFILE["action_kind"]),
            "transform_delta": dict(host_result.get("transform_delta") or {}),
            "clothing_binding": dict(q4_package.get("clothing_binding") or {}),
            "fx_binding": dict(r3_package.get("fx_binding") or {}),
            "slot_bindings": list(host_result.get("slot_bindings") or []),
            "slot_attach_state": list(host_result.get("slot_attach_state") or []),
            "managed_components_by_slot": dict(host_result.get("managed_components_by_slot") or {}),
            "hero_shot_id": str(FIXED_EXECUTION_PROFILE["hero_shot_id"]),
            "shot_results": shot_results,
            "external_motion_evidence": external_motion_evidence,
            "counts": {
                "shots": len(shot_results),
                "full_stack_before_shots": full_stack_before_count,
                "full_stack_after_shots": full_stack_after_count,
                "motion_pass_shots": passing_external_motion_shots,
            },
            "failed_requirements": failed_requirements,
            "artifacts": {
                "result_path": str(result_path.resolve()),
            },
        },
        failed_requirements,
    )


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = Path(workspace["paths"]["aiue_repo_root"]).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict] = []
    q4_report_path = resolve_report_path(args.q4_report_path, default_latest_q4_report_path(workspace), "No latest_multi_slot_quality_gate_q4_report.json could be resolved for E1.")
    r3_report_path = resolve_report_path(args.r3_report_path, default_latest_r3_report_path(workspace), "No latest_live_fx_visual_quality_r3_report.json could be resolved for E1.")
    d8_report_path = resolve_report_path(args.d8_report_path, default_latest_d8_report_path(workspace), "No latest_demo_retargeted_animation_preview_d8_report.json could be resolved for E1.")
    d12_report_path = resolve_report_path(args.d12_report_path, default_latest_d12_report_path(workspace), "No latest_demo_cross_bundle_regression_d12_report.json could be resolved for E1.")

    q4_report = load_json(q4_report_path)
    r3_report = load_json(r3_report_path)
    d8_report = load_json(d8_report_path)
    d12_report = load_json(d12_report_path)

    for gate_name, report_path, report_payload in (
        ("q4", q4_report_path, q4_report),
        ("r3", r3_report_path, r3_report),
        ("d8", d8_report_path, d8_report),
        ("d12", d12_report_path, d12_report),
    ):
        if report_payload.get("status") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    f"e1_prerequisite_{gate_name}_failed",
                    "E1 requires the supporting active/platform gates to pass before showcase capture.",
                    source_gate=gate_name,
                    source_report=str(report_path.resolve()),
                    source_status=report_payload.get("status"),
                )
            )

    q4_packages = passing_q4_packages(q4_report)
    r3_packages = passing_r3_packages(r3_report)
    resolved_package_ids = sorted(set(q4_packages) & set(r3_packages))
    if len(resolved_package_ids) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
        failed_requirements.append(
            make_failed_requirement(
                "e1_required_package_count_mismatch",
                "E1 requires exactly two packages shared across Q4 and R3 evidence.",
                required_package_count=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                resolved_package_ids=resolved_package_ids,
            )
        )

    shot_plans = fixed_shot_plans()
    per_package_results = []
    for package_id in resolved_package_ids:
        host_result, host_invocation_error, result_path = run_action_preview_for_package(
            workspace,
            output_root / "captures",
            package_id,
            q4_packages[package_id],
            r3_packages[package_id],
            shot_plans,
        )
        package_result, package_failures = evaluate_showcase_package(
            repo_root,
            package_id,
            q4_packages[package_id],
            r3_packages[package_id],
            host_result,
            host_invocation_error,
            result_path,
        )
        per_package_results.append(package_result)
        failed_requirements.extend(package_failures)

    counts = {
        "required_package_count": int(FIXED_EXECUTION_PROFILE["required_package_count"]),
        "resolved_package_count": len(resolved_package_ids),
        "packages": len(per_package_results),
        "passing_packages": sum(1 for item in per_package_results if item.get("status") == "pass"),
        "captured_before_images": sum(len(list(item.get("shot_results") or [])) for item in per_package_results),
        "captured_after_images": sum(len(list(item.get("shot_results") or [])) for item in per_package_results),
        "hero_shots_passed": sum(1 for item in per_package_results if any(shot.get("hero_front") for shot in list(item.get("shot_results") or []))),
        "motion_pass_shots": sum(int((item.get("counts") or {}).get("motion_pass_shots") or 0) for item in per_package_results),
    }
    status = "pass" if not failed_requirements and counts["packages"] == counts["passing_packages"] == int(FIXED_EXECUTION_PROFILE["required_package_count"]) else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        first_pass_reason="first_complete_e1_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_reports": {
                "q4_report_path": str(q4_report_path.resolve()),
                "r3_report_path": str(r3_report_path.resolve()),
                "d8_report_path": str(d8_report_path.resolve()),
                "d12_report_path": str(d12_report_path.resolve()),
            },
            "fixed_execution_profile": {
                **FIXED_EXECUTION_PROFILE,
                "shot_plans": shot_plans,
            },
            "counts": counts,
            "failed_requirements": failed_requirements,
            "resolved_package_ids": resolved_package_ids,
            "per_package_results": per_package_results,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
            },
        },
        "aiue_showcase_demo_e1_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_showcase_demo_e1_report",
            notes=[
                "internal_showcase_demo_gate",
                "demo_host_only",
                "evidence_first_demo_lane",
                "action_preview_backed",
            ],
        ),
    )
    report_path = output_root / "showcase_demo_e1_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)


if __name__ == "__main__":
    main()
