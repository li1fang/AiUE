from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import (
    build_discussion_signal,
    default_latest_report_path,
    default_output_root,
    make_failed_requirement,
    now_utc,
)
from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json
from aiue_unreal.host_bridge import run_host_auto_ue_cli
from toy_yard_view import (
    resolve_toy_yard_equipment_report_path,
    resolve_toy_yard_summary_path,
)

GATE_ID = "editor_core_closure_g1"
REQUIRED_PACKAGE_COUNT = 2
REQUIRED_MODE = "editor_rendered"
REQUIRED_SOCKET = "WeaponSocket"
SCENARIO_ORDER = ["idle_2s", "walk_forward_2s", "run_forward_2s", "jump_land_1cycle"]
CAPTURE_TIMING_BUCKETS = {
    "captured_before_report",
    "captured_after_report_before_exit",
    "captured_after_exit",
}
FIXED_EXECUTION_PROFILE = {
    "mode": REQUIRED_MODE,
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

def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE PMX editor core closure gate G1.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--equipment-report-path")
    parser.add_argument("--summary-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def latest_matching_file(root: Path, pattern: str) -> Path | None:
    if not root.exists():
        return None
    candidates = sorted(root.rglob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None

def resolve_equipment_report_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Equipment report path does not exist: {candidate}")

    toy_yard_report = resolve_toy_yard_equipment_report_path(workspace)
    if toy_yard_report:
        return toy_yard_report

    local_auto_report = Path(workspace["paths"].get("auto_ue_cli_output_root") or "") / "ue_equipment_assets_report.local.json"
    if local_auto_report.exists():
        return local_auto_report.resolve()

    conversion_root = Path(workspace["paths"]["conversion_root"]).expanduser().resolve()
    fallback = latest_matching_file(conversion_root / "_e2e_runs", "ue_equipment_assets_report.json")
    if fallback:
        return fallback.resolve()
    raise FileNotFoundError("No ue_equipment_assets_report.json could be resolved for G1 gate.")


def resolve_summary_path(workspace: dict, equipment_report_path: Path, equipment_report: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Suite summary path does not exist: {candidate}")

    toy_yard_summary = resolve_toy_yard_summary_path(workspace)
    if toy_yard_summary:
        return toy_yard_summary

    registry_json_path = equipment_report.get("registry_json_path")
    if registry_json_path:
        registry_path = Path(registry_json_path).expanduser()
        if registry_path.exists():
            candidate = registry_path.parent / "ue_suite_summary.json"
            if candidate.exists():
                return candidate.resolve()

    if equipment_report_path.name == "ue_equipment_assets_report.json":
        candidate = equipment_report_path.with_name("ue_suite_summary.json")
        if candidate.exists():
            return candidate.resolve()

    conversion_root = Path(workspace["paths"]["conversion_root"]).expanduser().resolve()
    fallback = latest_matching_file(conversion_root / "_e2e_runs", "ue_suite_summary.json")
    if fallback:
        return fallback.resolve()
    raise FileNotFoundError("No ue_suite_summary.json could be resolved for G1 gate.")


def build_loadout_index(equipment_report: dict) -> dict[str, dict]:
    return {
        entry.get("character_package_id"): entry
        for entry in (equipment_report.get("loadout_assets") or [])
        if entry.get("character_package_id")
    }


def is_runtime_ready_host_record(record: dict, loadout: dict) -> bool:
    return (
        bool(record.get("consumer_ready"))
        and bool(record.get("has_ready_weapon_pairs"))
        and bool(record.get("native_runtime_available"))
        and bool(record.get("has_runtime_weapon_mesh_component"))
        and bool(record.get("default_weapon_component_attach_ok"))
        and record.get("default_weapon_component_attach_socket_name") == REQUIRED_SOCKET
        and bool(record.get("default_weapon_package_id"))
        and bool(record.get("asset_path"))
        and bool(loadout.get("has_ready_weapon_pairs"))
        and loadout.get("default_attach_name") == REQUIRED_SOCKET
        and loadout.get("default_weapon_package_id") == record.get("default_weapon_package_id")
    )


def select_target_packages(equipment_report: dict) -> list[dict]:
    loadout_index = build_loadout_index(equipment_report)
    selected = []
    for host_record in equipment_report.get("host_blueprints") or []:
        package_id = host_record.get("character_package_id")
        loadout = loadout_index.get(package_id, {})
        if not is_runtime_ready_host_record(host_record, loadout):
            continue
        selected.append(
            {
                "package_id": package_id,
                "sample_id": host_record.get("sample_id"),
                "host_blueprint_asset": host_record.get("asset_path"),
                "default_weapon_package_id": host_record.get("default_weapon_package_id"),
                "host_record": host_record,
                "loadout_record": loadout,
            }
        )
    return sorted(selected, key=lambda item: item["package_id"])


def sha256_file(path: Path | None) -> str | None:
    if not path or not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluate_scenario_capture(scenario_result: dict | None, scenario_name: str) -> dict:
    scenario_result = dict(scenario_result or {})
    image_path = scenario_result.get("image_path")
    resolved_path = Path(image_path) if image_path else None
    exists = bool(resolved_path and resolved_path.exists())
    size_bytes = resolved_path.stat().st_size if exists else 0
    capture_status = scenario_result.get("capture_status")
    valid_capture = (
        scenario_result.get("status") == "pass"
        and exists
        and size_bytes > 0
        and str(capture_status).startswith("captured")
    )
    timing_bucket = capture_status if capture_status in CAPTURE_TIMING_BUCKETS else None
    errors = list(scenario_result.get("errors") or [])
    if not valid_capture:
        errors.append("invalid_capture")
    if timing_bucket == "captured_after_report_before_exit":
        errors.append("capture_not_finalized_before_report")
    if timing_bucket == "captured_after_exit":
        errors.append("capture_not_finalized_before_exit")
    if timing_bucket is None:
        errors.append("capture_status_missing_or_unrecognized")
    return {
        "scenario": scenario_name,
        "status": scenario_result.get("status") or ("pass" if valid_capture else "fail"),
        "capture_status": capture_status or "missing",
        "image_path": str(resolved_path.resolve()) if exists and resolved_path else (str(resolved_path) if resolved_path else ""),
        "valid_capture": valid_capture,
        "captured_before_report": timing_bucket == "captured_before_report",
        "captured_after_exit": timing_bucket == "captured_after_exit",
        "late_capture": timing_bucket in {"captured_after_report_before_exit", "captured_after_exit"},
        "captured_after_report_before_exit": timing_bucket == "captured_after_report_before_exit",
        "exists": exists,
        "size_bytes": size_bytes,
        "sha256": sha256_file(resolved_path) if valid_capture else None,
        "warnings": list(scenario_result.get("warnings") or []),
        "errors": sorted(set(errors)),
    }

def evaluate_package_result(package: dict, action_payload: dict, package_artifacts: dict) -> tuple[dict, list[dict]]:
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
                "package_action_success",
                "run-scene-sweep did not complete successfully for the package.",
                package_id=package["package_id"],
                action_result_path=package_artifacts["action_result_path"],
            )
        )

    if not raw_package_result:
        package_errors.append("package_result_missing")
        failed_requirements.append(
            make_failed_requirement(
                "package_result_presence",
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
    evaluated_scenarios = [evaluate_scenario_capture(scenario_index.get(name), name) for name in SCENARIO_ORDER]

    missing_or_extra = len(raw_package_result.get("scenario_results") or []) != len(SCENARIO_ORDER)
    if missing_or_extra:
        package_errors.append("scenario_result_count_mismatch")
        failed_requirements.append(
            make_failed_requirement(
                "scenario_result_count",
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
                "weapon_socket_attachment",
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
                "package_status",
                "Package-level scene sweep status is not pass.",
                package_id=package["package_id"],
                actual_status=raw_package_result.get("status"),
            )
        )

    for scenario in evaluated_scenarios:
        if not scenario["valid_capture"]:
            package_errors.append(f"invalid_capture:{scenario['scenario']}")
            failed_requirements.append(
                make_failed_requirement(
                    "scenario_capture_valid",
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
                    "scenario_capture_timing",
                    "Scenario capture was not finalized before the report was written.",
                    package_id=package["package_id"],
                    scenario=scenario["scenario"],
                    capture_status=scenario["capture_status"],
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


def aggregate_counts(per_package_results: list[dict]) -> dict:
    counts = {
        "required_packages": REQUIRED_PACKAGE_COUNT,
        "resolved_packages": len(per_package_results),
        "requested_packages": len(per_package_results),
        "completed_packages": sum(1 for entry in per_package_results if entry.get("status") == "pass"),
        "failed_packages": sum(1 for entry in per_package_results if entry.get("status") != "pass"),
        "expected_images": REQUIRED_PACKAGE_COUNT * len(SCENARIO_ORDER),
        "attempted_images": 0,
        "capture_entries": 0,
        "valid_images": 0,
        "captured_before_report": 0,
        "captured_after_report_before_exit": 0,
        "captured_after_exit": 0,
        "late_captures": 0,
    }
    for package_result in per_package_results:
        for scenario in package_result.get("scenario_results") or []:
            if scenario.get("status") == "not_run":
                continue
            counts["attempted_images"] += 1
            counts["capture_entries"] += 1
            counts["valid_images"] += int(bool(scenario.get("valid_capture")))
            counts["captured_before_report"] += int(bool(scenario.get("captured_before_report")))
            counts["captured_after_report_before_exit"] += int(bool(scenario.get("captured_after_report_before_exit")))
            counts["captured_after_exit"] += int(bool(scenario.get("captured_after_exit")))
            counts["late_captures"] += int(bool(scenario.get("late_capture")))
    return counts

def verify_editor_capture_capability(workspace: dict) -> list[dict]:
    capability_path = Path(workspace["paths"]["capability_probe_root"]).expanduser().resolve() / "latest_capabilities.json"
    if not capability_path.exists():
        return [
            make_failed_requirement(
                "editor_capture_capability",
                "latest_capabilities.json is missing, so the fixed G1 editor mode cannot be verified.",
                capability_path=str(capability_path),
            )
        ]
    capabilities_payload = load_json(capability_path)
    for entry in capabilities_payload.get("capabilities") or []:
        if entry.get("capability_id") != "capture_frame":
            continue
        if entry.get("mode") != REQUIRED_MODE:
            continue
        if entry.get("callable") and entry.get("reliable"):
            return []
        return [
            make_failed_requirement(
                "editor_capture_capability",
                "editor_rendered capture_frame is not callable and reliable on this machine.",
                capability_path=str(capability_path),
                callable=entry.get("callable"),
                reliable=entry.get("reliable"),
            )
        ]
    return [
        make_failed_requirement(
            "editor_capture_capability",
            "editor_rendered capture_frame capability entry is missing.",
            capability_path=str(capability_path),
        )
    ]


def run_package_scene_sweep(workspace: dict, summary_path: Path, package: dict, package_root: Path) -> tuple[dict, dict]:
    capture_root = package_root / "captures"
    suite_output = package_root / "ue_animation_suite_summary.json"
    capture_manifest_output = package_root / "ue_capture_manifest.json"
    action_result_path = package_root / "run-scene-sweep.json"
    params = {
        "summary": str(summary_path),
        "package_id": package["package_id"],
        "validation_mode": "editor_world_scene_sweep",
        "enable_capture": True,
        "capture_root": str(capture_root),
        "suite_output": str(suite_output),
        "capture_manifest_output": str(capture_manifest_output),
        "preferred_capture_mode": REQUIRED_MODE,
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
    selected_packages: list[dict],
    per_package_results: list[dict],
    failed_requirements: list[dict],
    previous_report: dict | None,
    previous_report_path: Path | None,
) -> dict:
    counts = aggregate_counts(per_package_results)
    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        first_pass_reason="g1_first_complete_pass",
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
            "status": status,
            "success": status == "pass",
            "workspace_config": workspace["config_path"],
            "suite_name": suite_name,
            "required_package_count": REQUIRED_PACKAGE_COUNT,
            "resolved_package_ids": [entry["package_id"] for entry in selected_packages],
            "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
            "counts": counts,
            "failed_requirements": failed_requirements,
            "per_package_results": per_package_results,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "summary_path": str(summary_path.resolve()),
                "equipment_report_path": str(equipment_report_path.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
                "package_run_roots": package_run_roots,
            },
        },
        "aiue_editor_gate_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_editor_gate_report",
            notes=["internal_gate_runner", "not_part_of_stable_alpha_surface"],
        ),
    )


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = (
        Path(args.latest_report_path).expanduser().resolve()
        if args.latest_report_path
        else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    )
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    equipment_report_path = resolve_equipment_report_path(workspace, args.equipment_report_path)
    equipment_report = load_json(equipment_report_path)
    summary_path = resolve_summary_path(workspace, equipment_report_path, equipment_report, args.summary_path)
    suite_name = equipment_report.get("suite_name") or equipment_report.get("suite_slug") or "conversion_success"

    failed_requirements = verify_editor_capture_capability(workspace)
    selected_packages = select_target_packages(equipment_report)
    if len(selected_packages) != REQUIRED_PACKAGE_COUNT:
        failed_requirements.append(
            make_failed_requirement(
                "required_package_count",
                "G1 requires exactly two runtime-ready host packages with ready weapon pairs.",
                expected=REQUIRED_PACKAGE_COUNT,
                actual=len(selected_packages),
                resolved_package_ids=[entry["package_id"] for entry in selected_packages],
            )
        )

    per_package_results = []
    if not failed_requirements:
        for index, package in enumerate(selected_packages, start=1):
            package_root = output_root / f"{index:03d}_{package['package_id']}"
            action_payload, package_artifacts = run_package_scene_sweep(workspace, summary_path, package, package_root)
            package_result, package_failures = evaluate_package_result(package, action_payload, package_artifacts)
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
        selected_packages=selected_packages,
        per_package_results=per_package_results,
        failed_requirements=failed_requirements,
        previous_report=previous_report,
        previous_report_path=previous_report_path,
    )
    report_path = output_root / "g1_editor_gate_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    print(f"G1 editor gate report written to: {report_path}")
    raise SystemExit(0 if report_payload.get("status") == "pass" else 1)


if __name__ == "__main__":
    main()
