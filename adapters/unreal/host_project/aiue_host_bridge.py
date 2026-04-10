from __future__ import annotations

import argparse
import json
import re
import subprocess
import shutil
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parent


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def add_aiue_paths(workspace: dict) -> None:
    repo_root = Path(workspace["paths"]["aiue_repo_root"]).expanduser().resolve()
    for entry in (repo_root / "core" / "python",):
        text = str(entry)
        if text not in sys.path:
            sys.path.insert(0, text)


def load_workspace(config_path: str, project_root_override: str | None = None, host_key: str | None = None) -> dict:
    config_file = Path(config_path).expanduser().resolve()
    raw = json.loads(config_file.read_text(encoding="utf-8-sig"))
    config_dir = config_file.parent
    project_root = config_dir.parent

    def expand(value):
        if value is None:
            return None
        text = str(value)
        if not text:
            return text
        if text.startswith("/Game/"):
            return text
        expanded = text.replace("${project_root}", str(project_root))
        expanded = expanded.replace("${config_dir}", str(config_dir))
        expanded = expanded.replace("${workspace_dir}", str(config_dir))
        path = Path(expanded).expanduser()
        if path.is_absolute():
            return str(path.resolve())
        return str((config_dir / path).resolve())

    resolved_paths = {key: expand(value) for key, value in (raw.get("paths") or {}).items()}
    project_root_path = Path(project_root_override).expanduser().resolve() if project_root_override else Path(
        resolved_paths.get("unreal_project_root") or project_root
    ).expanduser().resolve()
    resolved_paths["unreal_project_root"] = str(project_root_path)
    return {
        "project_root": str(project_root),
        "config_path": str(config_file),
        "paths": resolved_paths,
        "probe": raw.get("probe") or {},
        "host_key": str(host_key or ""),
    }


def build_capability_entries(workspace: dict, mode: str) -> list[dict]:
    editor_cmd_exists = Path(workspace["paths"]["unreal_editor_cmd"]).exists()
    editor_gui_exists = Path(workspace["paths"]["unreal_editor_gui"]).exists()
    project_root_exists = Path(workspace["paths"]["unreal_project_root"]).exists()
    conversion_root_exists = Path(workspace["paths"]["conversion_root"]).exists()
    catalog_root_exists = Path(workspace["paths"]["dataset_catalog_root"]).exists()
    project_root = Path(workspace["paths"]["unreal_project_root"])
    plugin_root = project_root / "Plugins" / "AiUEPmxRuntime"
    source_root = plugin_root / "Source" / "AiUEPmxRuntime"
    native_runtime_source_present = all(
        path.exists()
        for path in (
            source_root / "Public" / "PMXCharacterEquipmentComponent.h",
            source_root / "Public" / "PMXCharacterHost.h",
            source_root / "Public" / "PMXEquipmentBlueprintLibrary.h",
            source_root / "Public" / "PMXEquipmentReflection.h",
            source_root / "Private" / "PMXCharacterEquipmentComponent.cpp",
            source_root / "Private" / "PMXCharacterHost.cpp",
            source_root / "Private" / "PMXEquipmentBlueprintLibrary.cpp",
            plugin_root / "AiUEPmxRuntime.uplugin",
        )
    )
    native_runtime_binary_present = any(
        path.exists()
        for path in (
            plugin_root / "Binaries" / "Win64" / "UnrealEditor-AiUEPmxRuntime.dll",
            plugin_root / "Binaries" / "Win64" / "UnrealEditor.modules",
            project_root / "Binaries" / "Win64" / "UnrealEditor.modules",
            *list((project_root / "Binaries" / "Win64").glob("*.target")),
        )
    )
    live_editor_callable = bool(editor_gui_exists and project_root_exists)

    return [
        {
            "capability_id": "capture_frame",
            "category": "capture_ops",
            "mode": "cmd_nullrhi",
            "api_symbol": "UnrealEditor-Cmd NullRHI capture",
            "present": editor_cmd_exists,
            "callable": False,
            "reliable": False,
            "mutates_state": True,
            "preferred": mode == "cmd_nullrhi",
            "evidence": ["nullrhi_capture_not_bootstrapped"],
            "warnings": ["capture pipeline not wired for nullrhi in bootstrap host"],
            "errors": [],
        },
        {
            "capability_id": "capture_frame",
            "category": "capture_ops",
            "mode": "cmd_rendered",
            "api_symbol": "UnrealEditor-Cmd rendered capture",
            "present": editor_cmd_exists,
            "callable": False,
            "reliable": False,
            "mutates_state": True,
            "preferred": mode == "cmd_rendered",
            "evidence": ["rendered_commandlet_capture_not_bootstrapped"],
            "warnings": ["rendered commandlet capture is not enabled in the local host bridge yet"],
            "errors": [],
        },
        {
            "capability_id": "capture_frame",
            "category": "capture_ops",
            "mode": "editor_rendered",
            "api_symbol": "UnrealEditor viewport capture",
            "present": editor_gui_exists,
            "callable": live_editor_callable,
            "reliable": live_editor_callable,
            "mutates_state": True,
            "preferred": True,
            "evidence": [
                "editor_binary_present",
                "unreal_project_present",
                "bootstrap_host_live_editor_capture_bridge",
            ],
            "warnings": [],
            "errors": [],
        },
        {
            "capability_id": "conversion_artifacts",
            "category": "dataset_ops",
            "mode": "offline",
            "api_symbol": "conversion_root",
            "present": conversion_root_exists,
            "callable": conversion_root_exists,
            "reliable": conversion_root_exists,
            "mutates_state": False,
            "preferred": False,
            "evidence": ["conversion_root_exists"] if conversion_root_exists else ["conversion_root_missing"],
            "warnings": [],
            "errors": [],
        },
        {
            "capability_id": "dataset_catalog",
            "category": "dataset_ops",
            "mode": "offline",
            "api_symbol": "dataset_catalog_root",
            "present": catalog_root_exists,
            "callable": catalog_root_exists,
            "reliable": catalog_root_exists,
            "mutates_state": False,
            "preferred": False,
            "evidence": ["dataset_catalog_root_exists"] if catalog_root_exists else ["dataset_catalog_root_missing"],
            "warnings": [],
            "errors": [],
        },
        {
            "capability_id": "native_runtime_component",
            "category": "runtime_ops",
            "mode": "editor_rendered",
            "api_symbol": "PMXCharacterEquipmentComponent",
            "present": native_runtime_source_present,
            "callable": native_runtime_binary_present,
            "reliable": native_runtime_binary_present,
            "mutates_state": False,
            "preferred": False,
            "evidence": [
                item
                for item, enabled in (
                    ("native_runtime_source_present", native_runtime_source_present),
                    ("native_runtime_binary_present", native_runtime_binary_present),
                )
                if enabled
            ] or ["native_runtime_missing"],
            "warnings": [] if native_runtime_binary_present else ["native runtime is present in source but not built yet"],
            "errors": [],
        },
        {
            "capability_id": "dual_host_bridge",
            "category": "runtime_ops",
            "mode": "offline",
            "api_symbol": "AiUE host routing",
            "present": bool(workspace.get("host_key")),
            "callable": bool(project_root_exists),
            "reliable": bool(project_root_exists),
            "mutates_state": False,
            "preferred": False,
            "evidence": [f"host_key:{workspace.get('host_key') or 'implicit'}", "shared_host_bridge"],
            "warnings": [],
            "errors": [],
        },
    ]


def compute_counts(entries: list[dict]) -> dict:
    return {
        "total": len(entries),
        "present": sum(1 for entry in entries if entry.get("present")),
        "callable": sum(1 for entry in entries if entry.get("callable")),
        "reliable": sum(1 for entry in entries if entry.get("reliable")),
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_manifest_artifact(manifest_path: Path, artifact_path: str | None) -> Path | None:
    if not artifact_path:
        return None
    candidate = Path(artifact_path).expanduser()
    if candidate.exists():
        return candidate.resolve()
    local_sibling = manifest_path.parent / candidate.name
    if local_sibling.exists():
        return local_sibling.resolve()
    return candidate.resolve(strict=False)


def sanitize_segment(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff]+", "_", str(value).strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "asset"


def resolve_equipment_report_path(params: dict) -> Path | None:
    explicit = params.get("report_path")
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if candidate.exists():
            return candidate
    for raw_path in (params.get("summary"), params.get("suite_output"), params.get("capture_manifest_output")):
        if not raw_path:
            continue
        base_path = Path(raw_path).expanduser().resolve()
        for sibling_name in ("ue_equipment_assets_report.local.json", "ue_equipment_assets_report.json"):
            candidate = base_path.parent / sibling_name
            if candidate.exists():
                return candidate
    return None


def wait_for_stable_file(path: Path, timeout_seconds: float, stability_window_seconds: float, poll_interval_seconds: float) -> Path | None:
    deadline = time.time() + timeout_seconds
    stable_since = None
    last_size = None
    while time.time() < deadline:
        if path.exists():
            current_size = path.stat().st_size
            if last_size == current_size:
                if stable_since is None:
                    stable_since = time.time()
                elif time.time() - stable_since >= stability_window_seconds:
                    return path
            else:
                last_size = current_size
                stable_since = None
        time.sleep(poll_interval_seconds)
    return path if path.exists() else None


def load_suite_summary_record(summary_path: str | None, package_id: str | None) -> dict:
    if not summary_path or not package_id:
        return {}
    candidate = Path(summary_path).expanduser().resolve()
    if not candidate.exists():
        return {}
    payload = json.loads(candidate.read_text(encoding="utf-8-sig"))
    for entry in payload.get("successes") or []:
        if entry.get("package_id") == package_id:
            return entry
    for entry in payload.get("entries") or []:
        if entry.get("package_id") == package_id:
            return entry
    return {}


def scenario_capture_overrides(index: int, scenario_name: str, params: dict) -> dict:
    stage_map = dict(params.get("scenario_stage_map") or {})
    stage_entry = dict(stage_map.get(scenario_name) or {})
    camera_mode = str(stage_entry.get("camera_mode") or params.get("camera_mode") or "auto_framing")
    if camera_mode == "anchor_actor":
        return {
            "camera_mode": "anchor_actor",
            "spawn_anchor_actor_label": stage_entry.get("spawn_anchor_actor_label") or params.get("spawn_anchor_actor_label"),
            "camera_anchor_actor_label": stage_entry.get("camera_anchor_actor_label") or params.get("camera_anchor_actor_label"),
            "expected_spawn_location": stage_entry.get("expected_spawn_location") or params.get("expected_spawn_location"),
            "expected_spawn_rotation": stage_entry.get("expected_spawn_rotation") or params.get("expected_spawn_rotation"),
            "expected_camera_location": stage_entry.get("expected_camera_location") or params.get("expected_camera_location"),
            "expected_camera_rotation": stage_entry.get("expected_camera_rotation") or params.get("expected_camera_rotation"),
        }
    base_location = dict(params.get("location") or {"x": 0.0, "y": 0.0, "z": 120.0})
    base_rotation = dict(params.get("rotation") or {"pitch": 0.0, "yaw": 180.0, "roll": 0.0})
    base_distance = float(params.get("camera_distance") or 320.0)
    base_lateral = float(params.get("camera_lateral_offset") or -160.0)
    base_height = float(params.get("camera_height") or 120.0)
    presets = {
        "idle_2s": {
            "location": base_location,
            "rotation": base_rotation,
            "camera_distance": base_distance,
            "camera_lateral_offset": base_lateral,
            "camera_height": base_height,
        },
        "walk_forward_2s": {
            "location": {"x": base_location["x"] + 110.0 + (index * 5.0), "y": base_location["y"] + 30.0, "z": base_location["z"]},
            "rotation": {"pitch": base_rotation["pitch"], "yaw": base_rotation["yaw"] - 15.0, "roll": base_rotation["roll"]},
            "camera_distance": base_distance - 20.0,
            "camera_lateral_offset": base_lateral + 15.0,
            "camera_height": base_height,
        },
        "run_forward_2s": {
            "location": {"x": base_location["x"] + 220.0 + (index * 10.0), "y": base_location["y"] - 55.0, "z": base_location["z"]},
            "rotation": {"pitch": base_rotation["pitch"], "yaw": base_rotation["yaw"] - 32.0, "roll": base_rotation["roll"]},
            "camera_distance": base_distance - 35.0,
            "camera_lateral_offset": base_lateral + 40.0,
            "camera_height": base_height + 6.0,
        },
        "jump_land_1cycle": {
            "location": {"x": base_location["x"] + 90.0, "y": base_location["y"] + 95.0, "z": base_location["z"] + 95.0},
            "rotation": {"pitch": base_rotation["pitch"], "yaw": base_rotation["yaw"] - 8.0, "roll": base_rotation["roll"]},
            "camera_distance": base_distance + 25.0,
            "camera_lateral_offset": base_lateral - 10.0,
            "camera_height": base_height + 55.0,
            "target_height_offset": float(params.get("target_height_offset") or 150.0),
        },
    }
    selected = presets.get(scenario_name, presets["idle_2s"])
    return {
        "camera_mode": "auto_framing",
        "location": selected["location"],
        "rotation": selected["rotation"],
        "camera_distance": selected["camera_distance"],
        "camera_lateral_offset": selected["camera_lateral_offset"],
        "camera_height": selected["camera_height"],
        "target_height_offset": float(selected.get("target_height_offset", params.get("target_height_offset") or 0.0)),
    }


def finalize_capture_payload(host_payload: dict, expected_output_path: Path, params: dict) -> dict:
    if host_payload.get("success") and (host_payload.get("result") or {}).get("output_exists"):
        return host_payload
    stable_file = wait_for_stable_file(
        expected_output_path,
        float(params.get("settle_timeout_seconds") or params.get("timeout_seconds") or 20.0),
        float(params.get("file_stability_window_seconds") or 0.75),
        float(params.get("viewport_pump_interval_seconds") or params.get("poll_interval_seconds") or 0.2),
    )
    if not stable_file:
        return host_payload
    result = dict(host_payload.get("result") or {})
    result["output_exists"] = True
    result["output_path"] = str(stable_file)
    result["requested_output_path"] = str(expected_output_path)
    result["file_size_bytes"] = stable_file.stat().st_size
    result["task_done"] = True
    result["warnings"] = [warning for warning in (result.get("warnings") or []) if warning != "screenshot_output_missing_after_task_completion"]
    result["errors"] = []
    host_payload["success"] = True
    host_payload["result"] = result
    host_payload["warnings"] = [warning for warning in (host_payload.get("warnings") or []) if warning != "screenshot_output_missing_after_task_completion"]
    host_payload["errors"] = []
    return host_payload


def run_scene_sweep(workspace: dict, mode: str, params: dict) -> dict:
    summary_path = params.get("summary")
    package_id = params.get("package_id")
    report_path = resolve_equipment_report_path(params)
    scenario_names = list(params.get("scenario_names") or ["idle_2s", "walk_forward_2s", "run_forward_2s", "jump_land_1cycle"])
    capture_root = Path(params.get("capture_root") or (Path(workspace["paths"]["visual_review_output_root"]).resolve() / "scene_sweep")).expanduser().resolve()
    capture_root.mkdir(parents=True, exist_ok=True)
    suite_output_path = Path(params.get("suite_output") or (capture_root / "ue_animation_suite_summary.json")).expanduser().resolve()
    capture_manifest_path = Path(params.get("capture_manifest_output") or (capture_root / "ue_capture_manifest.json")).expanduser().resolve()

    suite_record = load_suite_summary_record(summary_path, package_id)
    package_capture_root = capture_root / sanitize_segment(package_id or suite_record.get("sample_id") or "package")
    package_capture_root.mkdir(parents=True, exist_ok=True)

    scenario_results = []
    capture_entries = []
    package_warnings = []
    for scenario_index, scenario_name in enumerate(scenario_names, start=1):
        overrides = scenario_capture_overrides(scenario_index, scenario_name, params)
        scenario_camera_mode = str(overrides.get("camera_mode") or params.get("camera_mode") or "auto_framing")
        image_path = package_capture_root / f"{scenario_index:02d}_{sanitize_segment(scenario_name)}.png"
        capture_request = {
            "command": "capture-frame",
            "asset_root": workspace["paths"]["asset_root"],
            "summary": summary_path,
            "report_path": str(report_path) if report_path else None,
            "package_id": package_id,
            "sample_id": suite_record.get("sample_id"),
            "runtime_ready_only": True,
            "level_path": params.get("level_path") or params.get("scene_level_path") or workspace.get("animation", {}).get("scene_level_path"),
            "actor_label": f"AIUE_{sanitize_segment(package_id or suite_record.get('sample_id') or 'package')}_{sanitize_segment(scenario_name)}",
            "output_path": str(image_path),
            "width": int(params.get("capture_width") or params.get("width") or workspace.get("animation", {}).get("capture_width", 1280)),
            "height": int(params.get("capture_height") or params.get("height") or workspace.get("animation", {}).get("capture_height", 720)),
            "capture_delay_seconds": float(params.get("capture_delay_seconds") or workspace.get("animation", {}).get("capture_delay_seconds", 0.2)),
            "camera_mode": scenario_camera_mode,
            "timeout_seconds": float(params.get("settle_timeout_seconds") or 20.0),
            "file_stability_window_seconds": float(params.get("file_stability_window_seconds") or 0.75),
            "poll_interval_seconds": float(params.get("viewport_pump_interval_seconds") or 0.2),
        }
        if scenario_camera_mode == "anchor_actor":
            capture_request["spawn_anchor_actor_label"] = str(overrides.get("spawn_anchor_actor_label") or params.get("spawn_anchor_actor_label") or "")
            capture_request["camera_anchor_actor_label"] = str(overrides.get("camera_anchor_actor_label") or params.get("camera_anchor_actor_label") or "")
        else:
            capture_request["camera_distance"] = overrides["camera_distance"]
            capture_request["camera_lateral_offset"] = overrides["camera_lateral_offset"]
            capture_request["camera_height"] = overrides["camera_height"]
            capture_request["target_height_offset"] = overrides["target_height_offset"]
            capture_request["location"] = overrides["location"]
            capture_request["rotation"] = overrides["rotation"]
        host_payload = run_unreal_python_request(workspace, mode, capture_request)
        host_payload = finalize_capture_payload(host_payload, image_path, params)
        result = dict(host_payload.get("result") or {})
        capture_success = bool(host_payload.get("success")) and bool(result.get("output_exists"))
        capture_status = "captured_before_report" if capture_success else "capture_failed"
        scenario_result = {
            "scenario": scenario_name,
            "status": "pass" if capture_success else "fail",
            "capture_status": capture_status,
            "image_path": result.get("output_path") or str(image_path),
            "camera_source": result.get("camera_source") or scenario_camera_mode,
            "spawn_anchor_actor_label": result.get("spawn_anchor_actor_label") or capture_request.get("spawn_anchor_actor_label") or "",
            "camera_anchor_actor_label": result.get("camera_anchor_actor_label") or capture_request.get("camera_anchor_actor_label") or "",
            "subject_visible": bool(result.get("subject_visible")),
            "subject_visibility": dict(result.get("subject_visibility") or {}),
            "warnings": list(result.get("warnings") or host_payload.get("warnings") or []),
            "errors": list(result.get("errors") or host_payload.get("errors") or []),
            "camera_plan": result.get("camera_plan"),
        }
        scenario_results.append(scenario_result)
        capture_entries.append(
            {
                "sample_id": suite_record.get("sample_id"),
                "package_id": package_id,
                "scenario": scenario_name,
                "image_path": scenario_result["image_path"],
                "capture_status": capture_status,
                "camera_source": scenario_result["camera_source"],
                "spawn_anchor_actor_label": scenario_result["spawn_anchor_actor_label"],
                "camera_anchor_actor_label": scenario_result["camera_anchor_actor_label"],
                "subject_visible": scenario_result["subject_visible"],
                "reference_dir": str(package_capture_root),
                "warnings": scenario_result["warnings"],
                "errors": scenario_result["errors"],
                "host_blueprint_asset_path": result.get("host_blueprint_asset_path"),
            }
        )
        package_warnings.extend([warning for warning in scenario_result["warnings"] if warning not in package_warnings])

    failed_packages = 1 if any(item["status"] != "pass" for item in scenario_results) else 0
    package_results = [
        {
            "package_id": package_id,
            "sample_id": suite_record.get("sample_id"),
            "host_blueprint_asset_path": next((entry.get("host_blueprint_asset_path") for entry in capture_entries if entry.get("host_blueprint_asset_path")), None),
            "status": "fail" if failed_packages else "pass",
            "warnings": package_warnings,
            "errors": ["one_or_more_scenarios_failed"] if failed_packages else [],
            "scenario_results": scenario_results,
        }
    ]
    manifest_payload = {
        "generated_at_utc": now_utc(),
        "suite_name": "ue_scene_sweep",
        "suite_summary_path": str(suite_output_path),
        "capture_enabled": True,
        "capture_root": str(capture_root),
        "entries": capture_entries,
    }
    summary_payload = {
        "generated_at_utc": now_utc(),
        "summary_source_path": summary_path,
        "capture_root": str(capture_root),
        "suite_output_path": str(suite_output_path),
        "capture_manifest_output": str(capture_manifest_path),
        "package_results": package_results,
        "scenario_names": scenario_names,
        "config": {
            "validation_mode": params.get("validation_mode"),
            "camera_lifecycle": params.get("camera_lifecycle"),
            "camera_mode": params.get("camera_mode") or "auto_framing",
            "level_lifecycle": params.get("level_lifecycle"),
            "scenario_scheduling": params.get("scenario_scheduling"),
            "completion_strategy": params.get("completion_strategy"),
        },
    }
    write_json(capture_manifest_path, manifest_payload)
    write_json(suite_output_path, summary_payload)
    valid_images = sum(1 for entry in capture_entries if entry.get("capture_status") == "captured_before_report")
    return {
        "summary_path": summary_path,
        "suite_output": str(suite_output_path),
        "capture_manifest_output": str(capture_manifest_path),
        "capture_root": str(capture_root),
        "level_path": params.get("level_path") or params.get("scene_level_path") or workspace.get("animation", {}).get("scene_level_path"),
        "current_level_path": params.get("level_path") or params.get("scene_level_path") or workspace.get("animation", {}).get("scene_level_path"),
        "scenario_names": scenario_names,
        "package_results": package_results,
        "counts": {
            "requested_packages": 1 if package_id else 0,
            "completed_packages": 0 if failed_packages else 1,
            "failed_packages": failed_packages,
            "capture_entries": len(capture_entries),
            "valid_images": valid_images,
            "captured_before_report": valid_images,
            "captured_after_report_before_exit": 0,
            "captured_after_exit": 0,
            "late_captures": 0,
        },
        "warnings": [],
        "errors": ["scene_sweep_failed_packages_present"] if failed_packages else [],
    }


def find_uproject(workspace: dict) -> Path:
    project_root = Path(workspace["paths"]["unreal_project_root"]).expanduser().resolve()
    matches = sorted(project_root.glob("*.uproject"))
    if not matches:
        raise FileNotFoundError(f"No .uproject file found under {project_root}")
    return matches[0]


def mode_args(mode: str) -> list[str]:
    if mode == "cmd_nullrhi":
        return ["-NullRHI"]
    if mode == "cmd_rendered":
        return ["-AllowCommandletRendering"]
    return []


def run_unreal_python_request(workspace: dict, mode: str, request: dict) -> dict:
    project_root = Path(workspace["paths"]["unreal_project_root"]).expanduser().resolve()
    host_root = project_root / "Saved" / "pmx_pipeline" / "host_bridge"
    request_path = host_root / f"{request['command']}_{uuid.uuid4().hex[:8]}_request.json"
    response_path = host_root / f"{request['command']}_{uuid.uuid4().hex[:8]}_response.json"
    script_path = SCRIPT_ROOT / "aiue_unreal_command.py"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(request_path, request)

    script_arg = script_path.resolve().as_posix()
    if mode == "editor_rendered":
        executable = workspace["paths"]["unreal_editor_gui"]
        command = [
            executable,
            str(find_uproject(workspace)),
            f"-ExecutePythonScript={script_arg}",
            "-unattended",
            "-nop4",
            "-nosplash",
            "-stdout",
            "-FullStdOutLogOutput",
        ]
    else:
        executable = workspace["paths"]["unreal_editor_cmd"]
        command = [
            executable,
            str(find_uproject(workspace)),
            "-run=pythonscript",
            f"-script={script_arg}",
            "-unattended",
            "-nop4",
            "-nosplash",
            "-stdout",
            "-FullStdOutLogOutput",
            *mode_args(mode),
        ]
    env = dict(**__import__("os").environ)
    env["AIUE_REQUEST_PATH"] = str(request_path)
    env["AIUE_RESPONSE_PATH"] = str(response_path)
    env["AIUE_PROJECT_ROOT"] = str(project_root)
    env["AIUE_HOST_KEY"] = str(workspace.get("host_key") or "")
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if not response_path.exists():
        return {
            "success": False,
            "result": {},
            "warnings": [],
            "errors": [
                f"unreal_command_failed_exit_{completed.returncode}",
                completed.stderr or completed.stdout or "Unreal command produced no response file",
            ],
            "invocation": {
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "command": command,
            },
        }
    payload = json.loads(response_path.read_text(encoding="utf-8-sig"))
    payload["invocation"] = {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "command": command,
    }
    if completed.returncode != 0 and payload.get("success", True):
        payload["success"] = False
        payload.setdefault("errors", []).append(f"unreal_command_failed_exit_{completed.returncode}")
    return payload


def probe(workspace_config: str, mode: str, run_id: str | None, project_root: str | None = None, host_key: str | None = None) -> int:
    workspace = load_workspace(workspace_config, project_root_override=project_root, host_key=host_key)
    add_aiue_paths(workspace)

    from aiue_core.policy import derive_capture_policy
    from aiue_core.report_writer import make_compatibility_block, with_report_envelope

    resolved_mode = mode or workspace["probe"].get("default_mode") or "cmd_nullrhi"
    run_token = run_id or f"bootstrap_probe_{uuid.uuid4().hex[:8]}"
    capability_root = Path(workspace["paths"]["capability_probe_root"]).expanduser().resolve()
    run_root = capability_root / run_token
    capabilities_path = run_root / "ue_capabilities.json"
    probe_report_path = run_root / "aiue_probe_report.json"
    api_matrix_path = run_root / "api_matrix.json"
    probe_index_path = capability_root / "latest_probe_index.json"
    native_runtime_report_path = Path(workspace["paths"]["unreal_project_root"]).expanduser().resolve() / "Saved" / "pmx_pipeline" / "native_runtime_activation_report.json"
    plugin_root = Path(workspace["paths"]["unreal_project_root"]).expanduser().resolve() / "Plugins" / "AiUEPmxRuntime"

    entries = build_capability_entries(workspace, resolved_mode)
    preferred_capture_mode = workspace["probe"].get("preferred_capture_mode", "editor_rendered")
    policy_payload = with_report_envelope(
        derive_capture_policy(
            {"run_id": run_token, "capabilities": entries, "capture_finalize_wait_seconds": workspace["probe"].get("capture_finalize_wait_seconds", 8)},
            None,
            preferred_capture_mode,
        ),
        "aiue_capture_policy",
        workflow_pack="core",
        compatibility=make_compatibility_block(
            "aiue_capture_policy",
            notes=["derived_by_bootstrap_host_bridge"],
        ),
    )
    capabilities_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "run_id": run_token,
            "preferred_capture_mode": preferred_capture_mode,
            "recommended_capture_mode": policy_payload["recommended_mode"],
            "capture_policy": policy_payload,
            "capabilities": entries,
        },
        "aiue_capabilities",
        workflow_pack="core",
        compatibility=make_compatibility_block(
            "aiue_capabilities",
            notes=["bootstrap_host_bridge_inferred_live_capabilities"],
        ),
    )
    api_matrix_payload = {
        "generated_at_utc": now_utc(),
        "run_id": run_token,
        "entries": [
            {
                "capability_id": entry["capability_id"],
                "mode": entry["mode"],
                "present": entry["present"],
                "callable": entry["callable"],
                "reliable": entry["reliable"],
            }
            for entry in entries
        ],
    }
    probe_report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "run_id": run_token,
            "workspace_config_path": workspace["config_path"],
            "mode": resolved_mode,
            "capabilities_path": str(capabilities_path),
            "probe_report_path": str(probe_report_path),
            "api_matrix_path": str(api_matrix_path),
            "capture_policy_path": str(run_root / "recommended_capture_policy.json"),
            "latest_aiue_capture_lab_report": None,
            "counts": compute_counts(entries),
            "warnings": ["probe results are inferred by the bootstrap host bridge, not by a live Unreal probe"],
            "errors": [],
        },
        "aiue_probe_report",
        workflow_pack="core",
        compatibility=make_compatibility_block(
            "aiue_probe_report",
            notes=["bootstrap_host_bridge_probe"],
        ),
    )

    write_json(capabilities_path, capabilities_payload)
    write_json(run_root / "recommended_capture_policy.json", policy_payload)
    write_json(api_matrix_path, api_matrix_payload)
    write_json(probe_report_path, probe_report_payload)
    write_json(
        native_runtime_report_path,
        {
            "generated_at_utc": now_utc(),
            "project_root": workspace["paths"]["unreal_project_root"],
            "plugin_root": str(plugin_root.resolve()),
            "source_root": str((plugin_root / "Source" / "AiUEPmxRuntime").resolve()),
            "native_runtime_source_present": any(entry["capability_id"] == "native_runtime_component" and entry["present"] for entry in entries),
            "native_runtime_binary_present": any(entry["capability_id"] == "native_runtime_component" and entry["reliable"] for entry in entries),
            "component_class": "PMXCharacterEquipmentComponent",
            "blueprint_library_class": "PMXEquipmentBlueprintLibrary",
            "host_key": workspace.get("host_key") or "",
        },
    )
    write_json(
        probe_index_path,
        {
            "generated_at_utc": now_utc(),
            "run_id": run_token,
            "capabilities_path": str(capabilities_path),
            "probe_report_path": str(probe_report_path),
            "api_matrix_path": str(api_matrix_path),
            "capture_policy_path": str(run_root / "recommended_capture_policy.json"),
        },
    )

    latest_map = {
        capability_root / "latest_capabilities.json": capabilities_path,
        capability_root / "latest_probe_report.json": probe_report_path,
        capability_root / "latest_api_matrix.json": api_matrix_path,
        capability_root / "latest_recommended_capture_policy.json": run_root / "recommended_capture_policy.json",
    }
    for latest_path, source_path in latest_map.items():
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, latest_path)

    print(json.dumps({"status": "pass", "run_id": run_token, "capabilities_path": str(capabilities_path)}, ensure_ascii=False))
    return 0


def dry_run_import_result(params: dict, workspace: dict) -> dict:
    manifest_path = Path(params["manifest"]).expanduser().resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    output_fbx = resolve_manifest_artifact(manifest_path, manifest.get("output_fbx"))
    textures_dir = output_fbx.parent / "textures"
    texture_count = len([path for path in textures_dir.iterdir() if path.is_file()]) if textures_dir.exists() else 0
    return {
        "manifest_path": str(manifest_path),
        "source_file": manifest.get("source_file"),
        "sample_id": manifest.get("sample_id"),
        "output_fbx": str(output_fbx) if output_fbx else manifest.get("output_fbx"),
        "original_output_fbx": manifest.get("output_fbx"),
        "asset_root": params.get("asset_root") or workspace["paths"]["asset_root"],
        "mode": "dry_run",
        "texture_count": texture_count,
        "warnings": ["dry_run_only_no_assets_imported"],
        "errors": [],
    }


def run_command(
    workspace_config: str,
    mode: str,
    command: str,
    output_path: str | None,
    params_json: str | None,
    dry_run: bool,
    project_root: str | None = None,
    host_key: str | None = None,
) -> int:
    workspace = load_workspace(workspace_config, project_root_override=project_root, host_key=host_key)
    add_aiue_paths(workspace)

    from aiue_core.report_writer import make_compatibility_block, with_report_envelope

    run_id = uuid.uuid4().hex[:12]
    params = json.loads(params_json) if params_json else {}

    effective_mode = mode
    if command in {"import-package", "load-level", "spawn-host", "capture-frame", "run-scene-sweep", "inspect-stage-anchors", "ensure-stage-anchors", "inspect-host-visual", "stage-capture", "action-preview", "animation-preview", "retarget-preflight", "retarget-bootstrap", "retarget-author-chains"} and not dry_run and mode != "editor_rendered":
        effective_mode = "editor_rendered"

    if command == "run-scene-sweep":
        result = run_scene_sweep(workspace, effective_mode, params)
        host_payload = {
            "success": not result.get("errors"),
            "result": result,
            "warnings": list(result.get("warnings", [])),
            "errors": list(result.get("errors", [])),
        }
    elif command in {"inspect-host", "inspect-host-visual", "list-assets", "debug-physics-api", "build-equipment-registry", "load-level", "spawn-host", "capture-frame", "stage-capture", "inspect-stage-anchors", "ensure-stage-anchors", "action-preview", "animation-preview", "retarget-preflight", "retarget-bootstrap", "retarget-author-chains"}:
        request = {"command": command, "asset_root": workspace["paths"]["asset_root"], **params}
        host_payload = run_unreal_python_request(workspace, effective_mode, request)
    elif command == "import-package" and dry_run:
        request = {"command": command, "asset_root": workspace["paths"]["asset_root"], "dry_run": True, **params}
        host_payload = {
            "success": True,
            "result": dry_run_import_result(request, workspace),
            "warnings": ["handled_by_bootstrap_dry_run"],
            "errors": [],
        }
    elif command == "import-package":
        request = {"command": command, "asset_root": workspace["paths"]["asset_root"], "dry_run": False, **params}
        host_payload = run_unreal_python_request(workspace, effective_mode, request)
        if effective_mode != mode:
            host_payload.setdefault("warnings", []).append(f"requested_mode_{mode}_promoted_to_{effective_mode}_for_live_import")
    else:
        host_payload = {
            "success": False,
            "result": {},
            "warnings": [],
            "errors": [f"unsupported_command:{command}"],
        }
    if effective_mode != mode and command != "import-package":
        host_payload.setdefault("warnings", []).append(f"requested_mode_{mode}_promoted_to_{effective_mode}_for_live_scene_command")

    status = "pass" if host_payload.get("success") else "fail"
    if dry_run and command == "import-package" and host_payload.get("success"):
        status = "dry_run"
    payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "run_id": run_id,
            "command": command,
            "mode": effective_mode,
            "status": status,
            "success": bool(host_payload.get("success")),
            "warnings": list(host_payload.get("warnings", [])),
            "errors": list(host_payload.get("errors", [])),
            "result": dict(host_payload.get("result") or {}),
            "host_key": workspace.get("host_key") or "",
            "project_root": workspace["paths"]["unreal_project_root"],
        },
        "aiue_action_result",
        workflow_pack="core",
        compatibility=make_compatibility_block(
            "aiue_action_result",
            notes=["bootstrap_host_bridge_live_probe_commands"],
        ),
    )
    if output_path:
        write_json(Path(output_path).expanduser().resolve(), payload)
    print(json.dumps({"status": payload["status"], "command": command}, ensure_ascii=False))
    return 0 if payload["success"] else 1


def load_params(params_json: str | None, params_path: str | None) -> dict:
    if params_path:
        path = Path(params_path).expanduser().resolve()
        return json.loads(path.read_text(encoding="utf-8-sig"))
    if params_json:
        return json.loads(params_json)
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap host bridge for local AiUE integration.")
    subparsers = parser.add_subparsers(dest="operation", required=True)

    probe_parser = subparsers.add_parser("probe")
    probe_parser.add_argument("--workspace-config", required=True)
    probe_parser.add_argument("--mode", default="cmd_nullrhi")
    probe_parser.add_argument("--run-id")
    probe_parser.add_argument("--project-root")
    probe_parser.add_argument("--host-key")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--workspace-config", required=True)
    run_parser.add_argument("--mode", default="cmd_nullrhi")
    run_parser.add_argument("--command", required=True)
    run_parser.add_argument("--output-path")
    run_parser.add_argument("--params-json")
    run_parser.add_argument("--params-path")
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--project-root")
    run_parser.add_argument("--host-key")

    args = parser.parse_args()
    if args.operation == "probe":
        return probe(args.workspace_config, args.mode, args.run_id, project_root=args.project_root, host_key=args.host_key)
    params_json = json.dumps(load_params(args.params_json, args.params_path), ensure_ascii=False) if (args.params_json or args.params_path) else None
    return run_command(
        args.workspace_config,
        args.mode,
        args.command,
        args.output_path,
        params_json,
        args.dry_run,
        project_root=args.project_root,
        host_key=args.host_key,
    )


if __name__ == "__main__":
    raise SystemExit(main())
