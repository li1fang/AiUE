from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json
from aiue_unreal.host_bridge import run_host_auto_ue_cli

GATE_ID = "visual_proof_v1"
REQUIRED_MODE = "editor_rendered"
REQUIRED_SHOTS = ["front", "side", "top"]
FIXED_EXECUTION_PROFILE = {
    "mode": REQUIRED_MODE,
    "cell_strategy": "isolated_vertical_cell",
    "cell_origin": {"x": 0.0, "y": 0.0, "z": 30000.0},
    "shot_order": list(REQUIRED_SHOTS),
    "capture_width": 1280,
    "capture_height": 720,
    "capture_delay_seconds": 0.2,
    "subject_min_screen_coverage": 0.015,
    "weapon_min_screen_coverage": 0.001,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE V1 visual proof gate on the kernel host.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--equipment-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def repo_root_from_workspace(workspace: dict) -> Path:
    return Path(workspace["paths"].get("aiue_repo_root") or REPO_ROOT).expanduser().resolve()


def default_output_root(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / f"{GATE_ID}_{run_stamp()}"


def default_latest_report_path(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / f"latest_{GATE_ID}_report.json"


def resolve_equipment_report_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Equipment report path does not exist: {candidate}")
    local_auto_report = Path(workspace["paths"].get("auto_ue_cli_output_root") or "") / "ue_equipment_assets_report.local.json"
    if local_auto_report.exists():
        return local_auto_report.resolve()
    raise FileNotFoundError("No ue_equipment_assets_report.local.json could be resolved for V1 visual proof.")


def make_failed_requirement(requirement_id: str, message: str, **details) -> dict:
    payload = {
        "id": requirement_id,
        "message": message,
    }
    payload.update(details)
    return payload


def verify_editor_capture_capability(workspace: dict) -> list[dict]:
    capability_path = Path(workspace["paths"]["capability_probe_root"]).expanduser().resolve() / "latest_capabilities.json"
    if not capability_path.exists():
        return [
            make_failed_requirement(
                "editor_capture_capability",
                "latest_capabilities.json is missing, so V1 cannot verify editor capture capability.",
                capability_path=str(capability_path),
            )
        ]
    payload = load_json(capability_path)
    for entry in payload.get("capabilities") or []:
        if entry.get("capability_id") != "capture_frame":
            continue
        if entry.get("mode") != REQUIRED_MODE:
            continue
        if entry.get("callable") and entry.get("reliable"):
            return []
        return [
            make_failed_requirement(
                "editor_capture_capability",
                "editor_rendered capture_frame is not callable and reliable.",
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
        and record.get("default_weapon_component_attach_socket_name") == "WeaponSocket"
        and bool(record.get("default_weapon_package_id"))
        and bool(record.get("asset_path"))
        and bool(loadout.get("has_ready_weapon_pairs"))
    )


def select_target_package(equipment_report: dict) -> dict | None:
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
    selected = sorted(selected, key=lambda item: item["package_id"])
    return selected[0] if selected else None


def build_discussion_signal(status: str, failed_requirements: list[dict], previous_report: dict | None, previous_report_path: Path | None) -> dict:
    current_failed_ids = sorted({item.get("id") for item in failed_requirements if item.get("id")})
    previous_failed_ids = sorted(
        {
            item.get("id")
            for item in ((previous_report or {}).get("failed_requirements") or [])
            if isinstance(item, dict) and item.get("id")
        }
    )
    previous_status = (previous_report or {}).get("status")
    payload = {
        "should_discuss": False,
        "reason": None,
        "previous_report_path": str(previous_report_path) if previous_report_path else None,
        "repeated_failed_requirement_ids": [],
    }
    if status == "pass" and previous_status != "pass":
        payload["should_discuss"] = True
        payload["reason"] = "v1_first_complete_pass"
        return payload
    if status != "pass" and current_failed_ids and previous_status != "pass" and current_failed_ids == previous_failed_ids:
        payload["should_discuss"] = True
        payload["reason"] = "same_failed_requirement_two_rounds"
        payload["repeated_failed_requirement_ids"] = current_failed_ids
    return payload


def evaluate_visual_proof_result(result: dict, gate_output_root: Path) -> tuple[dict, list[dict]]:
    failed_requirements = []
    shots = {item.get("shot_id"): item for item in (result.get("shots") or []) if item.get("shot_id")}
    evaluated_shots = []
    subject_pass_count = 0
    weapon_pass_count = 0
    for shot_id in REQUIRED_SHOTS:
        shot = dict(shots.get(shot_id) or {})
        image_path = Path(shot.get("image_path")).expanduser().resolve() if shot.get("image_path") else None
        image_exists = bool(image_path and image_path.exists())
        subject_coverage = float(shot.get("subject_screen_coverage") or 0.0)
        weapon_coverage = float(shot.get("weapon_screen_coverage") or 0.0)
        line_of_sight_clear = bool(shot.get("line_of_sight_clear"))
        valid = image_exists and shot.get("status") == "pass"
        subject_pass = subject_coverage >= FIXED_EXECUTION_PROFILE["subject_min_screen_coverage"] and line_of_sight_clear and image_exists
        weapon_pass = weapon_coverage >= FIXED_EXECUTION_PROFILE["weapon_min_screen_coverage"] and image_exists
        subject_pass_count += int(subject_pass)
        weapon_pass_count += int(weapon_pass)
        evaluated = {
            "shot_id": shot_id,
            "camera_id": shot.get("camera_id") or shot_id,
            "image_path": str(image_path) if image_path else "",
            "subject_screen_coverage": subject_coverage,
            "weapon_screen_coverage": weapon_coverage,
            "line_of_sight_clear": line_of_sight_clear,
            "status": "pass" if valid and subject_pass else "fail",
            "warnings": list(shot.get("warnings") or []),
            "errors": list(shot.get("errors") or []),
        }
        evaluated_shots.append(evaluated)
    if result.get("status") != "pass":
        for requirement_id in (result.get("failed_requirements") or []):
            failed_requirements.append(
                make_failed_requirement(
                    str(requirement_id),
                    "Kernel host visual proof reported a failed requirement.",
                    gate_output_root=str(gate_output_root),
                )
            )
    if not result.get("character_mesh_asset"):
        failed_requirements.append(make_failed_requirement("mesh_missing", "Character mesh asset is missing in host visual proof result."))
    if not result.get("weapon_mesh_asset"):
        failed_requirements.append(make_failed_requirement("weapon_missing", "Weapon mesh asset is missing in host visual proof result."))
    if not (result.get("main_mesh_bounds") or {}).get("non_zero"):
        failed_requirements.append(make_failed_requirement("bounds_invalid", "Main mesh bounds are zero or invalid."))
    if subject_pass_count < 2:
        failed_requirements.append(
            make_failed_requirement(
                "out_of_frame",
                "At least two of the three visual proof shots must keep the subject in frame with sufficient coverage.",
                subject_pass_count=subject_pass_count,
            )
        )
    if weapon_pass_count < 1:
        failed_requirements.append(
            make_failed_requirement(
                "weapon_invisible",
                "At least one visual proof shot must show the weapon with sufficient screen coverage.",
                weapon_pass_count=weapon_pass_count,
            )
        )
    if len(shots) != len(REQUIRED_SHOTS):
        failed_requirements.append(
            make_failed_requirement(
                "shot_count",
                "Visual proof must produce exactly three fixed shots.",
                expected=len(REQUIRED_SHOTS),
                actual=len(shots),
            )
        )
    if any("capture_failed" in (shot.get("errors") or []) for shot in evaluated_shots):
        failed_requirements.append(make_failed_requirement("capture_failed", "At least one visual proof shot failed to capture."))
    if any("occluded" in (shot.get("errors") or []) for shot in evaluated_shots):
        failed_requirements.append(make_failed_requirement("occluded", "At least one visual proof shot is occluded."))
    return (
        {
            "status": "pass" if not failed_requirements else "fail",
            "package_id": result.get("package_id"),
            "host_id": result.get("host_id"),
            "host_blueprint_asset": result.get("host_blueprint_asset"),
            "character_mesh_asset": result.get("character_mesh_asset"),
            "weapon_mesh_asset": result.get("weapon_mesh_asset"),
            "main_mesh_component": dict(result.get("main_mesh_component") or {}),
            "weapon_mesh_component": dict(result.get("weapon_mesh_component") or {}),
            "main_mesh_bounds": dict(result.get("main_mesh_bounds") or {}),
            "weapon_mesh_bounds": dict(result.get("weapon_mesh_bounds") or {}),
            "main_mesh_world_transform": dict(result.get("main_mesh_world_transform") or {}),
            "weapon_mesh_world_transform": dict(result.get("weapon_mesh_world_transform") or {}),
            "component_visibility": dict(result.get("component_visibility") or {}),
            "shots": evaluated_shots,
            "warnings": list(result.get("warnings") or []),
            "errors": list(result.get("errors") or []),
        },
        failed_requirements,
    )


def build_report(
    workspace: dict,
    output_root: Path,
    latest_report_path: Path,
    equipment_report_path: Path,
    selected_package: dict | None,
    visual_result: dict,
    failed_requirements: list[dict],
    previous_report: dict | None,
    previous_report_path: Path | None,
) -> dict:
    shots = list(visual_result.get("shots") or [])
    discussion_signal = build_discussion_signal(
        "pass" if not failed_requirements else "fail",
        failed_requirements,
        previous_report,
        previous_report_path,
    )
    counts = {
        "requested_packages": 1 if selected_package else 0,
        "resolved_packages": 1 if selected_package else 0,
        "expected_shots": len(REQUIRED_SHOTS),
        "captured_shots": sum(1 for shot in shots if shot.get("image_path")),
        "passing_shots": sum(1 for shot in shots if shot.get("status") == "pass"),
        "subject_pass_shots": sum(
            1 for shot in shots if shot.get("subject_screen_coverage", 0.0) >= FIXED_EXECUTION_PROFILE["subject_min_screen_coverage"]
        ),
        "weapon_pass_shots": sum(
            1 for shot in shots if shot.get("weapon_screen_coverage", 0.0) >= FIXED_EXECUTION_PROFILE["weapon_min_screen_coverage"]
        ),
    }
    return with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": "pass" if not failed_requirements else "fail",
            "success": not failed_requirements,
            "workspace_config": workspace["config_path"],
            "host_key": "kernel",
            "package_id": selected_package.get("package_id") if selected_package else None,
            "host_blueprint_asset": (selected_package or {}).get("host_blueprint_asset"),
            "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
            "counts": counts,
            "failed_requirements": failed_requirements,
            "visual_result": visual_result,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "equipment_report_path": str(equipment_report_path.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
                "visual_proof_report_path": str((output_root / "visual_proof_report.json").resolve()),
                "host_action_result_path": str((output_root / "inspect-host-visual.json").resolve()),
            },
        },
        "aiue_visual_proof_gate_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_visual_proof_gate_report",
            notes=["internal_visual_proof_gate", "kernel_host_only"],
        ),
    )


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    visual_proof_config = dict(workspace.get("visual_proof") or {})
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    equipment_report_path = resolve_equipment_report_path(workspace, args.equipment_report_path)
    equipment_report = load_json(equipment_report_path)
    failed_requirements = verify_editor_capture_capability(workspace)
    selected_package = select_target_package(equipment_report)
    if not selected_package:
        failed_requirements.append(
            make_failed_requirement(
                "ready_package_missing",
                "No runtime-ready package with ready weapon pairs could be selected for V1 visual proof.",
            )
        )

    visual_result = {
        "status": "not_run",
        "shots": [],
    }
    if not failed_requirements and selected_package:
        host_action_result_path = output_root / "inspect-host-visual.json"
        visual_report_path = output_root / "visual_proof_report.json"
        params = {
            "report_path": str(equipment_report_path.resolve()),
            "package_id": selected_package["package_id"],
            "runtime_ready_only": True,
            "output_root": str((output_root / "captures").resolve()),
            "cell_origin": dict(visual_proof_config.get("cell_origin") or FIXED_EXECUTION_PROFILE["cell_origin"]),
            "capture_width": int(visual_proof_config.get("capture_width") or FIXED_EXECUTION_PROFILE["capture_width"]),
            "capture_height": int(visual_proof_config.get("capture_height") or FIXED_EXECUTION_PROFILE["capture_height"]),
            "capture_delay_seconds": float(visual_proof_config.get("capture_delay_seconds") or FIXED_EXECUTION_PROFILE["capture_delay_seconds"]),
            "subject_min_screen_coverage": float(visual_proof_config.get("subject_min_screen_coverage") or FIXED_EXECUTION_PROFILE["subject_min_screen_coverage"]),
            "weapon_min_screen_coverage": float(visual_proof_config.get("weapon_min_screen_coverage") or FIXED_EXECUTION_PROFILE["weapon_min_screen_coverage"]),
        }
        try:
            invocation = run_host_auto_ue_cli(
                workspace_or_config=workspace,
                mode=REQUIRED_MODE,
                command="inspect-host-visual",
                params=params,
                output_path=str(host_action_result_path),
                host_key="kernel",
            )
            payload = invocation.get("payload") or {}
        except Exception as exc:
            if host_action_result_path.exists():
                payload = load_json(host_action_result_path)
            else:
                payload = {
                    "success": False,
                    "result": {},
                    "warnings": [],
                    "errors": [str(exc)],
                }
        raw_result = dict(payload.get("result") or {})
        write_json(visual_report_path, raw_result)
        visual_result, result_failures = evaluate_visual_proof_result(raw_result, output_root)
        failed_requirements.extend(result_failures)

    report_payload = build_report(
        workspace=workspace,
        output_root=output_root,
        latest_report_path=latest_report_path,
        equipment_report_path=equipment_report_path,
        selected_package=selected_package,
        visual_result=visual_result,
        failed_requirements=failed_requirements,
        previous_report=previous_report,
        previous_report_path=previous_report_path,
    )
    report_path = output_root / "v1_visual_proof_gate_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    print(f"V1 visual proof gate report written to: {report_path}")
    raise SystemExit(0 if report_payload.get("status") == "pass" else 1)


if __name__ == "__main__":
    main()
