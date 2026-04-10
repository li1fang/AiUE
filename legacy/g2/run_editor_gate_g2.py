from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json
from aiue_unreal.host_bridge import run_host_auto_ue_cli
from run_editor_gate_g1 import (
    REQUIRED_MODE,
    REQUIRED_PACKAGE_COUNT,
    REQUIRED_SOCKET,
    aggregate_counts,
    evaluate_scenario_capture as evaluate_g1_scenario_capture,
    make_failed_requirement,
    normalize_failed_requirement_ids,
    now_utc,
    repo_root_from_workspace,
    resolve_equipment_report_path,
    resolve_summary_path,
    run_stamp,
    select_target_packages,
    verify_editor_capture_capability,
)

GATE_ID = "editor_fixed_stage_g2"
STAGE_PROFILE_PATH = Path(__file__).with_name("editor_fixed_stage_g2.stage.json")
SCENARIO_ORDER = ["idle_2s", "walk_forward_2s", "run_forward_2s", "jump_land_1cycle"]
FIXED_EXECUTION_PROFILE = {
    "mode": REQUIRED_MODE,
    "camera_mode": "anchor_actor",
    "completion_strategy": "native_helper_wait",
    "level_lifecycle": "reuse_level",
    "camera_lifecycle": "reuse_camera",
    "scenario_scheduling": "single_scenario",
    "scenario_order": list(SCENARIO_ORDER),
    "capture_delay_seconds": 0.2,
    "settle_timeout_seconds": 6.0,
    "file_stability_window_seconds": 0.75,
    "viewport_pump_interval_seconds": 0.05,
    "quit_barrier_seconds": 2.0,
    "finalize_wait_seconds": 8,
}
BOOTSTRAP_STAGE_TEMPLATE = {
    "idle_2s": {
        "spawn_location": {"x": 440.0, "y": 90.0, "z": 32.88926724241901},
        "spawn_rotation": {"pitch": 0.0, "yaw": 90.0, "roll": 0.0},
        "camera_location": {"x": 665.2429627385732, "y": -70.0, "z": 110.91632992236356},
        "camera_rotation": {"pitch": -4.793184129333487, "yaw": 153.434948822922, "roll": 9.931552300260824e-08},
    },
    "walk_forward_2s": {
        "spawn_location": {"x": 560.0, "y": 120.0, "z": 32.88926724241901},
        "spawn_rotation": {"pitch": 0.0, "yaw": 105.0, "roll": 0.0},
        "camera_location": {"x": 751.3226639593563, "y": -25.00000000000003, "z": 55.362032144599145},
        "camera_rotation": {"pitch": 10.69083302460323, "yaw": 153.41737376103413, "roll": -2.2046442718196766e-07},
    },
    "run_forward_2s": {
        "spawn_location": {"x": 690.0, "y": 35.0, "z": 32.88926724241901},
        "spawn_rotation": {"pitch": 0.0, "yaw": 88.0, "roll": 0.0},
        "camera_location": {"x": 846.4644305574022, "y": -85.0, "z": 19.088594433457403},
        "camera_rotation": {"pitch": 28.16810304671429, "yaw": 153.59577755212467, "roll": -5.616614187670897e-07},
    },
    "jump_land_1cycle": {
        "spawn_location": {"x": 530.0, "y": 185.0, "z": 127.88926724241901},
        "spawn_rotation": {"pitch": 0.0, "yaw": 98.0, "roll": 0.0},
        "camera_location": {"x": 771.7754803852344, "y": 14.999999999999972, "z": 222.5366462703491},
        "camera_rotation": {"pitch": 3.451379281329354, "yaw": 153.54523702932352, "roll": -7.160474254961309e-08},
    },
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE PMX fixed stage editor gate G2.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--equipment-report-path")
    parser.add_argument("--summary-path")
    parser.add_argument("--stage-profile-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    parser.add_argument("--ensure-stage-anchors", action="store_true")
    return parser.parse_args()


def default_output_root(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / f"{GATE_ID}_{run_stamp()}"


def default_latest_report_path(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / f"latest_{GATE_ID}_report.json"


def load_stage_profile(path: str | None) -> dict:
    profile_path = Path(path).expanduser().resolve() if path else STAGE_PROFILE_PATH.resolve()
    if not profile_path.exists():
        raise FileNotFoundError(f"G2 stage profile does not exist: {profile_path}")
    payload = load_json(profile_path)
    payload["_path"] = str(profile_path)
    return payload


def validate_stage_profile(profile: dict) -> list[dict]:
    failed = []
    if str(profile.get("camera_mode") or "anchor_actor") != "anchor_actor":
        failed.append(
            make_failed_requirement(
                "stage_profile_camera_mode",
                "G2 stage profile must lock camera_mode to anchor_actor.",
                profile_path=profile.get("_path"),
                actual_camera_mode=profile.get("camera_mode"),
            )
        )
    if list(profile.get("scenario_order") or []) != SCENARIO_ORDER:
        failed.append(
            make_failed_requirement(
                "stage_profile_scenario_order",
                "G2 stage profile must resolve exactly the fixed four scenarios in order.",
                profile_path=profile.get("_path"),
                expected=list(SCENARIO_ORDER),
                actual=list(profile.get("scenario_order") or []),
            )
        )
    if not profile.get("level_path"):
        failed.append(
            make_failed_requirement(
                "stage_profile_level_path",
                "G2 stage profile must include the fixed level_path.",
                profile_path=profile.get("_path"),
            )
        )
    scenarios = dict(profile.get("scenarios") or {})
    for scenario_name in SCENARIO_ORDER:
        stage_entry = dict(scenarios.get(scenario_name) or {})
        if not stage_entry.get("spawn_anchor_actor_label"):
            failed.append(
                make_failed_requirement(
                    f"stage_profile_spawn_anchor:{scenario_name}",
                    "G2 stage profile is missing a spawn anchor label for a required scenario.",
                    profile_path=profile.get("_path"),
                    scenario=scenario_name,
                )
            )
        if not stage_entry.get("camera_anchor_actor_label"):
            failed.append(
                make_failed_requirement(
                    f"stage_profile_camera_anchor:{scenario_name}",
                    "G2 stage profile is missing a camera anchor label for a required scenario.",
                    profile_path=profile.get("_path"),
                    scenario=scenario_name,
                )
            )
    return failed


def build_scenario_stage_map(profile: dict) -> dict[str, dict]:
    stage_map = {}
    for scenario_name in SCENARIO_ORDER:
        stage_entry = dict((profile.get("scenarios") or {}).get(scenario_name) or {})
        bootstrap_template = BOOTSTRAP_STAGE_TEMPLATE[scenario_name]
        stage_map[scenario_name] = {
            "camera_mode": "anchor_actor",
            "spawn_anchor_actor_label": str(stage_entry.get("spawn_anchor_actor_label") or ""),
            "camera_anchor_actor_label": str(stage_entry.get("camera_anchor_actor_label") or ""),
            "expected_spawn_location": dict(bootstrap_template["spawn_location"]),
            "expected_spawn_rotation": dict(bootstrap_template["spawn_rotation"]),
            "expected_camera_location": dict(bootstrap_template["camera_location"]),
            "expected_camera_rotation": dict(bootstrap_template["camera_rotation"]),
        }
    return stage_map


def bootstrap_anchor_specs(stage_map: dict[str, dict]) -> list[dict]:
    anchors = []
    for scenario_name in SCENARIO_ORDER:
        template = BOOTSTRAP_STAGE_TEMPLATE[scenario_name]
        stage_entry = stage_map[scenario_name]
        anchors.append(
            {
                "label": stage_entry["spawn_anchor_actor_label"],
                "actor_class": "TargetPoint",
                "location": dict(template["spawn_location"]),
                "rotation": dict(template["spawn_rotation"]),
            }
        )
        anchors.append(
            {
                "label": stage_entry["camera_anchor_actor_label"],
                "actor_class": "CineCameraActor",
                "location": dict(template["camera_location"]),
                "rotation": dict(template["camera_rotation"]),
            }
        )
    return anchors


def run_stage_command(workspace: dict, output_root: Path, command: str, params: dict, output_name: str) -> dict:
    output_path = output_root / output_name
    payload = None
    try:
        invocation = run_host_auto_ue_cli(
            workspace_or_config=workspace,
            mode=REQUIRED_MODE,
            command=command,
            params=params,
            output_path=str(output_path),
            post_exit_finalize_wait_seconds=None,
            host_key="kernel",
        )
        payload = invocation.get("payload") or {}
    except Exception as exc:
        invocation = {"payload": None}
        if output_path.exists():
            payload = load_json(output_path)
        else:
            payload = {
                "success": False,
                "warnings": [],
                "errors": [str(exc)],
                "result": {},
            }
    return {
        "payload": payload or {},
        "output_path": str(output_path.resolve()),
    }


def inspect_stage_anchors(workspace: dict, output_root: Path, stage_profile: dict, scenario_stage_map: dict[str, dict]) -> dict:
    params = {
        "stage_id": stage_profile["stage_id"],
        "level_path": stage_profile["level_path"],
        "scenario_order": list(SCENARIO_ORDER),
        "scenario_stage_map": scenario_stage_map,
    }
    return run_stage_command(workspace, output_root, "inspect-stage-anchors", params, "inspect-stage-anchors.json")


def ensure_stage_anchors(workspace: dict, output_root: Path, stage_profile: dict, scenario_stage_map: dict[str, dict]) -> dict:
    params = {
        "stage_id": stage_profile["stage_id"],
        "level_path": stage_profile["level_path"],
        "anchors": bootstrap_anchor_specs(scenario_stage_map),
    }
    return run_stage_command(workspace, output_root, "ensure-stage-anchors", params, "ensure-stage-anchors.json")


def stage_inspection_failures(inspect_payload: dict, scenario_stage_map: dict[str, dict]) -> tuple[dict, list[dict]]:
    result = dict((inspect_payload or {}).get("result") or {})
    resolved_stage_anchors = dict(result.get("resolved_stage_anchors") or {})
    failed = []
    for scenario_name in SCENARIO_ORDER:
        scenario_record = dict(resolved_stage_anchors.get(scenario_name) or {})
        for role, expected_class_name, label_key in (
            ("spawn", "TargetPoint", "spawn_anchor_actor_label"),
            ("camera", "CineCameraActor", "camera_anchor_actor_label"),
        ):
            expected_label = scenario_stage_map[scenario_name][label_key]
            role_record = dict(scenario_record.get(role) or {})
            record_errors = list(role_record.get("errors") or [])
            if role_record.get("status") == "pass" and not record_errors:
                continue
            failed.append(
                make_failed_requirement(
                    f"stage_anchor_resolution:{scenario_name}:{role}:{expected_label}",
                    "A required fixed stage anchor is missing or invalid.",
                    scenario=scenario_name,
                    role=role,
                    expected_class_name=expected_class_name,
                    expected_label=expected_label,
                    resolved_record=role_record,
                    inspect_errors=record_errors,
                )
            )
    if inspect_payload and not inspect_payload.get("success") and not failed:
        failed.append(
            make_failed_requirement(
                "stage_anchor_inspect_command",
                "The stage anchor inspection command did not complete successfully.",
                errors=list((inspect_payload or {}).get("errors") or []),
                warnings=list((inspect_payload or {}).get("warnings") or []),
            )
        )
    return resolved_stage_anchors, failed


def evaluate_g2_scenario_capture(scenario_result: dict | None, scenario_name: str, stage_entry: dict) -> dict:
    evaluated = evaluate_g1_scenario_capture(scenario_result, scenario_name)
    raw = dict(scenario_result or {})
    evaluated["spawn_anchor_actor_label"] = str(raw.get("spawn_anchor_actor_label") or stage_entry.get("spawn_anchor_actor_label") or "")
    evaluated["camera_anchor_actor_label"] = str(raw.get("camera_anchor_actor_label") or stage_entry.get("camera_anchor_actor_label") or "")
    evaluated["camera_source"] = str(raw.get("camera_source") or "")
    evaluated["subject_visible"] = bool(raw.get("subject_visible"))
    evaluated["subject_visibility"] = dict(raw.get("subject_visibility") or {})
    return evaluated


def evaluate_package_result(package: dict, action_payload: dict, package_artifacts: dict, scenario_stage_map: dict[str, dict]) -> tuple[dict, list[dict]]:
    host_record = package["host_record"]
    loadout = package["loadout_record"]
    action_result = dict((action_payload or {}).get("result") or {})
    action_success = bool((action_payload or {}).get("success"))
    package_errors = []
    failed_requirements = []

    raw_package_result = None
    for entry in action_result.get("package_results") or []:
        if entry.get("package_id") == package["package_id"]:
            raw_package_result = entry
            break

    if not action_success:
        package_errors.append("action_result_not_success")
        failed_requirements.append(
            make_failed_requirement(
                f"package_action_success:{package['package_id']}",
                "run-scene-sweep did not complete successfully for the package.",
                package_id=package["package_id"],
                action_result_path=package_artifacts["action_result_path"],
            )
        )

    if not raw_package_result:
        package_errors.append("package_result_missing")
        failed_requirements.append(
            make_failed_requirement(
                f"package_result_presence:{package['package_id']}",
                "Expected package result entry is missing from run-scene-sweep output.",
                package_id=package["package_id"],
                action_result_path=package_artifacts["action_result_path"],
            )
        )
        raw_package_result = {
            "package_id": package["package_id"],
            "status": "fail",
            "warnings": [],
            "errors": ["package_result_missing"],
            "scenario_results": [],
        }

    scenario_index = {
        entry.get("scenario"): entry
        for entry in (raw_package_result.get("scenario_results") or [])
        if entry.get("scenario")
    }
    evaluated_scenarios = [
        evaluate_g2_scenario_capture(scenario_index.get(scenario_name), scenario_name, scenario_stage_map[scenario_name])
        for scenario_name in SCENARIO_ORDER
    ]

    if len(raw_package_result.get("scenario_results") or []) != len(SCENARIO_ORDER):
        package_errors.append("scenario_result_count_mismatch")
        failed_requirements.append(
            make_failed_requirement(
                f"scenario_result_count:{package['package_id']}",
                "Package did not return exactly the required four scenario results.",
                package_id=package["package_id"],
                expected=len(SCENARIO_ORDER),
                actual=len(raw_package_result.get("scenario_results") or []),
            )
        )

    weapon_attachment = {
        "required_socket": REQUIRED_SOCKET,
        "loadout_attach_type": loadout.get("default_attach_type"),
        "loadout_attach_socket": loadout.get("default_attach_name"),
        "host_component_name": host_record.get("default_weapon_component_name"),
        "host_component_attach_socket": host_record.get("default_weapon_component_attach_socket_name"),
        "host_component_attach_ok": bool(host_record.get("default_weapon_component_attach_ok")),
        "has_runtime_weapon_mesh_component": bool(host_record.get("has_runtime_weapon_mesh_component")),
        "status": "pass",
    }
    if not (
        weapon_attachment["loadout_attach_socket"] == REQUIRED_SOCKET
        and weapon_attachment["host_component_attach_socket"] == REQUIRED_SOCKET
        and weapon_attachment["host_component_attach_ok"]
        and weapon_attachment["has_runtime_weapon_mesh_component"]
    ):
        weapon_attachment["status"] = "fail"
        package_errors.append("weapon_socket_attachment_mismatch")
        failed_requirements.append(
            make_failed_requirement(
                f"weapon_socket_attachment:{package['package_id']}",
                "Package did not confirm the default weapon attachment on WeaponSocket.",
                package_id=package["package_id"],
                expected_socket=REQUIRED_SOCKET,
                loadout_attach_socket=weapon_attachment["loadout_attach_socket"],
                host_component_attach_socket=weapon_attachment["host_component_attach_socket"],
            )
        )

    if raw_package_result.get("status") != "pass":
        package_errors.append("package_status_fail")
        failed_requirements.append(
            make_failed_requirement(
                f"package_status:{package['package_id']}",
                "Package-level scene sweep status is not pass.",
                package_id=package["package_id"],
                actual_status=raw_package_result.get("status"),
            )
        )

    for scenario in evaluated_scenarios:
        expected_stage = scenario_stage_map[scenario["scenario"]]
        if not scenario["valid_capture"]:
            package_errors.append(f"invalid_capture:{scenario['scenario']}")
            failed_requirements.append(
                make_failed_requirement(
                    f"scenario_capture_valid:{package['package_id']}:{scenario['scenario']}",
                    "Scenario did not produce a valid capture.",
                    package_id=package["package_id"],
                    scenario=scenario["scenario"],
                    image_path=scenario["image_path"],
                )
            )
        if scenario["late_capture"]:
            package_errors.append(f"late_capture:{scenario['scenario']}")
            failed_requirements.append(
                make_failed_requirement(
                    f"scenario_capture_timing:{package['package_id']}:{scenario['scenario']}",
                    "Scenario capture was not finalized before the report was written.",
                    package_id=package["package_id"],
                    scenario=scenario["scenario"],
                    capture_status=scenario["capture_status"],
                )
            )
        if scenario.get("camera_source") != "anchor_actor":
            package_errors.append(f"camera_source_mismatch:{scenario['scenario']}")
            failed_requirements.append(
                make_failed_requirement(
                    f"scenario_camera_source:{package['package_id']}:{scenario['scenario']}",
                    "Scenario did not use the fixed anchor_actor camera source.",
                    package_id=package["package_id"],
                    scenario=scenario["scenario"],
                    actual_camera_source=scenario.get("camera_source"),
                )
            )
        if scenario.get("spawn_anchor_actor_label") != expected_stage["spawn_anchor_actor_label"]:
            package_errors.append(f"spawn_anchor_label_mismatch:{scenario['scenario']}")
            failed_requirements.append(
                make_failed_requirement(
                    f"scenario_spawn_anchor:{package['package_id']}:{scenario['scenario']}",
                    "Scenario did not resolve the expected spawn anchor label.",
                    package_id=package["package_id"],
                    scenario=scenario["scenario"],
                    expected_label=expected_stage["spawn_anchor_actor_label"],
                    actual_label=scenario.get("spawn_anchor_actor_label"),
                )
            )
        if scenario.get("camera_anchor_actor_label") != expected_stage["camera_anchor_actor_label"]:
            package_errors.append(f"camera_anchor_label_mismatch:{scenario['scenario']}")
            failed_requirements.append(
                make_failed_requirement(
                    f"scenario_camera_anchor:{package['package_id']}:{scenario['scenario']}",
                    "Scenario did not resolve the expected camera anchor label.",
                    package_id=package["package_id"],
                    scenario=scenario["scenario"],
                    expected_label=expected_stage["camera_anchor_actor_label"],
                    actual_label=scenario.get("camera_anchor_actor_label"),
                )
            )
        if not scenario.get("subject_visible"):
            package_errors.append(f"subject_not_visible:{scenario['scenario']}")
            failed_requirements.append(
                make_failed_requirement(
                    f"scenario_subject_visible:{package['package_id']}:{scenario['scenario']}",
                    "Scenario did not place the target actor inside the camera view.",
                    package_id=package["package_id"],
                    scenario=scenario["scenario"],
                    subject_visibility=scenario.get("subject_visibility"),
                    image_path=scenario["image_path"],
                )
            )

    return (
        {
            "package_id": package["package_id"],
            "host_blueprint_asset": package["host_blueprint_asset"],
            "default_weapon_package_id": package["default_weapon_package_id"],
            "status": "pass" if not package_errors else "fail",
            "weapon_attachment": weapon_attachment,
            "scenario_results": evaluated_scenarios,
            "warnings": sorted(
                {
                    *list(raw_package_result.get("warnings") or []),
                    *list((action_payload or {}).get("warnings") or []),
                }
            ),
            "errors": sorted(
                {
                    *package_errors,
                    *list(raw_package_result.get("errors") or []),
                    *list((action_payload or {}).get("errors") or []),
                }
            ),
            "artifacts": package_artifacts,
        },
        failed_requirements,
    )


def build_discussion_signal(status: str, failed_requirements: list[dict], previous_report: dict | None, previous_report_path: Path | None) -> dict:
    current_failed_ids = normalize_failed_requirement_ids({"failed_requirements": failed_requirements})
    previous_status = (previous_report or {}).get("status")
    previous_failed_ids = normalize_failed_requirement_ids(previous_report)
    signal = {
        "should_discuss": False,
        "reason": None,
        "previous_report_path": str(previous_report_path) if previous_report_path else None,
        "repeated_failed_requirement_ids": [],
    }
    if status == "pass" and previous_status != "pass":
        signal["should_discuss"] = True
        signal["reason"] = "g2_first_complete_pass"
        return signal
    if status != "pass" and current_failed_ids and previous_status != "pass" and current_failed_ids == previous_failed_ids:
        signal["should_discuss"] = True
        signal["reason"] = "same_failed_requirement_two_rounds"
        signal["repeated_failed_requirement_ids"] = current_failed_ids
    return signal


def run_package_scene_sweep(
    workspace: dict,
    summary_path: Path,
    package: dict,
    package_root: Path,
    stage_profile: dict,
    scenario_stage_map: dict[str, dict],
) -> tuple[dict, dict]:
    capture_root = package_root / "captures"
    suite_output = package_root / "ue_animation_suite_summary.json"
    capture_manifest_output = package_root / "ue_capture_manifest.json"
    action_result_path = package_root / "run-scene-sweep.json"
    params = {
        "summary": str(summary_path),
        "package_id": package["package_id"],
        "validation_mode": "editor_world_fixed_stage_scene_sweep",
        "enable_capture": True,
        "capture_root": str(capture_root),
        "suite_output": str(suite_output),
        "capture_manifest_output": str(capture_manifest_output),
        "preferred_capture_mode": REQUIRED_MODE,
        "camera_mode": "anchor_actor",
        "level_path": stage_profile["level_path"],
        "scenario_stage_map": scenario_stage_map,
        "capture_delay_seconds": FIXED_EXECUTION_PROFILE["capture_delay_seconds"],
        "camera_lifecycle": FIXED_EXECUTION_PROFILE["camera_lifecycle"],
        "level_lifecycle": FIXED_EXECUTION_PROFILE["level_lifecycle"],
        "scenario_names": list(SCENARIO_ORDER),
        "scenario_scheduling": FIXED_EXECUTION_PROFILE["scenario_scheduling"],
        "completion_strategy": FIXED_EXECUTION_PROFILE["completion_strategy"],
        "settle_timeout_seconds": FIXED_EXECUTION_PROFILE["settle_timeout_seconds"],
        "file_stability_window_seconds": FIXED_EXECUTION_PROFILE["file_stability_window_seconds"],
        "viewport_pump_interval_seconds": FIXED_EXECUTION_PROFILE["viewport_pump_interval_seconds"],
        "quit_barrier_seconds": FIXED_EXECUTION_PROFILE["quit_barrier_seconds"],
    }
    invocation = run_host_auto_ue_cli(
        workspace_or_config=workspace,
        mode=REQUIRED_MODE,
        command="run-scene-sweep",
        params=params,
        output_path=str(action_result_path),
        post_exit_finalize_wait_seconds=FIXED_EXECUTION_PROFILE["finalize_wait_seconds"],
        host_key="kernel",
    )
    return (
        invocation.get("payload") or {},
        {
            "action_result_path": str(action_result_path.resolve()),
            "capture_manifest_output": str(capture_manifest_output.resolve()),
            "suite_output": str(suite_output.resolve()),
            "capture_root": str(capture_root.resolve()),
        },
    )


def build_report(
    workspace: dict,
    output_root: Path,
    latest_report_path: Path,
    summary_path: Path,
    equipment_report_path: Path,
    suite_name: str,
    stage_profile: dict,
    scenario_stage_map: dict[str, dict],
    resolved_stage_anchors: dict,
    selected_packages: list[dict],
    per_package_results: list[dict],
    failed_requirements: list[dict],
    previous_report: dict | None,
    previous_report_path: Path | None,
    stage_ensure_artifact: dict | None,
    stage_inspect_artifact: dict | None,
) -> dict:
    counts = aggregate_counts(per_package_results)
    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(status, failed_requirements, previous_report, previous_report_path)
    fixed_stage_applied = (
        status == "pass"
        and all(
            scenario.get("camera_source") == "anchor_actor" and scenario.get("subject_visible")
            for package_result in per_package_results
            for scenario in (package_result.get("scenario_results") or [])
            if scenario.get("status") != "not_run"
        )
    )
    package_run_roots = []
    for entry in per_package_results:
        capture_root = (entry.get("artifacts") or {}).get("capture_root")
        if capture_root:
            package_run_roots.append(capture_root)
    return with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "stage_id": stage_profile["stage_id"],
            "status": status,
            "success": status == "pass",
            "workspace_config": workspace["config_path"],
            "suite_name": suite_name,
            "required_package_count": REQUIRED_PACKAGE_COUNT,
            "resolved_package_ids": [entry["package_id"] for entry in selected_packages],
            "stage_level_path": stage_profile["level_path"],
            "scenario_stage_map": scenario_stage_map,
            "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
            "fixed_stage_applied": fixed_stage_applied,
            "resolved_stage_anchors": resolved_stage_anchors,
            "counts": counts,
            "failed_requirements": failed_requirements,
            "per_package_results": per_package_results,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "summary_path": str(summary_path.resolve()),
                "equipment_report_path": str(equipment_report_path.resolve()),
                "stage_profile_path": stage_profile["_path"],
                "stage_ensure_path": (stage_ensure_artifact or {}).get("output_path"),
                "stage_inspect_path": (stage_inspect_artifact or {}).get("output_path"),
                "latest_report_path": str(latest_report_path.resolve()),
                "package_run_roots": package_run_roots,
            },
        },
        "aiue_editor_gate_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_editor_gate_report",
            notes=["internal_gate_runner", "not_part_of_stable_alpha_surface", "fixed_stage_gate"],
        ),
    )


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    equipment_report_path = resolve_equipment_report_path(workspace, args.equipment_report_path)
    equipment_report = load_json(equipment_report_path)
    summary_path = resolve_summary_path(workspace, equipment_report_path, equipment_report, args.summary_path)
    suite_name = equipment_report.get("suite_name") or equipment_report.get("suite_slug") or "conversion_success"

    stage_profile = load_stage_profile(args.stage_profile_path)
    scenario_stage_map = build_scenario_stage_map(stage_profile)
    failed_requirements = verify_editor_capture_capability(workspace)
    failed_requirements.extend(validate_stage_profile(stage_profile))

    stage_ensure_artifact = None
    if args.ensure_stage_anchors and not failed_requirements:
        stage_ensure_artifact = ensure_stage_anchors(workspace, output_root, stage_profile, scenario_stage_map)
        if not (stage_ensure_artifact.get("payload") or {}).get("success"):
            failed_requirements.append(
                make_failed_requirement(
                    "stage_anchor_ensure_command",
                    "The stage anchor ensure command did not complete successfully.",
                    output_path=stage_ensure_artifact.get("output_path"),
                    errors=list(((stage_ensure_artifact.get("payload") or {}).get("errors") or [])),
                )
            )

    stage_inspect_artifact = inspect_stage_anchors(workspace, output_root, stage_profile, scenario_stage_map) if not failed_requirements else None
    resolved_stage_anchors = {}
    if stage_inspect_artifact:
        resolved_stage_anchors, stage_failures = stage_inspection_failures(stage_inspect_artifact.get("payload") or {}, scenario_stage_map)
        failed_requirements.extend(stage_failures)

    selected_packages = select_target_packages(equipment_report)
    if len(selected_packages) != REQUIRED_PACKAGE_COUNT:
        failed_requirements.append(
            make_failed_requirement(
                "required_package_count",
                "G2 requires exactly two runtime-ready host packages with ready weapon pairs.",
                expected=REQUIRED_PACKAGE_COUNT,
                actual=len(selected_packages),
                resolved_package_ids=[entry["package_id"] for entry in selected_packages],
            )
        )

    per_package_results = []
    if not failed_requirements:
        for index, package in enumerate(selected_packages, start=1):
            package_root = output_root / f"{index:03d}_{package['package_id']}"
            action_payload, package_artifacts = run_package_scene_sweep(
                workspace,
                summary_path,
                package,
                package_root,
                stage_profile,
                scenario_stage_map,
            )
            package_result, package_failures = evaluate_package_result(package, action_payload, package_artifacts, scenario_stage_map)
            per_package_results.append(package_result)
            failed_requirements.extend(package_failures)

    if failed_requirements and not per_package_results:
        for package in selected_packages:
            per_package_results.append(
                {
                    "package_id": package["package_id"],
                    "host_blueprint_asset": package["host_blueprint_asset"],
                    "default_weapon_package_id": package["default_weapon_package_id"],
                    "status": "not_run",
                    "weapon_attachment": {
                        "required_socket": REQUIRED_SOCKET,
                        "loadout_attach_type": package["loadout_record"].get("default_attach_type"),
                        "loadout_attach_socket": package["loadout_record"].get("default_attach_name"),
                        "host_component_name": package["host_record"].get("default_weapon_component_name"),
                        "host_component_attach_socket": package["host_record"].get("default_weapon_component_attach_socket_name"),
                        "host_component_attach_ok": bool(package["host_record"].get("default_weapon_component_attach_ok")),
                        "has_runtime_weapon_mesh_component": bool(package["host_record"].get("has_runtime_weapon_mesh_component")),
                        "status": "pass",
                    },
                    "scenario_results": [
                        {
                            "scenario": scenario_name,
                            "status": "not_run",
                            "capture_status": "not_run",
                            "image_path": "",
                            "valid_capture": False,
                            "captured_before_report": False,
                            "captured_after_exit": False,
                            "late_capture": False,
                            "captured_after_report_before_exit": False,
                            "exists": False,
                            "size_bytes": 0,
                            "sha256": None,
                            "warnings": [],
                            "errors": ["not_run_due_to_prerequisite_failure"],
                            "spawn_anchor_actor_label": scenario_stage_map[scenario_name]["spawn_anchor_actor_label"],
                            "camera_anchor_actor_label": scenario_stage_map[scenario_name]["camera_anchor_actor_label"],
                            "camera_source": "anchor_actor",
                            "subject_visible": False,
                            "subject_visibility": {},
                        }
                        for scenario_name in SCENARIO_ORDER
                    ],
                    "warnings": [],
                    "errors": ["gate_not_executed_due_to_prerequisite_failure"],
                    "artifacts": {},
                }
            )

    report_payload = build_report(
        workspace=workspace,
        output_root=output_root,
        latest_report_path=latest_report_path,
        summary_path=summary_path,
        equipment_report_path=equipment_report_path,
        suite_name=suite_name,
        stage_profile=stage_profile,
        scenario_stage_map=scenario_stage_map,
        resolved_stage_anchors=resolved_stage_anchors,
        selected_packages=selected_packages,
        per_package_results=per_package_results,
        failed_requirements=failed_requirements,
        previous_report=previous_report,
        previous_report_path=previous_report_path,
        stage_ensure_artifact=stage_ensure_artifact,
        stage_inspect_artifact=stage_inspect_artifact,
    )
    report_path = output_root / "g2_editor_gate_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)

    print(str(report_path))
    return 0 if report_payload.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
