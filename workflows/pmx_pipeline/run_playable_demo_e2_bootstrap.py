from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _demo_common import (
    animation_label,
    default_named_verification_report_path,
    resolve_report_path,
    run_host_command_result,
)
from _gate_common import (
    build_discussion_signal,
    default_latest_report_path,
    default_output_root,
    make_failed_requirement,
    now_utc,
    repo_root_from_workspace,
    write_report_pair,
)

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json

GATE_ID = "playable_demo_e2_bootstrap"
DEFAULT_E1_STABILITY_LATEST_NAME = "latest_showcase_demo_e1_stability_report.json"
DEFAULT_E1_LATEST_NAME = "latest_showcase_demo_e1_report.json"
DEFAULT_Q4_LATEST_NAME = "latest_multi_slot_quality_gate_q4_report.json"
DEFAULT_R3_LATEST_NAME = "latest_live_fx_visual_quality_r3_report.json"
DEFAULT_D8_LATEST_NAME = "latest_demo_retargeted_animation_preview_d8_report.json"
DEFAULT_D12_LATEST_NAME = "latest_demo_cross_bundle_regression_d12_report.json"
DEFAULT_D1_LATEST_NAME = "latest_demo_stage_d1_onboarding_report.json"
RETARGET_PRESET_FIELDS = (
    "retarget_source_ik_rig_asset_path",
    "retarget_target_ik_rig_asset_path",
    "retarget_source_mesh_asset_path",
    "retarget_target_mesh_asset_path",
)

FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "required_package_count": 2,
    "session_smoke_required": True,
    "session_smoke_shot_count_per_package": 1,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE E2 playable demo bootstrap.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--e1-stability-report-path")
    parser.add_argument("--e1-report-path")
    parser.add_argument("--q4-report-path")
    parser.add_argument("--r3-report-path")
    parser.add_argument("--d8-report-path")
    parser.add_argument("--d12-report-path")
    parser.add_argument("--d1-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    parser.add_argument("--session-output-path")
    parser.add_argument("--latest-session-path")
    return parser.parse_args()


def default_latest_e1_stability_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_E1_STABILITY_LATEST_NAME)


def default_latest_e1_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_E1_LATEST_NAME)


def default_latest_q4_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_Q4_LATEST_NAME)


def default_latest_r3_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_R3_LATEST_NAME)


def default_latest_d8_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_D8_LATEST_NAME)


def default_latest_d12_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_D12_LATEST_NAME)


def default_latest_d1_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_D1_LATEST_NAME)


def default_session_output_path(repo_root: Path, output_root: Path) -> Path:
    session_root = repo_root / "Saved" / "demo" / "e2" / output_root.name
    session_root.mkdir(parents=True, exist_ok=True)
    return session_root / "playable_demo_e2_session.json"


def default_latest_session_path(repo_root: Path) -> Path:
    latest_root = repo_root / "Saved" / "demo" / "e2" / "latest"
    latest_root.mkdir(parents=True, exist_ok=True)
    return latest_root / "playable_demo_e2_session.json"


def passing_e1_packages(e1_report: dict) -> dict[str, dict]:
    return {
        str(item.get("package_id") or ""): dict(item)
        for item in list(e1_report.get("per_package_results") or [])
        if item.get("status") == "pass" and item.get("package_id")
    }


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


def passing_d1_packages(d1_report: dict) -> dict[str, dict]:
    package_results = list((((d1_report.get("scene_sweep") or {}).get("result") or {}).get("package_results") or []))
    return {
        str(item.get("package_id") or ""): dict(item)
        for item in package_results
        if item.get("status") == "pass" and item.get("package_id")
    }


def validated_animation_presets_for_primary(d8_report: dict) -> dict[str, list[dict]]:
    package_id = str(d8_report.get("package_id") or "")
    if not package_id or d8_report.get("status") != "pass":
        return {}
    engine_evidence = dict(d8_report.get("engine_evidence") or {})
    retarget_generation = dict(engine_evidence.get("retarget_generation") or {})
    fixed_profile = dict(d8_report.get("fixed_execution_profile") or {})
    preset_payload = {
        "animation_sample_time_seconds": float(fixed_profile.get("animation_sample_time_seconds") or 0.0),
        "pose_probe_bone_names": [str(item) for item in list(fixed_profile.get("pose_probe_bone_names") or []) if str(item)],
    }
    for field_name in RETARGET_PRESET_FIELDS:
        value = str(retarget_generation.get(field_name) or fixed_profile.get(field_name) or "")
        if value:
            preset_payload[field_name] = value
    retargeter_asset_path = str(retarget_generation.get("retargeter_asset_path") or "")
    if retargeter_asset_path:
        preset_payload["retargeter_asset_path"] = retargeter_asset_path
    preset = {
        "preset_id": animation_label(str(engine_evidence.get("animation_asset_path") or fixed_profile.get("animation_asset_path") or "")),
        "family": "attack",
        "case_id": "d8_primary_preview",
        "source_gate_id": str(d8_report.get("gate_id") or "demo_retargeted_animation_preview_d8"),
        "requested_animation_asset_path": str(engine_evidence.get("animation_asset_path") or fixed_profile.get("animation_asset_path") or ""),
        "resolved_animation_asset_path": str(engine_evidence.get("resolved_animation_asset_path") or ""),
        "retargeted_animation_asset_path": str(((engine_evidence.get("retarget_generation") or {}).get("retargeted_animation_asset_path")) or ""),
        "host_blueprint_asset": str(engine_evidence.get("host_blueprint_asset") or d8_report.get("host_blueprint_asset") or ""),
        "status": str(d8_report.get("status") or "unknown"),
        **preset_payload,
    }
    return {package_id: [preset]}


def validated_animation_presets_for_secondary(d12_report: dict) -> dict[str, list[dict]]:
    final_step_report = dict(d12_report.get("final_step_report") or {})
    package_id = str(final_step_report.get("package_id") or d12_report.get("secondary_package_id") or "")
    if not package_id or final_step_report.get("status") != "pass":
        return {}
    round_results = list(final_step_report.get("per_round_results") or [])
    first_round = next((item for item in round_results if item.get("status") == "pass"), {})
    case_results = list(first_round.get("per_case_results") or [])
    fixed_profile = dict(final_step_report.get("fixed_execution_profile") or {})
    animation_cases = list(fixed_profile.get("animation_cases") or [])
    presets = []
    for case_result in case_results:
        if case_result.get("status") != "pass":
            continue
        animation_asset_path = str(case_result.get("animation_asset_path") or "")
        case_profile = next(
            (
                dict(item)
                for item in animation_cases
                if str(item.get("animation_asset_path") or "") == animation_asset_path
            ),
            {},
        )
        preset_payload = {
            "animation_sample_time_seconds": float(case_profile.get("animation_sample_time_seconds") or fixed_profile.get("animation_sample_time_seconds") or 0.0),
            "pose_probe_bone_names": [str(item) for item in list(fixed_profile.get("pose_probe_bone_names") or []) if str(item)],
        }
        for field_name in RETARGET_PRESET_FIELDS:
            value = str(fixed_profile.get(field_name) or "")
            if value:
                preset_payload[field_name] = value
        retargeter_asset_path = str(dict(case_result.get("retarget_generation_summary") or {}).get("retargeter_asset_path") or "")
        if retargeter_asset_path:
            preset_payload["retargeter_asset_path"] = retargeter_asset_path
        presets.append(
            {
                "preset_id": str(case_result.get("animation_id") or animation_label(animation_asset_path)),
                "family": str(case_profile.get("family") or ""),
                "case_id": str(case_profile.get("case_id") or animation_label(animation_asset_path)),
                "source_gate_id": str(final_step_report.get("gate_id") or "demo_animation_stability_regression_d11"),
                "requested_animation_asset_path": animation_asset_path,
                "resolved_animation_asset_path": str(case_result.get("resolved_animation_asset_path") or ""),
                "retargeted_animation_asset_path": str(case_result.get("retargeted_animation_asset_path") or ""),
                "host_blueprint_asset": str(final_step_report.get("host_blueprint_asset") or ""),
                "status": str(case_result.get("status") or "unknown"),
                **preset_payload,
            }
        )
    return {package_id: presets}


def hero_shot_result(package_result: dict) -> dict:
    hero_shot_id = str(package_result.get("hero_shot_id") or "")
    return next((dict(item) for item in list(package_result.get("shot_results") or []) if str(item.get("shot_id") or "") == hero_shot_id), {})


def session_action_preset(package_result: dict, fixed_profile: dict) -> dict:
    transform_delta = dict(package_result.get("transform_delta") or {})
    return {
        "preset_id": "showcase_root_translate_and_turn",
        "action_kind": str(package_result.get("action_kind") or fixed_profile.get("action_kind") or "root_translate_and_turn"),
        "action_distance": float(fixed_profile.get("action_distance") or 85.0),
        "action_yaw_delta": float(fixed_profile.get("action_yaw_delta") or 24.0),
        "action_settle_seconds": float(fixed_profile.get("action_settle_seconds") or 0.2),
        "expected_distance_delta": float(transform_delta.get("distance_delta") or 0.0),
        "expected_yaw_delta": float(transform_delta.get("yaw_delta") or 0.0),
    }


def hero_shot_plan(e1_report: dict, hero_shot_id: str) -> dict:
    fixed_profile = dict(e1_report.get("fixed_execution_profile") or {})
    for plan in list(fixed_profile.get("shot_plans") or []):
        if str(plan.get("shot_id") or "") == hero_shot_id:
            return dict(plan)
    return {}


def session_entry_for_package(
    *,
    package_id: str,
    e1_package: dict,
    q4_package: dict,
    r3_package: dict,
    d1_package: dict,
    e1_report: dict,
    animation_presets_by_package: dict[str, list[dict]],
) -> dict:
    hero_result = hero_shot_result(e1_package)
    hero_shot_id = str(e1_package.get("hero_shot_id") or "top")
    host_blueprint_asset = str(r3_package.get("host_blueprint_asset") or d1_package.get("host_blueprint_asset_path") or "")
    return {
        "package_id": package_id,
        "sample_id": str(e1_package.get("sample_id") or q4_package.get("sample_id") or r3_package.get("sample_id") or d1_package.get("sample_id") or ""),
        "host_blueprint_asset": host_blueprint_asset,
        "level_path": str((e1_report.get("fixed_execution_profile") or {}).get("level_path") or ""),
        "spawn_location": dict((e1_report.get("fixed_execution_profile") or {}).get("spawn_location") or {}),
        "spawn_rotation": dict((e1_report.get("fixed_execution_profile") or {}).get("spawn_rotation") or {}),
        "hero_shot_id": hero_shot_id,
        "hero_shot_plan": hero_shot_plan(e1_report, hero_shot_id),
        "action_presets": [session_action_preset(e1_package, dict(e1_report.get("fixed_execution_profile") or {}))],
        "animation_presets": list(animation_presets_by_package.get(package_id) or []),
        "slot_bindings": list(e1_package.get("slot_bindings") or []),
        "weapon_binding": dict(q4_package.get("weapon_binding") or {}),
        "clothing_binding": dict(e1_package.get("clothing_binding") or q4_package.get("clothing_binding") or {}),
        "fx_binding": dict(e1_package.get("fx_binding") or r3_package.get("fx_binding") or {}),
        "slot_attach_state": list(e1_package.get("slot_attach_state") or []),
        "managed_components_by_slot": dict(e1_package.get("managed_components_by_slot") or {}),
        "evidence": {
            "hero_before_image_path": str(hero_result.get("before_image_path") or ""),
            "hero_after_image_path": str(hero_result.get("after_image_path") or ""),
            "hero_before_full_stack": bool(hero_result.get("before_full_stack")),
            "hero_after_full_stack": bool(hero_result.get("after_full_stack")),
            "motion_metrics": dict(hero_result.get("motion_metrics") or {}),
        },
    }


def evaluate_session_smoke(
    *,
    workspace: dict,
    output_root: Path,
    session_entry: dict,
    e1_report: dict,
) -> tuple[dict, list[dict]]:
    output_root.mkdir(parents=True, exist_ok=True)
    failed_requirements: list[dict] = []
    package_id = str(session_entry.get("package_id") or "")
    level_path = str(session_entry.get("level_path") or "")
    hero_shot_id = str(session_entry.get("hero_shot_id") or "top")
    shot_plan = dict(session_entry.get("hero_shot_plan") or {})
    if not shot_plan:
        failed_requirements.append(
            make_failed_requirement(
                "e2_session_hero_shot_plan_missing",
                "E2 bootstrap requires a hero shot plan for each session entry.",
                package_id=package_id,
                hero_shot_id=hero_shot_id,
            )
        )
        return (
            {
                "package_id": package_id,
                "status": "fail",
                "failed_requirements": failed_requirements,
            },
            failed_requirements,
        )

    load_level_result, load_level_error, load_level_path = run_host_command_result(
        workspace=workspace,
        mode=str(FIXED_EXECUTION_PROFILE["mode"]),
        command="load-level",
        params={"level_path": level_path},
        output_path=output_root / f"{package_id}_load_level_result.json",
        host_key=str(FIXED_EXECUTION_PROFILE["host_key"]),
    )
    if load_level_result.get("loaded") is not True:
        failed_requirements.append(
            make_failed_requirement(
                "e2_session_level_load_failed",
                "E2 bootstrap requires the demo level to load before session smoke runs.",
                package_id=package_id,
                level_path=level_path,
                load_level_error=load_level_error,
                load_level_errors=list(load_level_result.get("errors") or []),
                load_level_result_path=str(load_level_path.resolve()),
            )
        )
        return (
            {
                "package_id": package_id,
                "status": "fail",
                "load_level": load_level_result,
                "artifacts": {"load_level_result_path": str(load_level_path.resolve())},
                "failed_requirements": failed_requirements,
            },
            failed_requirements,
        )

    fixed_profile = dict(e1_report.get("fixed_execution_profile") or {})
    action_preset = dict((session_entry.get("action_presets") or [{}])[0] or {})
    action_result, action_error, action_result_path = run_host_command_result(
        workspace=workspace,
        mode=str(FIXED_EXECUTION_PROFILE["mode"]),
        command="action-preview",
        params={
            "package_id": package_id,
            "sample_id": session_entry.get("sample_id"),
            "host_blueprint_asset_path": session_entry.get("host_blueprint_asset"),
            "level_path": level_path,
            "location": dict(session_entry.get("spawn_location") or {}),
            "rotation": dict(session_entry.get("spawn_rotation") or {}),
            "output_root": str((output_root / package_id / "captures").resolve()),
            "shot_order": [hero_shot_id],
            "shot_plans": [shot_plan],
            "capture_width": int(fixed_profile.get("capture_width") or 1280),
            "capture_height": int(fixed_profile.get("capture_height") or 720),
            "capture_delay_seconds": float(fixed_profile.get("capture_delay_seconds") or 0.2),
            "subject_min_screen_coverage": float(fixed_profile.get("subject_min_screen_coverage") or 0.015),
            "weapon_min_screen_coverage": float(fixed_profile.get("weapon_min_screen_coverage") or 0.001),
            "action_kind": str(action_preset.get("action_kind") or "root_translate_and_turn"),
            "action_distance": float(action_preset.get("action_distance") or 85.0),
            "action_yaw_delta": float(action_preset.get("action_yaw_delta") or 24.0),
            "action_settle_seconds": float(action_preset.get("action_settle_seconds") or 0.2),
            "min_distance_delta": float(fixed_profile.get("min_distance_delta") or 40.0),
            "min_yaw_delta": float(fixed_profile.get("min_yaw_delta") or 10.0),
            "slot_binding_overrides": [
                dict(session_entry.get("clothing_binding") or {}),
                dict(session_entry.get("fx_binding") or {}),
            ],
            "tracked_slots": ["clothing", "fx"],
            "scene_capture_source": str(fixed_profile.get("scene_capture_source") or "SCS_FINAL_COLOR_HDR"),
            "scene_capture_warmup_count": int(fixed_profile.get("scene_capture_warmup_count") or 4),
            "scene_capture_warmup_delay_seconds": float(fixed_profile.get("scene_capture_warmup_delay_seconds") or 0.08),
            "prime_niagara_before_capture": True,
            "niagara_desired_age_seconds": float(fixed_profile.get("niagara_desired_age_seconds") or 0.08),
            "niagara_seek_delta_seconds": float(fixed_profile.get("niagara_seek_delta_seconds") or (1.0 / 60.0)),
            "niagara_advance_step_count": int(fixed_profile.get("niagara_advance_step_count") or 4),
            "niagara_advance_step_delta_seconds": float(fixed_profile.get("niagara_advance_step_delta_seconds") or (1.0 / 60.0)),
            "niagara_flush_world": True,
        },
        output_path=output_root / f"{package_id}_session_smoke_action_result.json",
        host_key=str(FIXED_EXECUTION_PROFILE["host_key"]),
    )
    if action_result.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2_session_smoke_action_failed",
                "E2 bootstrap requires each session entry to survive a one-shot full-stack action preview smoke test.",
                package_id=package_id,
                action_error=action_error,
                action_errors=list(action_result.get("errors") or []),
                action_result_path=str(action_result_path.resolve()),
            )
        )
    slot_names = {str(item.get("slot_name") or "") for item in list(action_result.get("slot_bindings") or [])}
    for required_slot in ("weapon", "clothing", "fx"):
        if required_slot not in slot_names:
            failed_requirements.append(
                make_failed_requirement(
                    "e2_session_slot_missing_in_smoke",
                    "E2 bootstrap requires the session smoke to expose the full stack slot set.",
                    package_id=package_id,
                    missing_slot=required_slot,
                    resolved_slot_names=sorted(slot_names),
                )
            )

    return (
        {
            "package_id": package_id,
            "status": "pass" if not failed_requirements else "fail",
            "load_level": load_level_result,
            "action_preview": {
                "status": str(action_result.get("status") or "fail"),
                "transform_delta": dict(action_result.get("transform_delta") or {}),
                "slot_bindings": list(action_result.get("slot_bindings") or []),
                "slot_attach_state": list(action_result.get("slot_attach_state") or []),
                "managed_components_by_slot": dict(action_result.get("managed_components_by_slot") or {}),
                "shots": list(action_result.get("shots") or []),
            },
            "artifacts": {
                "load_level_result_path": str(load_level_path.resolve()),
                "action_result_path": str(action_result_path.resolve()),
            },
            "failed_requirements": failed_requirements,
        },
        failed_requirements,
    )


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    session_output_path = Path(args.session_output_path).expanduser().resolve() if args.session_output_path else default_session_output_path(repo_root, output_root)
    latest_session_path = Path(args.latest_session_path).expanduser().resolve() if args.latest_session_path else default_latest_session_path(repo_root)
    output_root.mkdir(parents=True, exist_ok=True)
    session_output_path.parent.mkdir(parents=True, exist_ok=True)
    latest_session_path.parent.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict] = []
    e1_stability_report_path = resolve_report_path(args.e1_stability_report_path, default_latest_e1_stability_report_path(workspace), "No latest_showcase_demo_e1_stability_report.json could be resolved for E2 bootstrap.")
    e1_report_path = resolve_report_path(args.e1_report_path, default_latest_e1_report_path(workspace), "No latest_showcase_demo_e1_report.json could be resolved for E2 bootstrap.")
    q4_report_path = resolve_report_path(args.q4_report_path, default_latest_q4_report_path(workspace), "No latest_multi_slot_quality_gate_q4_report.json could be resolved for E2 bootstrap.")
    r3_report_path = resolve_report_path(args.r3_report_path, default_latest_r3_report_path(workspace), "No latest_live_fx_visual_quality_r3_report.json could be resolved for E2 bootstrap.")
    d8_report_path = resolve_report_path(args.d8_report_path, default_latest_d8_report_path(workspace), "No latest_demo_retargeted_animation_preview_d8_report.json could be resolved for E2 bootstrap.")
    d12_report_path = resolve_report_path(args.d12_report_path, default_latest_d12_report_path(workspace), "No latest_demo_cross_bundle_regression_d12_report.json could be resolved for E2 bootstrap.")
    d1_report_path = resolve_report_path(args.d1_report_path, default_latest_d1_report_path(workspace), "No latest_demo_stage_d1_onboarding_report.json could be resolved for E2 bootstrap.")

    e1_stability_report = load_json(e1_stability_report_path)
    e1_report = load_json(e1_report_path)
    q4_report = load_json(q4_report_path)
    r3_report = load_json(r3_report_path)
    d8_report = load_json(d8_report_path)
    d12_report = load_json(d12_report_path)
    d1_report = load_json(d1_report_path)

    for gate_name, report_path, report_payload in (
        ("e1_stability", e1_stability_report_path, e1_stability_report),
        ("e1", e1_report_path, e1_report),
        ("q4", q4_report_path, q4_report),
        ("r3", r3_report_path, r3_report),
        ("d8", d8_report_path, d8_report),
        ("d12", d12_report_path, d12_report),
        ("d1", d1_report_path, d1_report),
    ):
        if report_payload.get("status") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "e2_bootstrap_prerequisite_failed",
                    "E2 bootstrap requires the current demo and platform prerequisites to pass.",
                    source_gate=gate_name,
                    source_report=str(report_path.resolve()),
                    source_status=report_payload.get("status"),
                )
            )

    e1_packages = passing_e1_packages(e1_report)
    q4_packages = passing_q4_packages(q4_report)
    r3_packages = passing_r3_packages(r3_report)
    d1_packages = passing_d1_packages(d1_report)
    animation_presets_by_package = {}
    animation_presets_by_package.update(validated_animation_presets_for_primary(d8_report))
    animation_presets_by_package.update(validated_animation_presets_for_secondary(d12_report))
    resolved_package_ids = sorted(set(e1_packages) & set(q4_packages) & set(r3_packages) & set(d1_packages))
    if len(resolved_package_ids) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
        failed_requirements.append(
            make_failed_requirement(
                "e2_bootstrap_required_package_count_mismatch",
                "E2 bootstrap requires exactly two packages shared across E1, Q4, R3, and D1.",
                required_package_count=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                resolved_package_ids=resolved_package_ids,
            )
        )

    session_entries = []
    for package_id in resolved_package_ids:
        entry = session_entry_for_package(
            package_id=package_id,
            e1_package=e1_packages[package_id],
            q4_package=q4_packages[package_id],
            r3_package=r3_packages[package_id],
            d1_package=d1_packages[package_id],
            e1_report=e1_report,
            animation_presets_by_package=animation_presets_by_package,
        )
        if not entry.get("host_blueprint_asset"):
            failed_requirements.append(
                make_failed_requirement(
                    "e2_bootstrap_host_asset_missing",
                    "E2 bootstrap requires a resolved host blueprint asset for each session entry.",
                    package_id=package_id,
                )
            )
        if not list(entry.get("animation_presets") or []):
            failed_requirements.append(
                make_failed_requirement(
                    "e2_bootstrap_animation_preset_missing",
                    "E2 bootstrap requires at least one validated animation preset per package.",
                    package_id=package_id,
                )
            )
        session_entries.append(entry)

    default_package_id = resolved_package_ids[0] if resolved_package_ids else ""
    session_manifest = {
        "generated_at_utc": now_utc(),
        "session_id": GATE_ID,
        "session_type": "playable_demo_bootstrap",
        "host_key": str(FIXED_EXECUTION_PROFILE["host_key"]),
        "mode": str(FIXED_EXECUTION_PROFILE["mode"]),
        "level_path": str((e1_report.get("fixed_execution_profile") or {}).get("level_path") or ""),
        "default_package_id": default_package_id,
        "switch_order": list(resolved_package_ids),
        "packages": session_entries,
        "source_reports": {
            "e1_stability_report_path": str(e1_stability_report_path.resolve()),
            "e1_report_path": str(e1_report_path.resolve()),
            "q4_report_path": str(q4_report_path.resolve()),
            "r3_report_path": str(r3_report_path.resolve()),
            "d8_report_path": str(d8_report_path.resolve()),
            "d12_report_path": str(d12_report_path.resolve()),
            "d1_report_path": str(d1_report_path.resolve()),
        },
    }

    session_smoke_results = []
    if not failed_requirements and bool(FIXED_EXECUTION_PROFILE["session_smoke_required"]):
        for entry in session_entries:
            result, package_failures = evaluate_session_smoke(
                workspace=workspace,
                output_root=output_root / "session_smoke",
                session_entry=entry,
                e1_report=e1_report,
            )
            session_smoke_results.append(result)
            failed_requirements.extend(package_failures)

    write_json(session_output_path, session_manifest)
    write_json(latest_session_path, session_manifest)

    counts = {
        "required_package_count": int(FIXED_EXECUTION_PROFILE["required_package_count"]),
        "resolved_package_count": len(resolved_package_ids),
        "session_entries": len(session_entries),
        "packages_with_animation_presets": sum(1 for item in session_entries if list(item.get("animation_presets") or [])),
        "session_smoke_passed_packages": sum(1 for item in session_smoke_results if item.get("status") == "pass"),
        "session_smoke_total_packages": len(session_smoke_results),
    }
    status = "pass" if not failed_requirements and counts["resolved_package_count"] == int(FIXED_EXECUTION_PROFILE["required_package_count"]) else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        first_pass_reason="first_complete_playable_demo_e2_bootstrap_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
            "counts": counts,
            "failed_requirements": failed_requirements,
            "default_package_id": default_package_id,
            "resolved_package_ids": resolved_package_ids,
            "session_entries": session_entries,
            "session_smoke_results": session_smoke_results,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "session_output_path": str(session_output_path.resolve()),
                "latest_session_path": str(latest_session_path.resolve()),
            },
        },
        "aiue_playable_demo_e2_bootstrap_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_playable_demo_e2_bootstrap_report",
            notes=[
                "internal_playable_demo_bootstrap",
                "session_manifest_generation",
                "demo_host_full_stack_session_smoke",
            ],
        ),
    )
    report_path = output_root / "playable_demo_e2_bootstrap_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)
    raise SystemExit(0 if status == "pass" else 1)


if __name__ == "__main__":
    main()
