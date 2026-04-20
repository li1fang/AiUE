from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, make_failed_requirement, now_utc, repo_root_from_workspace, run_stamp

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json
from aiue_unreal.host_bridge import run_host_auto_ue_cli
from run_editor_gate_g1 import (
    resolve_equipment_report_path,
    resolve_summary_path,
    select_target_packages,
)
from toy_yard_view import (
    build_toy_yard_manifest_index,
    resolve_toy_yard_registry_path,
    resolve_toy_yard_view_root,
)

GATE_ID = "demo_stage_d1_onboarding"
REQUIRED_MODE = "editor_rendered"
REQUIRED_PACKAGE_COUNT = 2
DEMO_HOST_KEY = "demo"
DEMO_LEVEL_PATH = "/Game/Levels/DefaultLevel"
SCENARIO_NAMES = ["idle_2s", "run_forward_2s"]
FIXED_EXECUTION_PROFILE = {
    "host_key": DEMO_HOST_KEY,
    "mode": REQUIRED_MODE,
    "level_path": DEMO_LEVEL_PATH,
    "scenario_names": list(SCENARIO_NAMES),
    "level_lifecycle": "reuse_level",
    "camera_lifecycle": "reuse_camera",
    "scenario_scheduling": "single_scenario",
    "completion_strategy": "native_helper_wait",
    "camera_mode": "auto_framing",
    "capture_width": 1280,
    "capture_height": 720,
    "capture_delay_seconds": 0.2,
    "settle_timeout_seconds": 6.0,
    "file_stability_window_seconds": 0.75,
    "viewport_pump_interval_seconds": 0.05,
    "quit_barrier_seconds": 2.0,
}

def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE demo host onboarding gate D1.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--equipment-report-path")
    parser.add_argument("--summary-path")
    parser.add_argument("--registry-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()

def resolve_registry_path(equipment_report: dict, summary_path: Path, explicit_path: str | None, workspace: dict | None = None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Registry path does not exist: {candidate}")
    if workspace is not None:
        toy_yard_registry = resolve_toy_yard_registry_path(workspace)
        toy_yard_root = resolve_toy_yard_view_root(workspace)
        summary_is_from_toy_yard = False
        if toy_yard_root:
            try:
                summary_path.resolve().relative_to(toy_yard_root.resolve())
                summary_is_from_toy_yard = True
            except ValueError:
                summary_is_from_toy_yard = False
        if toy_yard_registry and summary_is_from_toy_yard:
            return toy_yard_registry
    registry_json_path = equipment_report.get("registry_json_path")
    if registry_json_path:
        candidate = Path(registry_json_path).expanduser()
        if candidate.exists():
            return candidate.resolve()
    candidate = summary_path.with_name("ue_equipment_registry.json")
    if candidate.exists():
        return candidate.resolve()
    raise FileNotFoundError("No ue_equipment_registry.json could be resolved for D1.")

def build_local_manifest_index(summary_path: Path) -> tuple[Path, dict[str, Path]]:
    return build_toy_yard_manifest_index(summary_path)

def filter_summary_payload(summary_payload: dict, selected_package_ids: set[str], manifest_index: dict[str, Path]) -> dict:
    successes = []
    for entry in (summary_payload.get("successes") or []):
        package_id = str(entry.get("package_id") or "")
        if package_id not in selected_package_ids:
            continue
        rewritten = dict(entry)
        manifest_path = manifest_index.get(package_id)
        if manifest_path:
            rewritten["manifest_path"] = str(manifest_path)
            rewritten["manifest_path_local"] = str(manifest_path)
        successes.append(rewritten)

    content_bucket_counts = Counter(entry.get("content_bucket") or "unknown" for entry in successes)
    package_role_counts = Counter(entry.get("package_role") or "unknown" for entry in successes)
    contract_type_counts = Counter(entry.get("contract_type") or "unknown" for entry in successes)
    consumer_ready_counts = Counter("ready" if entry.get("consumer_ready") else "not_ready" for entry in successes)
    counts = {
        "requested_items": len(successes),
        "completed_items": len(successes),
        "successful_items": len(successes),
        "failed_items": 0,
    }
    filtered = dict(summary_payload)
    filtered["generated_at_utc"] = now_utc()
    filtered["successes"] = successes
    filtered["failures"] = []
    filtered["counts"] = counts
    filtered["content_bucket_counts"] = dict(content_bucket_counts)
    filtered["package_role_counts"] = dict(package_role_counts)
    filtered["contract_type_counts"] = dict(contract_type_counts)
    filtered["consumer_ready_counts"] = dict(consumer_ready_counts)
    filtered["selected_package_ids"] = sorted(selected_package_ids)
    return filtered

def filter_registry_payload(registry_payload: dict, selected_character_ids: set[str], selected_weapon_ids: set[str]) -> dict:
    selected_package_ids = selected_character_ids | selected_weapon_ids
    characters = [
        entry
        for entry in (registry_payload.get("characters") or [])
        if str(entry.get("package_id") or "") in selected_character_ids
    ]
    weapons = [
        entry
        for entry in (registry_payload.get("weapons") or [])
        if str(entry.get("package_id") or "") in selected_weapon_ids
    ]
    ready_pairs = [
        entry
        for entry in (registry_payload.get("ready_pairs") or [])
        if str(entry.get("character_package_id") or "") in selected_character_ids
        and str(entry.get("weapon_package_id") or "") in selected_weapon_ids
    ]
    selected_sample_ids = {str(entry.get("sample_id") or "") for entry in characters + weapons if entry.get("sample_id")}
    bundles = [
        entry
        for entry in (registry_payload.get("bundles") or [])
        if str(entry.get("sample_id") or "") in selected_sample_ids
    ]
    package_index = {
        package_id: entry
        for package_id, entry in (registry_payload.get("package_index") or {}).items()
        if package_id in selected_package_ids
    }
    filtered = dict(registry_payload)
    filtered["generated_at_utc"] = now_utc()
    filtered["characters"] = characters
    filtered["weapons"] = weapons
    filtered["ready_pairs"] = ready_pairs
    filtered["bundles"] = bundles
    filtered["package_index"] = package_index
    filtered["counts"] = {
        "packages": len(selected_package_ids),
        "characters": len(characters),
        "weapons": len(weapons),
        "ready_characters": sum(1 for entry in characters if entry.get("consumer_ready")),
        "ready_weapons": sum(1 for entry in weapons if entry.get("consumer_ready")),
        "ready_pairs": len(ready_pairs),
        "equippable_bundles": sum(1 for entry in bundles if entry.get("equippable")),
    }
    filtered["selected_package_ids"] = sorted(selected_package_ids)
    return filtered

def run_host_command(
    workspace: dict,
    command: str,
    params: dict,
    output_path: Path,
    host_key: str = DEMO_HOST_KEY,
) -> dict:
    invocation = run_host_auto_ue_cli(
        workspace_or_config=workspace,
        mode=REQUIRED_MODE,
        command=command,
        params=params,
        output_path=str(output_path.resolve()),
        host_key=host_key,
    )
    return dict(invocation.get("payload") or {})

def evaluate_imports(import_results: list[dict], selected_package_ids: set[str]) -> tuple[list[dict], list[dict]]:
    failed_requirements: list[dict] = []
    import_records = []
    successful_package_ids = set()
    for item in import_results:
        payload = item["payload"]
        result = dict(payload.get("result") or {})
        imported_assets = dict(result.get("imported_assets") or {})
        package_id = str(result.get("package_id") or result.get("consumer_package_id") or item["package_id"])
        result_status = str(result.get("status") or result.get("validation_status") or ("fail" if result.get("errors") else "pass"))
        success = bool(payload.get("success")) and result_status == "pass"
        if success:
            successful_package_ids.add(package_id)
        import_records.append(
            {
                "package_id": package_id,
                "manifest_path": item["manifest_path"],
                "output_path": item["output_path"],
                "status": "pass" if success else "fail",
                "skeletal_mesh": imported_assets.get("skeletal_mesh"),
                "skeleton": imported_assets.get("skeleton"),
                "physics_asset": imported_assets.get("physics_asset"),
                "warnings": list(payload.get("warnings") or []) + list(result.get("warnings") or []),
                "errors": list(payload.get("errors") or []) + list(result.get("errors") or []),
            }
        )
    if successful_package_ids != selected_package_ids:
        failed_requirements.append(
            make_failed_requirement(
                "demo_imports_incomplete",
                "Demo host did not successfully import every selected manifest.",
                expected=sorted(selected_package_ids),
                actual=sorted(successful_package_ids),
            )
        )
    return import_records, failed_requirements

def evaluate_scene_sweeps(scene_runs: list[dict], expected_packages: set[str], expected_images: int) -> tuple[dict, list[dict]]:
    failed_requirements: list[dict] = []
    aggregated_package_results = []
    aggregated_warnings = []
    aggregated_errors = []
    completed_package_ids = set()
    valid_images = 0
    captured_before_report = 0
    failed_packages = 0
    requested_packages = 0
    suite_outputs = []
    capture_manifest_outputs = []
    capture_roots = []
    for scene_run in scene_runs:
        payload = dict(scene_run.get("payload") or {})
        result = dict(payload.get("result") or {})
        counts = dict(result.get("counts") or {})
        package_results = list(result.get("package_results") or [])
        requested_packages += int(counts.get("requested_packages") or 0)
        valid_images += int(counts.get("valid_images") or 0)
        captured_before_report += int(counts.get("captured_before_report") or 0)
        failed_packages += int(counts.get("failed_packages") or 0)
        aggregated_package_results.extend(package_results)
        aggregated_warnings.extend(list(payload.get("warnings") or []) + list(result.get("warnings") or []))
        aggregated_errors.extend(list(payload.get("errors") or []) + list(result.get("errors") or []))
        if result.get("suite_output"):
            suite_outputs.append(result.get("suite_output"))
        if result.get("capture_manifest_output"):
            capture_manifest_outputs.append(result.get("capture_manifest_output"))
        if result.get("capture_root"):
            capture_roots.append(result.get("capture_root"))
        for package_result in package_results:
            package_id = str(package_result.get("package_id") or scene_run.get("package_id") or "")
            if package_id and package_result.get("status") == "pass":
                completed_package_ids.add(package_id)
    aggregated_result = {
        "suite_outputs": suite_outputs,
        "capture_manifest_outputs": capture_manifest_outputs,
        "capture_roots": capture_roots,
        "package_results": aggregated_package_results,
        "counts": {
            "requested_packages": requested_packages,
            "completed_packages": len(completed_package_ids),
            "failed_packages": failed_packages,
            "valid_images": valid_images,
            "captured_before_report": captured_before_report,
        },
        "warnings": sorted(set(aggregated_warnings)),
        "errors": sorted(set(aggregated_errors)),
    }
    if completed_package_ids != expected_packages:
        failed_requirements.append(
            make_failed_requirement(
                "demo_scene_packages_incomplete",
                "Demo scene sweep did not complete successfully for every selected package.",
                expected=sorted(expected_packages),
                actual=sorted(completed_package_ids),
            )
        )
    if valid_images < expected_images:
        failed_requirements.append(
            make_failed_requirement(
                "demo_valid_images",
                "Demo scene sweep did not produce the expected number of valid images.",
                expected=expected_images,
                actual=valid_images,
            )
        )
    if failed_packages != 0:
        failed_requirements.append(
            make_failed_requirement(
                "demo_failed_packages",
                "Demo scene sweep reported failed packages.",
                failed_packages=failed_packages,
            )
        )
    return aggregated_result, failed_requirements

def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict] = []

    equipment_report_path = resolve_equipment_report_path(workspace, args.equipment_report_path)
    equipment_report = load_json(equipment_report_path)
    summary_path = resolve_summary_path(workspace, equipment_report_path, equipment_report, args.summary_path)
    summary_payload = load_json(summary_path)
    registry_path = resolve_registry_path(equipment_report, summary_path, args.registry_path, workspace=workspace)
    registry_payload = load_json(registry_path)

    selected_packages = select_target_packages(equipment_report)
    if len(selected_packages) != REQUIRED_PACKAGE_COUNT:
        failed_requirements.append(
            make_failed_requirement(
                "ready_package_count",
                "D1 requires exactly two runtime-ready character bundles with ready weapon pairs.",
                expected=REQUIRED_PACKAGE_COUNT,
                actual=len(selected_packages),
            )
        )

    selected_character_ids = {str(item.get("package_id") or "") for item in selected_packages}
    selected_weapon_ids = {str(item.get("default_weapon_package_id") or "") for item in selected_packages if item.get("default_weapon_package_id")}
    selected_package_ids = {package_id for package_id in (selected_character_ids | selected_weapon_ids) if package_id}

    conversion_root, manifest_index = build_local_manifest_index(summary_path)
    missing_manifest_package_ids = sorted(package_id for package_id in selected_package_ids if package_id not in manifest_index)
    if missing_manifest_package_ids:
        failed_requirements.append(
            make_failed_requirement(
                "manifest_resolution",
                "One or more selected packages could not be resolved to a local manifest.json.",
                package_ids=missing_manifest_package_ids,
                conversion_root=str(conversion_root),
            )
        )

    filtered_summary_path = output_root / "d1_demo_suite_summary.json"
    filtered_registry_path = output_root / "d1_demo_equipment_registry.json"
    write_json(filtered_summary_path, filter_summary_payload(summary_payload, selected_package_ids, manifest_index))
    write_json(filtered_registry_path, filter_registry_payload(registry_payload, selected_character_ids, selected_weapon_ids))

    inspect_before_path = output_root / "inspect_host_demo_before.json"
    inspect_after_import_path = output_root / "inspect_host_demo_after_import.json"
    build_result_path = output_root / "build_equipment_registry_demo_result.json"
    demo_equipment_report_path = output_root / "ue_equipment_assets_report.demo.json"
    scene_action_root = output_root / "scene_sweep"
    capture_root = output_root / "captures"

    inspect_before_payload = run_host_command(workspace, "inspect-host", {}, inspect_before_path)
    import_results = []
    if not failed_requirements:
        for package_id in sorted(selected_package_ids):
            manifest_path = manifest_index[package_id]
            output_path = output_root / "imports" / f"{package_id}.json"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            payload = run_host_command(
                workspace,
                "import-package",
                {"manifest": str(manifest_path)},
                output_path,
            )
            import_results.append(
                {
                    "package_id": package_id,
                    "manifest_path": str(manifest_path),
                    "output_path": str(output_path.resolve()),
                    "payload": payload,
                }
            )
        import_records, import_failures = evaluate_imports(import_results, selected_package_ids)
        failed_requirements.extend(import_failures)
    else:
        import_records = []

    inspect_after_import_payload = run_host_command(workspace, "inspect-host", {}, inspect_after_import_path)

    build_payload = {
        "success": False,
        "result": {},
        "warnings": [],
        "errors": ["build_not_run"],
    }
    if not failed_requirements:
        build_payload = run_host_command(
            workspace,
            "build-equipment-registry",
            {
                "registry_json": str(filtered_registry_path.resolve()),
                "report_path": str(demo_equipment_report_path.resolve()),
            },
            build_result_path,
        )
        build_result = dict(build_payload.get("result") or {})
        runtime_ready_hosts = int((build_result.get("counts") or {}).get("runtime_ready_host_blueprints") or 0)
        if not build_payload.get("success"):
            failed_requirements.append(
                make_failed_requirement(
                    "demo_registry_build",
                    "Demo host build-equipment-registry failed.",
                    output_path=str(build_result_path.resolve()),
                )
            )
        elif runtime_ready_hosts < REQUIRED_PACKAGE_COUNT:
            failed_requirements.append(
                make_failed_requirement(
                    "demo_runtime_ready_hosts",
                    "Demo host did not produce two runtime-ready host blueprints.",
                    expected=REQUIRED_PACKAGE_COUNT,
                    actual=runtime_ready_hosts,
                )
            )

    scene_runs: list[dict] = []
    scene_result = {}
    if not failed_requirements:
        for package_id in sorted(selected_character_ids):
            scene_output_root = scene_action_root / package_id
            scene_output_root.mkdir(parents=True, exist_ok=True)
            action_result_path = scene_output_root / "run_scene_sweep_demo_result.json"
            suite_output_path = scene_output_root / "ue_animation_suite_summary.demo.json"
            manifest_output_path = scene_output_root / "ue_capture_manifest.demo.json"
            payload = run_host_command(
                workspace,
                "run-scene-sweep",
                {
                    "summary": str(filtered_summary_path.resolve()),
                    "report_path": str(demo_equipment_report_path.resolve()),
                    "package_id": package_id,
                    "level_path": DEMO_LEVEL_PATH,
                    "scenario_names": list(SCENARIO_NAMES),
                    "capture_root": str((capture_root / package_id).resolve()),
                    "suite_output": str(suite_output_path.resolve()),
                    "capture_manifest_output": str(manifest_output_path.resolve()),
                    "level_lifecycle": FIXED_EXECUTION_PROFILE["level_lifecycle"],
                    "camera_lifecycle": FIXED_EXECUTION_PROFILE["camera_lifecycle"],
                    "scenario_scheduling": FIXED_EXECUTION_PROFILE["scenario_scheduling"],
                    "completion_strategy": FIXED_EXECUTION_PROFILE["completion_strategy"],
                    "camera_mode": FIXED_EXECUTION_PROFILE["camera_mode"],
                    "capture_width": FIXED_EXECUTION_PROFILE["capture_width"],
                    "capture_height": FIXED_EXECUTION_PROFILE["capture_height"],
                    "capture_delay_seconds": FIXED_EXECUTION_PROFILE["capture_delay_seconds"],
                    "settle_timeout_seconds": FIXED_EXECUTION_PROFILE["settle_timeout_seconds"],
                    "file_stability_window_seconds": FIXED_EXECUTION_PROFILE["file_stability_window_seconds"],
                    "viewport_pump_interval_seconds": FIXED_EXECUTION_PROFILE["viewport_pump_interval_seconds"],
                    "quit_barrier_seconds": FIXED_EXECUTION_PROFILE["quit_barrier_seconds"],
                },
                action_result_path,
            )
            scene_runs.append(
                {
                    "package_id": package_id,
                    "output_path": str(action_result_path.resolve()),
                    "payload": payload,
                }
            )
        scene_result, scene_failures = evaluate_scene_sweeps(
            scene_runs,
            expected_packages=selected_character_ids,
            expected_images=len(selected_character_ids) * len(SCENARIO_NAMES),
        )
        failed_requirements.extend(scene_failures)

    report_status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(report_status, failed_requirements, previous_report, previous_report_path, 'd1_first_complete_pass')
    inspect_before_result = dict(inspect_before_payload.get("result") or {})
    inspect_after_import_result = dict(inspect_after_import_payload.get("result") or {})
    build_result = dict(build_payload.get("result") or {})

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": report_status,
            "success": not failed_requirements,
            "workspace_config": workspace["config_path"],
            "host_key": DEMO_HOST_KEY,
            "level_path": DEMO_LEVEL_PATH,
            "required_package_count": REQUIRED_PACKAGE_COUNT,
            "resolved_character_package_ids": sorted(selected_character_ids),
            "resolved_weapon_package_ids": sorted(selected_weapon_ids),
            "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
            "counts": {
                "selected_characters": len(selected_character_ids),
                "selected_weapons": len(selected_weapon_ids),
                "imports_requested": len(selected_package_ids),
                "imports_passed": sum(1 for item in import_records if item.get("status") == "pass"),
                "runtime_ready_host_blueprints": int((build_result.get("counts") or {}).get("runtime_ready_host_blueprints") or 0),
                "ready_host_blueprints": int((build_result.get("counts") or {}).get("ready_host_blueprints") or 0),
                "valid_images": int((scene_result.get("counts") or {}).get("valid_images") or 0),
                "captured_before_report": int((scene_result.get("counts") or {}).get("captured_before_report") or 0),
                "failed_packages": int((scene_result.get("counts") or {}).get("failed_packages") or 0),
            },
            "failed_requirements": failed_requirements,
            "inspect_host": {
                "before_import": {
                    "asset_root_exists": inspect_before_result.get("asset_root_exists"),
                    "asset_count_under_root": inspect_before_result.get("asset_count_under_root"),
                },
                "after_import": {
                    "asset_root_exists": inspect_after_import_result.get("asset_root_exists"),
                    "asset_count_under_root": inspect_after_import_result.get("asset_count_under_root"),
                },
            },
            "imports": import_records,
            "build_registry": {
                "status": "pass" if build_payload.get("success") else "fail",
                "report_path": str(demo_equipment_report_path.resolve()),
                "registry_asset": build_result.get("registry_asset"),
                "counts": dict(build_result.get("counts") or {}),
                "warnings": list(build_payload.get("warnings") or []) + list(build_result.get("warnings") or []),
                "errors": list(build_payload.get("errors") or []) + list(build_result.get("errors") or []),
            },
            "scene_sweep": {
                "status": "pass" if scene_runs and not scene_failures else "fail" if scene_runs else "not_run",
                "result": scene_result,
                "action_results": scene_runs,
                "warnings": list(scene_result.get("warnings") or []),
                "errors": list(scene_result.get("errors") or []),
            },
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "equipment_report_path": str(equipment_report_path.resolve()),
                "summary_path": str(summary_path.resolve()),
                "registry_path": str(registry_path.resolve()),
                "filtered_summary_path": str(filtered_summary_path.resolve()),
                "filtered_registry_path": str(filtered_registry_path.resolve()),
                "inspect_host_before_path": str(inspect_before_path.resolve()),
                "inspect_host_after_import_path": str(inspect_after_import_path.resolve()),
                "build_registry_action_result_path": str(build_result_path.resolve()),
                "demo_equipment_report_path": str(demo_equipment_report_path.resolve()),
                "scene_action_root": str(scene_action_root.resolve()),
                "capture_root": str(capture_root.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
            },
        },
        "aiue_demo_gate_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_demo_gate_report",
            notes=["internal_demo_onboarding_gate", "demo_host_only"],
        ),
    )
    report_path = output_root / "d1_demo_gate_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    print(f"D1 demo gate report written to: {report_path}")
    raise SystemExit(0 if report_payload.get("status") == "pass" else 1)

if __name__ == "__main__":
    main()



