from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _demo_common import default_named_verification_report_path, resolve_report_path, run_host_command_result  # noqa: E402
from _gate_common import (  # noqa: E402
    build_discussion_signal,
    default_latest_report_path,
    default_output_root,
    make_failed_requirement,
    now_utc,
    write_report_pair,
)
from run_demo_action_preview_d2 import FIXED_EXECUTION_PROFILE as D2_PROFILE  # noqa: E402
from run_demo_animation_preview_d3 import DEFAULT_ANIMATION_ASSET_PATH, FIXED_EXECUTION_PROFILE as D3_PROFILE  # noqa: E402
from run_multi_slot_composition_p4 import ready_demo_packages  # noqa: E402

from aiue_core.report_writer import make_compatibility_block, with_report_envelope  # noqa: E402
from aiue_core.schema_utils import load_json, load_workspace_config  # noqa: E402


GATE_ID = "playable_core_smoke_pc1"
DEFAULT_D1_LATEST_NAME = "latest_demo_stage_d1_onboarding_report.json"
DEFAULT_P4_LATEST_NAME = "latest_multi_slot_composition_p4_report.json"
DEFAULT_E2_SESSION_ROUNDTRIP_LATEST_NAME = "latest_playable_demo_e2_session_roundtrip_report.json"
FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "required_package_count": 2,
    "level_path": "/Game/Levels/DefaultLevel",
    "spawn_location": {"x": 0.0, "y": 0.0, "z": 120.0},
    "spawn_rotation": {"pitch": 0.0, "yaw": 180.0, "roll": 0.0},
    "shot_order": ["front", "side"],
    "capture_width": 1280,
    "capture_height": 720,
    "capture_delay_seconds": 0.2,
    "subject_min_screen_coverage": 0.015,
    "weapon_min_screen_coverage": 0.001,
    "action_kind": str(D2_PROFILE["action_kind"]),
    "action_distance": float(D2_PROFILE["action_distance"]),
    "action_yaw_delta": float(D2_PROFILE["action_yaw_delta"]),
    "action_settle_seconds": float(D2_PROFILE["action_settle_seconds"]),
    "action_min_distance_delta": float(D2_PROFILE["min_distance_delta"]),
    "action_min_yaw_delta": float(D2_PROFILE["min_yaw_delta"]),
    "animation_asset_path": DEFAULT_ANIMATION_ASSET_PATH,
    "animation_sample_time_seconds": float(D3_PROFILE["animation_sample_time_seconds"]),
    "animation_settle_seconds": float(D3_PROFILE["animation_settle_seconds"]),
    "required_slots": ["weapon", "clothing", "fx"],
    "max_negative_bottom_z": -10.0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE playable core smoke gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--d1-report-path")
    parser.add_argument("--p4-report-path")
    parser.add_argument("--e2-session-roundtrip-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def default_latest_d1_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_D1_LATEST_NAME)


def default_latest_p4_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_P4_LATEST_NAME)


def default_latest_e2_session_roundtrip_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_E2_SESSION_ROUNDTRIP_LATEST_NAME)


def passing_p4_packages(p4_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("package_id") or ""): dict(item)
        for item in list(p4_report.get("runtime_checks") or [])
        if str(item.get("package_id") or "") and str(item.get("status") or "") == "pass"
    }


def _slot_attach_state(result_payload: dict[str, Any], slot_name: str) -> dict[str, Any]:
    return next(
        (
            dict(item)
            for item in list(result_payload.get("slot_attach_state") or [])
            if str(item.get("slot_name") or "") == slot_name
        ),
        {},
    )


def _slot_switch_ready(result_payload: dict[str, Any], slot_name: str) -> bool:
    managed_component = dict((result_payload.get("managed_components_by_slot") or {}).get(slot_name) or {})
    attach_state = _slot_attach_state(result_payload, slot_name)
    if not str(managed_component.get("component_name") or ""):
        return False
    if attach_state and attach_state.get("resolved_attach_socket_exists") is False:
        return False
    return True


def _subject_visible(result_payload: dict[str, Any]) -> bool:
    for shot in list(result_payload.get("shots") or []):
        before = dict(shot.get("before") or {})
        after = dict(shot.get("after") or {})
        for phase in (before, after):
            if (
                str(phase.get("status") or "") == "pass"
                and bool(phase.get("line_of_sight_clear"))
                and float(phase.get("subject_screen_coverage") or 0.0) >= float(FIXED_EXECUTION_PROFILE["subject_min_screen_coverage"])
            ):
                return True
    return False


def _grounded_summary(action_result: dict[str, Any]) -> dict[str, Any]:
    actor_location = dict((dict(action_result.get("before_actor_transform") or {}).get("location") or {}))
    bounds = dict(action_result.get("main_mesh_bounds") or {})
    origin = dict(bounds.get("origin") or {})
    extent = dict(bounds.get("extent") or {})
    actor_z = float(actor_location.get("z") or 0.0)
    bottom_z = float(origin.get("z") or 0.0) - float(extent.get("z") or 0.0)
    return {
        "actor_z": actor_z,
        "bottom_z": bottom_z,
        "non_zero_bounds": bool(bounds.get("non_zero")),
        "status": "pass"
        if bool(bounds.get("non_zero")) and bottom_z >= float(FIXED_EXECUTION_PROFILE["max_negative_bottom_z"])
        else "fail",
    }


def _action_motion_verified(action_result: dict[str, Any]) -> bool:
    transform_delta = dict(action_result.get("transform_delta") or {})
    return bool(
        str(action_result.get("status") or "") == "pass"
        and (
            float(transform_delta.get("distance_delta") or 0.0) >= float(FIXED_EXECUTION_PROFILE["action_min_distance_delta"])
            or abs(float(transform_delta.get("yaw_delta") or 0.0)) >= float(FIXED_EXECUTION_PROFILE["action_min_yaw_delta"])
        )
    )


def _animation_pose_verified(animation_result: dict[str, Any]) -> bool:
    native_pose = dict(animation_result.get("native_animation_pose_evaluation") or {})
    pose_probe = dict(animation_result.get("pose_probe_delta") or {})
    return bool(
        str(animation_result.get("status") or "") == "pass"
        and (
            bool(native_pose.get("pose_changed"))
            or int(pose_probe.get("moving_bone_count") or 0) > 0
        )
    )


def _run_action_preview(workspace: dict, output_root: Path, package: dict[str, Any], p4_package: dict[str, Any], level_path: str) -> tuple[dict[str, Any], str | None, Path]:
    result_path = output_root / f"{package['package_id']}_pc1_action_preview.json"
    return run_host_command_result(
        workspace=workspace,
        mode=str(FIXED_EXECUTION_PROFILE["mode"]),
        command="action-preview",
        params={
            "package_id": package["package_id"],
            "sample_id": package.get("sample_id"),
            "host_blueprint_asset_path": package["host_blueprint_asset_path"],
            "level_path": level_path,
            "location": dict(FIXED_EXECUTION_PROFILE["spawn_location"]),
            "rotation": dict(FIXED_EXECUTION_PROFILE["spawn_rotation"]),
            "output_root": str((output_root / package["package_id"] / "action_captures").resolve()),
            "shot_order": list(FIXED_EXECUTION_PROFILE["shot_order"]),
            "capture_width": int(FIXED_EXECUTION_PROFILE["capture_width"]),
            "capture_height": int(FIXED_EXECUTION_PROFILE["capture_height"]),
            "capture_delay_seconds": float(FIXED_EXECUTION_PROFILE["capture_delay_seconds"]),
            "subject_min_screen_coverage": float(FIXED_EXECUTION_PROFILE["subject_min_screen_coverage"]),
            "weapon_min_screen_coverage": float(FIXED_EXECUTION_PROFILE["weapon_min_screen_coverage"]),
            "action_kind": str(FIXED_EXECUTION_PROFILE["action_kind"]),
            "action_distance": float(FIXED_EXECUTION_PROFILE["action_distance"]),
            "action_yaw_delta": float(FIXED_EXECUTION_PROFILE["action_yaw_delta"]),
            "action_settle_seconds": float(FIXED_EXECUTION_PROFILE["action_settle_seconds"]),
            "min_distance_delta": float(FIXED_EXECUTION_PROFILE["action_min_distance_delta"]),
            "min_yaw_delta": float(FIXED_EXECUTION_PROFILE["action_min_yaw_delta"]),
            "slot_binding_overrides": [
                dict(p4_package.get("clothing_binding") or {}),
                dict(p4_package.get("fx_binding") or {}),
            ],
            "tracked_slots": ["clothing", "fx"],
        },
        output_path=result_path,
        host_key=str(FIXED_EXECUTION_PROFILE["host_key"]),
    )


def e2_animation_request_paths(e2_roundtrip_report: dict[str, Any]) -> dict[str, Path]:
    request_paths: dict[str, Path] = {}
    if str(e2_roundtrip_report.get("status") or "") != "pass":
        return request_paths
    for item in list(e2_roundtrip_report.get("per_package_results") or []):
        package_id = str(item.get("package_id") or "")
        request_path = str(dict(item.get("animation_invoke") or {}).get("request_json_path") or "")
        if package_id and request_path:
            request_paths[package_id] = Path(request_path).expanduser()
    return request_paths


def _animation_params_from_e2_request(request_path: Path) -> dict[str, Any]:
    request = load_json(request_path)
    params = dict(dict(request.get("request_payload") or {}).get("params") or {})
    if not params:
        raise ValueError(f"E2 animation request did not contain request_payload.params: {request_path}")
    return params


def _fallback_animation_params(package: dict[str, Any], p4_package: dict[str, Any], level_path: str, output_root: Path) -> dict[str, Any]:
    return {
        "package_id": package["package_id"],
        "sample_id": package.get("sample_id"),
        "host_blueprint_asset_path": package["host_blueprint_asset_path"],
        "level_path": level_path,
        "location": dict(FIXED_EXECUTION_PROFILE["spawn_location"]),
        "rotation": dict(FIXED_EXECUTION_PROFILE["spawn_rotation"]),
        "output_root": str((output_root / package["package_id"] / "animation_captures").resolve()),
        "shot_order": list(FIXED_EXECUTION_PROFILE["shot_order"]),
        "capture_width": int(FIXED_EXECUTION_PROFILE["capture_width"]),
        "capture_height": int(FIXED_EXECUTION_PROFILE["capture_height"]),
        "capture_delay_seconds": float(FIXED_EXECUTION_PROFILE["capture_delay_seconds"]),
        "subject_min_screen_coverage": float(FIXED_EXECUTION_PROFILE["subject_min_screen_coverage"]),
        "weapon_min_screen_coverage": float(FIXED_EXECUTION_PROFILE["weapon_min_screen_coverage"]),
        "animation_asset_path": str(FIXED_EXECUTION_PROFILE["animation_asset_path"]),
        "animation_sample_time_seconds": float(FIXED_EXECUTION_PROFILE["animation_sample_time_seconds"]),
        "animation_settle_seconds": float(FIXED_EXECUTION_PROFILE["animation_settle_seconds"]),
        "slot_binding_overrides": [
            dict(p4_package.get("clothing_binding") or {}),
            dict(p4_package.get("fx_binding") or {}),
        ],
        "tracked_slots": ["clothing", "fx"],
    }


def _run_animation_preview(
    workspace: dict,
    output_root: Path,
    package: dict[str, Any],
    p4_package: dict[str, Any],
    level_path: str,
    e2_animation_requests: dict[str, Path],
) -> tuple[dict[str, Any], str | None, Path, str, str | None]:
    result_path = output_root / f"{package['package_id']}_pc1_animation_preview.json"
    request_source = "d3_default"
    request_path: str | None = None
    try:
        e2_request_path = e2_animation_requests.get(str(package.get("package_id") or ""))
        if e2_request_path:
            params = _animation_params_from_e2_request(e2_request_path)
            params.update(
                {
                    "package_id": package["package_id"],
                    "sample_id": package.get("sample_id"),
                    "host_blueprint_asset_path": package["host_blueprint_asset_path"],
                    "level_path": level_path,
                    "location": dict(FIXED_EXECUTION_PROFILE["spawn_location"]),
                    "rotation": dict(FIXED_EXECUTION_PROFILE["spawn_rotation"]),
                    "output_root": str((output_root / package["package_id"] / "animation_captures").resolve()),
                    "capture_width": int(FIXED_EXECUTION_PROFILE["capture_width"]),
                    "capture_height": int(FIXED_EXECUTION_PROFILE["capture_height"]),
                    "capture_delay_seconds": float(FIXED_EXECUTION_PROFILE["capture_delay_seconds"]),
                    "subject_min_screen_coverage": float(FIXED_EXECUTION_PROFILE["subject_min_screen_coverage"]),
                    "weapon_min_screen_coverage": float(FIXED_EXECUTION_PROFILE["weapon_min_screen_coverage"]),
                    "slot_binding_overrides": [
                        dict(p4_package.get("clothing_binding") or {}),
                        dict(p4_package.get("fx_binding") or {}),
                    ],
                    "tracked_slots": ["clothing", "fx"],
                }
            )
            request_source = "e2_session_roundtrip"
            request_path = str(e2_request_path.resolve())
        else:
            params = _fallback_animation_params(package, p4_package, level_path, output_root)
    except Exception as exc:
        params = _fallback_animation_params(package, p4_package, level_path, output_root)
        request_source = "d3_default_after_e2_request_error"
        request_path = f"{type(exc).__name__}: {exc}"
    return run_host_command_result(
        workspace=workspace,
        mode=str(FIXED_EXECUTION_PROFILE["mode"]),
        command="animation-preview",
        params=params,
        output_path=result_path,
        host_key=str(FIXED_EXECUTION_PROFILE["host_key"]),
    ) + (request_source, request_path)


def evaluate_package(
    package: dict[str, Any],
    p4_package: dict[str, Any],
    *,
    action_result: dict[str, Any],
    action_error: str | None,
    action_result_path: Path,
    animation_result: dict[str, Any],
    animation_error: str | None,
    animation_result_path: Path,
    animation_request_source: str,
    animation_request_path: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failed_requirements: list[dict[str, Any]] = []
    package_id = str(package.get("package_id") or "")

    if action_error or str(action_result.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "pc1_action_preview_failed",
                "Playable Core Smoke requires action_preview to execute successfully.",
                package_id=package_id,
                action_result_path=str(action_result_path.resolve()),
                host_error=action_error,
                host_status=str(action_result.get("status") or ""),
            )
        )
    if animation_error or str(animation_result.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "pc1_animation_preview_failed",
                "Playable Core Smoke requires animation_preview to execute successfully.",
                package_id=package_id,
                animation_result_path=str(animation_result_path.resolve()),
                host_error=animation_error,
                host_status=str(animation_result.get("status") or ""),
            )
        )

    grounded = _grounded_summary(action_result)
    if grounded.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "pc1_grounding_failed",
                "Playable Core Smoke requires the spawned host to remain basically grounded.",
                package_id=package_id,
                grounded=grounded,
            )
        )

    if not _subject_visible(action_result):
        failed_requirements.append(
            make_failed_requirement(
                "pc1_action_subject_not_visible",
                "Playable Core Smoke requires the subject to be visible during action_preview.",
                package_id=package_id,
                action_result_path=str(action_result_path.resolve()),
            )
        )
    if not _subject_visible(animation_result):
        failed_requirements.append(
            make_failed_requirement(
                "pc1_animation_subject_not_visible",
                "Playable Core Smoke requires the subject to be visible during animation_preview.",
                package_id=package_id,
                animation_result_path=str(animation_result_path.resolve()),
            )
        )

    action_motion_verified = _action_motion_verified(action_result)
    if not action_motion_verified:
        failed_requirements.append(
            make_failed_requirement(
                "pc1_action_motion_not_verified",
                "Playable Core Smoke requires action_preview to produce meaningful root motion.",
                package_id=package_id,
                transform_delta=dict(action_result.get("transform_delta") or {}),
            )
        )

    animation_pose_verified = _animation_pose_verified(animation_result)
    if not animation_pose_verified:
        failed_requirements.append(
            make_failed_requirement(
                "pc1_animation_pose_not_verified",
                "Playable Core Smoke requires animation_preview to produce pose change evidence.",
                package_id=package_id,
                native_animation_pose_evaluation=dict(animation_result.get("native_animation_pose_evaluation") or {}),
                pose_probe_delta=dict(animation_result.get("pose_probe_delta") or {}),
            )
        )

    slot_switch_results = {
        slot_name: {
            "action_ready": _slot_switch_ready(action_result, slot_name),
            "animation_ready": _slot_switch_ready(animation_result, slot_name),
        }
        for slot_name in list(FIXED_EXECUTION_PROFILE["required_slots"])
    }
    for slot_name, slot_summary in slot_switch_results.items():
        if not (slot_summary["action_ready"] and slot_summary["animation_ready"]):
            failed_requirements.append(
                make_failed_requirement(
                    "pc1_slot_switch_failed",
                    "Playable Core Smoke requires weapon, clothing, and fx slots to remain attached across action and animation preview.",
                    package_id=package_id,
                    slot_name=slot_name,
                    slot_summary=slot_summary,
                )
            )

    return (
        {
            "package_id": package_id,
            "sample_id": str(package.get("sample_id") or ""),
            "host_blueprint_asset": str(package.get("host_blueprint_asset_path") or ""),
            "status": "pass" if not failed_requirements else "fail",
            "grounded_summary": grounded,
            "slot_switch_results": slot_switch_results,
            "action_preview": {
                "status": str(action_result.get("status") or "unknown"),
                "motion_verified": action_motion_verified,
                "transform_delta": dict(action_result.get("transform_delta") or {}),
                "managed_components_by_slot": dict(action_result.get("managed_components_by_slot") or {}),
                "slot_attach_state": list(action_result.get("slot_attach_state") or []),
                "result_path": str(action_result_path.resolve()),
            },
            "animation_preview": {
                "status": str(animation_result.get("status") or "unknown"),
                "request_source": animation_request_source,
                "source_request_path": animation_request_path,
                "pose_verified": animation_pose_verified,
                "native_animation_pose_evaluation": dict(animation_result.get("native_animation_pose_evaluation") or {}),
                "pose_probe_delta": dict(animation_result.get("pose_probe_delta") or {}),
                "managed_components_by_slot": dict(animation_result.get("managed_components_by_slot") or {}),
                "slot_attach_state": list(animation_result.get("slot_attach_state") or []),
                "result_path": str(animation_result_path.resolve()),
            },
            "clothing_binding": dict(p4_package.get("clothing_binding") or {}),
            "fx_binding": dict(p4_package.get("fx_binding") or {}),
            "failed_requirements": failed_requirements,
        },
        failed_requirements,
    )


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)

    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None
    d1_report_path = resolve_report_path(
        args.d1_report_path,
        default_latest_d1_report_path(workspace),
        "No latest_demo_stage_d1_onboarding_report.json could be resolved for PC1.",
    )
    p4_report_path = resolve_report_path(
        args.p4_report_path,
        default_latest_p4_report_path(workspace),
        "No latest_multi_slot_composition_p4_report.json could be resolved for PC1.",
    )
    e2_session_roundtrip_report_path = resolve_report_path(
        args.e2_session_roundtrip_report_path,
        default_latest_e2_session_roundtrip_report_path(workspace),
        "No latest_playable_demo_e2_session_roundtrip_report.json could be resolved for PC1.",
    )
    d1_report = load_json(d1_report_path)
    p4_report = load_json(p4_report_path)
    e2_session_roundtrip_report = load_json(e2_session_roundtrip_report_path)
    e2_animation_requests = e2_animation_request_paths(e2_session_roundtrip_report)

    failed_requirements: list[dict[str, Any]] = []
    if str(d1_report.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "pc1_d1_prerequisite_failed",
                "Playable Core Smoke requires a passing D1 report.",
                d1_report_path=str(d1_report_path.resolve()),
                d1_status=str(d1_report.get("status") or ""),
            )
        )
    if str(p4_report.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "pc1_p4_prerequisite_failed",
                "Playable Core Smoke requires a passing P4 report.",
                p4_report_path=str(p4_report_path.resolve()),
                p4_status=str(p4_report.get("status") or ""),
            )
        )

    d1_packages = ready_demo_packages(d1_report)
    p4_packages = passing_p4_packages(p4_report)
    resolved_packages = [package for package in d1_packages if str(package.get("package_id") or "") in p4_packages]
    if len(resolved_packages) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
        failed_requirements.append(
            make_failed_requirement(
                "pc1_required_package_count_mismatch",
                "Playable Core Smoke requires exactly two shared ready packages across D1 and P4.",
                required_package_count=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                resolved_package_ids=[str(item.get("package_id") or "") for item in resolved_packages],
            )
        )

    level_path = str(d1_report.get("level_path") or FIXED_EXECUTION_PROFILE["level_path"])
    per_package_results: list[dict[str, Any]] = []
    if not failed_requirements:
        for package in resolved_packages:
            package_id = str(package.get("package_id") or "")
            action_result, action_error, action_result_path = _run_action_preview(
                workspace,
                output_root / "action_runs",
                package,
                p4_packages[package_id],
                level_path,
            )
            animation_result, animation_error, animation_result_path, animation_request_source, animation_request_path = _run_animation_preview(
                workspace,
                output_root / "animation_runs",
                package,
                p4_packages[package_id],
                level_path,
                e2_animation_requests,
            )
            package_result, package_failures = evaluate_package(
                package,
                p4_packages[package_id],
                action_result=action_result,
                action_error=action_error,
                action_result_path=action_result_path,
                animation_result=animation_result,
                animation_error=animation_error,
                animation_result_path=animation_result_path,
                animation_request_source=animation_request_source,
                animation_request_path=animation_request_path,
            )
            per_package_results.append(package_result)
            failed_requirements.extend(package_failures)

    counts = {
        "required_package_count": int(FIXED_EXECUTION_PROFILE["required_package_count"]),
        "resolved_package_count": len(resolved_packages),
        "passing_packages": sum(1 for item in per_package_results if str(item.get("status") or "") == "pass"),
        "action_motion_verified": sum(1 for item in per_package_results if bool(dict(item.get("action_preview") or {}).get("motion_verified"))),
        "animation_pose_verified": sum(1 for item in per_package_results if bool(dict(item.get("animation_preview") or {}).get("pose_verified"))),
        "grounded_packages": sum(1 for item in per_package_results if str(dict(item.get("grounded_summary") or {}).get("status") or "") == "pass"),
        "slot_switch_packages": sum(
            1
            for item in per_package_results
            if all(
                bool(slot_summary.get("action_ready")) and bool(slot_summary.get("animation_ready"))
                for slot_summary in list(dict(item.get("slot_switch_results") or {}).values())
            )
        ),
    }
    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        "first_complete_playable_core_smoke_pc1_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
            "source_reports": {
                "d1_report_path": str(d1_report_path.resolve()),
                "p4_report_path": str(p4_report_path.resolve()),
                "e2_session_roundtrip_report_path": str(e2_session_roundtrip_report_path.resolve()),
                "e2_session_roundtrip_status": str(e2_session_roundtrip_report.get("status") or ""),
            },
            "counts": counts,
            "resolved_package_ids": [str(item.get("package_id") or "") for item in resolved_packages],
            "per_package_results": per_package_results,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
            },
        },
        schema_family="aiue_playable_core_smoke_pc1_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_playable_core_smoke_pc1_report",
            notes=[
                "internal_playable_core_smoke",
                "runtime_minimum_only",
                "action_preview_and_animation_preview_backed",
            ],
        ),
    )
    report_path = output_root / "playable_core_smoke_pc1_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
