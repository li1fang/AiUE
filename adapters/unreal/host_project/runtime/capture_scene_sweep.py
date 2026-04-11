from __future__ import annotations

from .common import *
from .capture_stage import *
from .capture_frame_command import capture_frame


def run_scene_sweep(request: dict) -> dict:
    summary_path = request.get("summary")
    suite_output_path = Path(request.get("suite_output") or "").expanduser() if request.get("suite_output") else None
    capture_manifest_path = Path(request.get("capture_manifest_output") or "").expanduser() if request.get("capture_manifest_output") else None
    capture_root = Path(request.get("capture_root") or (Path(unreal.Paths.project_saved_dir()) / "pmx_pipeline" / "captures")).expanduser().resolve()
    capture_root.mkdir(parents=True, exist_ok=True)
    suite_output_path = suite_output_path.resolve() if suite_output_path else capture_root / "ue_animation_suite_summary.json"
    capture_manifest_path = capture_manifest_path.resolve() if capture_manifest_path else capture_root / "ue_capture_manifest.json"

    scenario_names = list(request.get("scenario_names") or ["idle_2s", "walk_forward_2s", "run_forward_2s", "jump_land_1cycle"])
    camera_mode = str(request.get("camera_mode") or "auto_framing")
    package_ids = [request.get("package_id")] if request.get("package_id") else []
    if not package_ids:
        report_path = resolve_equipment_report_path(request)
        if report_path and report_path.exists():
            report_payload = read_json(report_path)
            package_ids = [
                entry.get("character_package_id")
                for entry in (report_payload.get("host_blueprints") or [])
                if entry.get("has_runtime_weapon_mesh_component")
            ]

    package_results = []
    capture_entries = []
    current_level_path = None
    if request.get("level_lifecycle") == "reuse_level" or len(package_ids) <= 1:
        requested_level = request.get("level_path") or request.get("scene_level_path")
        if requested_level:
            load_result = load_level({"level_path": requested_level})
            current_level_path = load_result.get("current_level_path")
            if load_result.get("errors"):
                return {
                    "summary_path": summary_path,
                    "suite_output": str(suite_output_path),
                    "capture_manifest_output": str(capture_manifest_path),
                    "capture_root": str(capture_root),
                    "counts": {
                        "requested_packages": len(package_ids),
                        "completed_packages": 0,
                        "failed_packages": len(package_ids),
                        "capture_entries": 0,
                        "valid_images": 0,
                        "captured_before_report": 0,
                        "captured_after_report_before_exit": 0,
                        "captured_after_exit": 0,
                    },
                    "warnings": list(load_result.get("warnings") or []),
                    "errors": list(load_result.get("errors") or []),
                }

    for package_index, package_id in enumerate(package_ids, start=1):
        suite_record = load_suite_summary_record(summary_path, package_id)
        host_request = {
            "package_id": package_id,
            "sample_id": suite_record.get("sample_id"),
            "summary": summary_path,
            "report_path": str(resolve_equipment_report_path(request)) if resolve_equipment_report_path(request) else None,
            "runtime_ready_only": True,
        }
        try:
            host_asset_path, host_record, host_warnings = resolve_host_blueprint_asset_path(host_request)
        except Exception as exc:
            package_result = {
                "package_id": package_id,
                "sample_id": suite_record.get("sample_id"),
                "host_blueprint_asset_path": None,
                "status": "fail",
                "warnings": [],
                "errors": [str(exc)],
                "scenario_results": [],
            }
            package_results.append(package_result)
            continue

        scenario_results = []
        package_warnings = list(host_warnings)
        for scenario_index, scenario_name in enumerate(scenario_names, start=1):
            if request.get("level_lifecycle") == "reload_level_per_run":
                requested_level = request.get("level_path") or request.get("scene_level_path")
                if requested_level:
                    level_result = load_level({"level_path": requested_level})
                    current_level_path = level_result.get("current_level_path")
                    package_warnings.extend(level_result.get("warnings") or [])
                    if level_result.get("errors"):
                        scenario_result = {
                            "scenario": scenario_name,
                            "status": "fail",
                            "capture_status": "capture_failed",
                            "image_path": None,
                            "warnings": list(level_result.get("warnings") or []),
                            "errors": list(level_result.get("errors") or []),
                        }
                        scenario_results.append(scenario_result)
                        capture_entries.append(
                            {
                                "sample_id": suite_record.get("sample_id") or host_record.get("sample_id") if host_record else None,
                                "package_id": package_id,
                                "scenario": scenario_name,
                                "image_path": None,
                                "capture_status": "capture_failed",
                                "reference_dir": str(Path(summary_path).expanduser().resolve().parent) if summary_path else None,
                                "warnings": list(level_result.get("warnings") or []),
                                "errors": list(level_result.get("errors") or []),
                            }
                        )
                        continue

            overrides = scenario_capture_overrides(scenario_index, scenario_name, request)
            scenario_camera_mode = str(overrides.get("camera_mode") or camera_mode)
            package_capture_root = capture_root / sanitize_segment(package_id or f"package_{package_index:03d}")
            package_capture_root.mkdir(parents=True, exist_ok=True)
            image_path = package_capture_root / f"{scenario_index:02d}_{sanitize_segment(scenario_name)}.png"
            capture_request = {
                "summary": summary_path,
                "report_path": str(resolve_equipment_report_path(request)) if resolve_equipment_report_path(request) else None,
                "package_id": package_id,
                "sample_id": (suite_record.get("sample_id") or (host_record or {}).get("sample_id")),
                "host_blueprint_asset_path": host_asset_path,
                "runtime_ready_only": True,
                "level_path": None if request.get("level_lifecycle") == "reuse_level" else (request.get("level_path") or request.get("scene_level_path")),
                "actor_label": f"AIUE_{sanitize_segment(package_id)}_{sanitize_segment(scenario_name)}",
                "output_path": str(image_path),
                "width": int(request.get("capture_width") or request.get("width") or 1280),
                "height": int(request.get("capture_height") or request.get("height") or 720),
                "capture_delay_seconds": float(request.get("capture_delay_seconds") or 0.2),
                "timeout_seconds": float(request.get("settle_timeout_seconds") or request.get("timeout_seconds") or 20.0),
                "file_stability_window_seconds": float(request.get("file_stability_window_seconds") or 0.75),
                "poll_interval_seconds": float(request.get("viewport_pump_interval_seconds") or request.get("poll_interval_seconds") or 0.2),
                "camera_mode": scenario_camera_mode,
            }
            if scenario_camera_mode == "anchor_actor":
                capture_request["spawn_anchor_actor_label"] = str(overrides.get("spawn_anchor_actor_label") or request.get("spawn_anchor_actor_label") or "")
                capture_request["camera_anchor_actor_label"] = str(overrides.get("camera_anchor_actor_label") or request.get("camera_anchor_actor_label") or "")
                if overrides.get("expected_spawn_location") is not None:
                    capture_request["expected_spawn_location"] = overrides.get("expected_spawn_location")
                if overrides.get("expected_spawn_rotation") is not None:
                    capture_request["expected_spawn_rotation"] = overrides.get("expected_spawn_rotation")
                if overrides.get("expected_camera_location") is not None:
                    capture_request["expected_camera_location"] = overrides.get("expected_camera_location")
                if overrides.get("expected_camera_rotation") is not None:
                    capture_request["expected_camera_rotation"] = overrides.get("expected_camera_rotation")
            else:
                capture_request["location"] = overrides["location"]
                capture_request["rotation"] = overrides["rotation"]
                capture_request["camera_distance"] = overrides["camera_distance"]
                capture_request["camera_lateral_offset"] = overrides["camera_lateral_offset"]
                capture_request["camera_height"] = overrides["camera_height"]
                capture_request["target_height_offset"] = overrides["target_height_offset"] or float(request.get("target_height_offset") or 0.0)
            capture_result = capture_frame(capture_request)
            if not capture_result.get("output_exists") and capture_result.get("output_path"):
                finalized_output_path, _ = wait_for_screenshot(
                    None,
                    Path(capture_result["output_path"]),
                    float(request.get("quit_barrier_seconds") or 2.0) + float(request.get("file_stability_window_seconds") or 0.75) + 1.0,
                    float(request.get("file_stability_window_seconds") or 0.75),
                    float(request.get("viewport_pump_interval_seconds") or 0.2),
                )
                if finalized_output_path and finalized_output_path.exists():
                    capture_result["output_path"] = str(finalized_output_path)
                    capture_result["output_exists"] = True
                    capture_result["file_size_bytes"] = finalized_output_path.stat().st_size
                    capture_result["task_done"] = True
                    capture_result["warnings"] = [
                        warning
                        for warning in (capture_result.get("warnings") or [])
                        if warning != "screenshot_output_missing_after_task_completion"
                    ]
                    capture_result["errors"] = []
            capture_success = not capture_result.get("errors") and bool(capture_result.get("output_exists"))
            capture_status = "captured_before_report" if capture_success else "capture_failed"
            scenario_result = {
                "scenario": scenario_name,
                "status": "pass" if capture_success else "fail",
                "capture_status": capture_status,
                "image_path": capture_result.get("output_path"),
                "camera_source": capture_result.get("camera_source") or scenario_camera_mode,
                "capture_backend": capture_result.get("capture_backend"),
                "spawn_anchor_actor_label": capture_result.get("spawn_anchor_actor_label") or capture_request.get("spawn_anchor_actor_label") or "",
                "camera_anchor_actor_label": capture_result.get("camera_anchor_actor_label") or capture_request.get("camera_anchor_actor_label") or "",
                "subject_visible": bool(capture_result.get("subject_visible")),
                "subject_visibility": dict(capture_result.get("subject_visibility") or {}),
                "target_render_components": list(capture_result.get("target_render_components") or []),
                "warnings": list(capture_result.get("warnings") or []),
                "errors": list(capture_result.get("errors") or []),
                "camera_plan": capture_result.get("camera_plan"),
            }
            scenario_results.append(scenario_result)
            capture_entries.append(
                {
                    "sample_id": suite_record.get("sample_id") or (host_record or {}).get("sample_id"),
                    "package_id": package_id,
                    "scenario": scenario_name,
                    "image_path": capture_result.get("output_path"),
                    "capture_status": capture_status,
                    "camera_source": scenario_result["camera_source"],
                    "spawn_anchor_actor_label": scenario_result["spawn_anchor_actor_label"],
                    "camera_anchor_actor_label": scenario_result["camera_anchor_actor_label"],
                    "subject_visible": scenario_result["subject_visible"],
                    "reference_dir": str(package_capture_root),
                    "warnings": list(capture_result.get("warnings") or []),
                    "errors": list(capture_result.get("errors") or []),
                    "host_blueprint_asset_path": host_asset_path,
                }
            )

        package_failed = any(result.get("status") != "pass" for result in scenario_results)
        package_results.append(
            {
                "package_id": package_id,
                "sample_id": suite_record.get("sample_id") or (host_record or {}).get("sample_id"),
                "host_blueprint_asset_path": host_asset_path,
                "status": "fail" if package_failed else "pass",
                "warnings": package_warnings,
                "errors": [] if not package_failed else ["one_or_more_scenarios_failed"],
                "scenario_results": scenario_results,
            }
        )

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
            "validation_mode": request.get("validation_mode"),
            "camera_lifecycle": request.get("camera_lifecycle"),
            "camera_mode": camera_mode,
            "level_lifecycle": request.get("level_lifecycle"),
            "scenario_scheduling": request.get("scenario_scheduling"),
            "completion_strategy": request.get("completion_strategy"),
        },
    }
    write_json(capture_manifest_path, manifest_payload)
    write_json(suite_output_path, summary_payload)

    valid_images = sum(1 for entry in capture_entries if entry.get("capture_status") == "captured_before_report" and entry.get("image_path"))
    failed_packages = sum(1 for item in package_results if item.get("status") != "pass")
    result = {
        "summary_path": summary_path,
        "suite_output": str(suite_output_path),
        "capture_manifest_output": str(capture_manifest_path),
        "capture_root": str(capture_root),
        "level_path": request.get("level_path") or request.get("scene_level_path"),
        "current_level_path": current_level_path or get_current_level_path(),
        "scenario_names": scenario_names,
        "package_results": package_results,
        "counts": {
            "requested_packages": len(package_ids),
            "completed_packages": len(package_results) - failed_packages,
            "failed_packages": failed_packages,
            "capture_entries": len(capture_entries),
            "valid_images": valid_images,
            "captured_before_report": valid_images,
            "captured_after_report_before_exit": 0,
            "captured_after_exit": 0,
            "late_captures": 0,
        },
        "warnings": [],
        "errors": [],
    }
    if not package_ids:
        result["warnings"].append("no_package_ids_resolved_for_scene_sweep")
    if failed_packages:
        result["errors"].append("scene_sweep_failed_packages_present")
    return result


__all__ = ["run_scene_sweep"]
