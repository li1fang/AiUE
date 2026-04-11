from __future__ import annotations

from .common import *
from .capture_stage import *
from .capture_visual import *

# Command shim: stage and visual helpers live in capture_stage/capture_visual.
def capture_frame(request: dict) -> dict:
    raw_output_path = request.get("output_path")
    output_path = Path(raw_output_path).expanduser() if raw_output_path else None
    if output_path is None:
        capture_root = Path(request.get("capture_root") or (Path(unreal.Paths.project_saved_dir()) / "Screenshots" / "AiUE"))
        shot_name = sanitize_segment(str(request.get("shot_name") or request.get("actor_label") or request.get("target_actor_label") or "capture"))
        output_path = capture_root / f"{shot_name}.png"
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    warnings = []
    camera_mode = str(request.get("camera_mode") or "auto_framing")
    level_path = request.get("level_path") or request.get("scene_level_path")
    if level_path:
        load_result = load_level({"level_path": level_path})
        warnings.extend(load_result.get("warnings") or [])
        if load_result.get("errors"):
            return {
                "warnings": warnings,
                "errors": list(load_result.get("errors") or []),
            }

    spawn_anchor_actor_label = str(request.get("spawn_anchor_actor_label") or "")
    camera_anchor_actor_label = str(request.get("camera_anchor_actor_label") or "")
    expected_spawn_location = request.get("expected_spawn_location")
    expected_spawn_rotation = request.get("expected_spawn_rotation")
    resolved_stage_anchors = {}
    spawn_anchor = None
    camera_anchor = None
    if camera_mode == "anchor_actor":
        wait_for_actor_labels([spawn_anchor_actor_label, camera_anchor_actor_label])
        spawn_anchor, spawn_anchor_record = resolve_stage_anchor_actor(spawn_anchor_actor_label, "TargetPoint", "spawn")
        camera_anchor, camera_anchor_record = resolve_stage_anchor_actor(camera_anchor_actor_label, "CineCameraActor", "camera")
        resolved_stage_anchors = {
            "spawn": spawn_anchor_record,
            "camera": camera_anchor_record,
        }
        anchor_errors = list(spawn_anchor_record.get("errors") or []) + list(camera_anchor_record.get("errors") or [])
        if anchor_errors:
            return {
                "camera_mode": camera_mode,
                "camera_source": "anchor_actor",
                "spawn_anchor_actor_label": spawn_anchor_actor_label,
                "camera_anchor_actor_label": camera_anchor_actor_label,
                "resolved_stage_anchors": resolved_stage_anchors,
                "warnings": warnings,
                "errors": anchor_errors,
            }

    actor_label = request.get("actor_label") or request.get("target_actor_label")
    actor_path = request.get("actor_path") or request.get("target_actor_path")
    target_actor = find_actor_by_label_or_path(actor_label=actor_label, actor_path=actor_path)
    actor_subsystem = editor_actor_subsystem()
    spawned_host = None
    host_asset_path = None
    host_record = None
    if not target_actor:
        try:
            host_asset_path, host_record, host_warnings = resolve_host_blueprint_asset_path(request)
            warnings.extend(host_warnings)
            blueprint_asset = unreal.EditorAssetLibrary.load_asset(object_path_from_asset_path(host_asset_path))
            if not blueprint_asset:
                return {
                    "warnings": warnings,
                    "errors": [f"host_blueprint_load_failed:{host_asset_path}"],
                }
            if camera_mode == "anchor_actor" and spawn_anchor:
                if expected_spawn_location and expected_spawn_rotation:
                    spawn_location = vector_from_request(expected_spawn_location)
                    spawn_rotation = rotator_from_request(expected_spawn_rotation)
                else:
                    spawn_location = spawn_anchor.get_actor_location()
                    spawn_rotation = spawn_anchor.get_actor_rotation()
            else:
                spawn_location = vector_from_request(request.get("location"), unreal.Vector(0.0, 0.0, 120.0))
                spawn_rotation = rotator_from_request(request.get("rotation"), make_rotator(0.0, 180.0, 0.0))
            spawned_host = actor_subsystem.spawn_actor_from_object(blueprint_asset, spawn_location, spawn_rotation, True)
            if not spawned_host:
                return {
                    "warnings": warnings,
                    "errors": ["target_actor_not_found", f"failed_to_spawn_host_for_capture:{host_asset_path}"],
                }
            spawned_host.set_actor_label(str(actor_label or asset_name_from_path(host_asset_path)))
            try:
                spawned_host.apply_configured_loadout()
            except Exception as exc:
                warnings.append(f"apply_configured_loadout_failed:{exc}")
            override_bindings = list(request.get("slot_binding_overrides") or [])
            if override_bindings and hasattr(unreal, "PMXEquipmentBlueprintLibrary"):
                try:
                    unreal.PMXEquipmentBlueprintLibrary.apply_slot_bindings(
                        spawned_host,
                        runtime_slot_binding_entries_from_request(override_bindings),
                    )
                except Exception as exc:
                    warnings.append(f"apply_slot_binding_overrides_failed:{exc}")
            target_actor = spawned_host
            warnings.append("target_actor_not_found_spawned_host_for_capture")
        except Exception:
            return {
                "warnings": warnings,
                "errors": ["target_actor_not_found"],
            }

    if camera_mode == "anchor_actor" and spawn_anchor and target_actor:
        if expected_spawn_location and expected_spawn_rotation:
            spawn_location = vector_from_request(expected_spawn_location)
            spawn_rotation = rotator_from_request(expected_spawn_rotation)
        else:
            spawn_location = spawn_anchor.get_actor_location()
            spawn_rotation = spawn_anchor.get_actor_rotation()
        try:
            target_actor.set_actor_location(spawn_location, False, False)
        except Exception:
            target_actor.set_actor_location(spawn_location, False)
        try:
            target_actor.set_actor_rotation(spawn_rotation, False)
        except Exception:
            target_actor.set_actor_rotation(spawn_rotation)

    if camera_mode == "anchor_actor":
        camera_plan = build_anchor_camera_plan(camera_anchor, target_actor, request)
    elif camera_mode == "explicit_pose":
        explicit_camera_location = vector_from_request(request.get("camera_location"))
        explicit_camera_rotation = rotator_from_request(request.get("camera_rotation"))
        origin, extent = actor_bounds(target_actor)
        camera_plan = {
            "camera_source": str(request.get("camera_source") or "explicit_pose"),
            "camera_location": serialize_vector(explicit_camera_location),
            "camera_rotation": serialize_rotator(explicit_camera_rotation),
            "target_location": serialize_vector(origin + unreal.Vector(0.0, 0.0, max(extent.z * 0.45, 65.0))),
            "bounds_origin": serialize_vector(origin),
            "bounds_extent": serialize_vector(extent),
        }
    else:
        camera_plan = build_capture_camera_for_actor(target_actor, request)
    camera_location = vector_from_request(camera_plan["camera_location"])
    camera_rotation = rotator_from_request(camera_plan["camera_rotation"])
    width = int(request.get("width") or request.get("capture_width") or 1280)
    height = int(request.get("height") or request.get("capture_height") or 720)
    delay_seconds = float(request.get("delay") or request.get("capture_delay_seconds") or 0.2)
    timeout_seconds = float(request.get("timeout_seconds") or 30.0)
    stability_window_seconds = float(request.get("file_stability_window_seconds") or 0.75)
    poll_interval_seconds = float(request.get("poll_interval_seconds") or 0.2)
    capture_hdr = bool(request.get("capture_hdr", False))
    force_game_view = bool(request.get("force_game_view", True))
    force_automation_capture = bool(request.get("force_automation_capture", False))
    capture_profile = str(request.get("capture_profile") or "")
    level_editor = level_editor_subsystem()
    temp_camera = None
    capture_camera = None
    niagara_capture_prep = prime_niagara_for_capture(target_actor, request)
    warnings.extend(list(niagara_capture_prep.get("warnings") or []))
    warnings.extend(list(niagara_capture_prep.get("errors") or []))
    try:
        temp_camera = actor_subsystem.spawn_actor_from_class(unreal.CameraActor, camera_location, camera_rotation, True)
        if not temp_camera:
            return {
                "warnings": warnings,
                "errors": ["temporary_camera_spawn_failed"],
            }
        temp_camera.set_actor_label(f"AIUE_CaptureCamera_{sanitize_segment(target_actor.get_actor_label())}")
        capture_camera = temp_camera

        subject_visibility = evaluate_subject_visibility(target_actor, capture_camera, camera_location, camera_rotation, width, height)
        if not subject_visibility.get("visible"):
            warnings.append("subject_not_visible_in_camera_plan")
        try:
            level_editor.pilot_level_actor(capture_camera)
        except Exception as exc:
            warnings.append(f"pilot_level_actor_failed:{exc}")
        try:
            if hasattr(level_editor, "set_allows_cinematic_control"):
                level_editor.set_allows_cinematic_control(True)
        except Exception:
            pass
        try:
            if hasattr(level_editor, "set_exact_camera_view"):
                level_editor.set_exact_camera_view(True)
        except Exception:
            pass
        actual_output_path = None
        task_done = False
        screenshot_exists = False
        capture_backend = ""
        resolved_scene_capture_source = ""
        if not force_automation_capture:
            render_target_capture = capture_to_render_target(
                capture_camera,
                width,
                height,
                output_path,
                capture_hdr,
                delay_seconds,
                timeout_seconds,
                stability_window_seconds,
                poll_interval_seconds,
                str(request.get("scene_capture_source") or ""),
                int(request.get("scene_capture_warmup_count") or 2),
                float(request.get("scene_capture_warmup_delay_seconds") or 0.05),
                capture_profile,
                list(request.get("_show_only_components") or []),
            )
            warnings.extend(render_target_capture.get("warnings") or [])
            actual_output_path = Path(render_target_capture["output_path"]).resolve() if render_target_capture.get("output_path") else None
            task_done = bool(render_target_capture.get("task_done"))
            screenshot_exists = bool(render_target_capture.get("output_exists"))
            capture_backend = str(render_target_capture.get("capture_backend") or "")
            resolved_scene_capture_source = str(render_target_capture.get("scene_capture_source") or "")
            if (
                screenshot_exists
                and int(render_target_capture.get("file_size_bytes") or 0) < 400000
                and capture_profile.lower() != "qa_mask_skeletal_only"
            ):
                warnings.append("render_target_capture_too_small_fallback_to_automation")
                screenshot_exists = False
        else:
            warnings.append("render_target_capture_skipped_by_request")

        if not screenshot_exists:
            unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera_location, camera_rotation)
            level_editor.editor_set_viewport_realtime(True)
            try:
                level_editor.editor_set_game_view(True)
            except Exception:
                pass
            level_editor.editor_invalidate_viewports()
            task = unreal.AutomationLibrary.take_high_res_screenshot(
                width,
                height,
                str(output_path),
                capture_camera,
                False,
                capture_hdr,
                unreal.ComparisonTolerance.LOW,
                "AiUE capture",
                delay_seconds,
                force_game_view,
            )
            actual_output_path, task_done = wait_for_screenshot(task, output_path, timeout_seconds, stability_window_seconds, poll_interval_seconds)
            if actual_output_path and actual_output_path != output_path:
                shutil.copyfile(actual_output_path, output_path)
                actual_output_path = output_path
            screenshot_exists = bool(actual_output_path and actual_output_path.exists())
            capture_backend = capture_backend or "automation_high_res_screenshot"
        return {
            "target_actor_label": target_actor.get_actor_label(),
            "target_actor_path": target_actor.get_path_name(),
            "host_blueprint_asset_path": host_asset_path,
            "host_record": host_record,
            "target_render_components": summarize_render_components(target_actor),
            "camera_mode": camera_mode,
            "camera_source": str(camera_plan.get("camera_source") or camera_mode),
            "spawn_anchor_actor_label": spawn_anchor_actor_label,
            "camera_anchor_actor_label": camera_anchor_actor_label,
            "resolved_stage_anchors": resolved_stage_anchors,
            "output_path": str(actual_output_path or output_path),
            "requested_output_path": str(output_path),
            "output_exists": screenshot_exists,
            "file_size_bytes": actual_output_path.stat().st_size if actual_output_path and actual_output_path.exists() else 0,
            "width": width,
            "height": height,
            "delay_seconds": delay_seconds,
            "camera_plan": camera_plan,
            "capture_backend": capture_backend,
            "scene_capture_source": resolved_scene_capture_source,
            "capture_profile": capture_profile,
            "niagara_capture_prep": niagara_capture_prep,
            "subject_visibility": subject_visibility,
            "subject_visible": bool(subject_visibility.get("visible")),
            "task_done": task_done,
            "warnings": warnings if screenshot_exists else warnings + ["screenshot_output_missing_after_task_completion"],
            "errors": [] if screenshot_exists else ["capture_frame_failed"],
        }
    finally:
        try:
            if hasattr(level_editor, "eject_pilot_level_actor"):
                level_editor.eject_pilot_level_actor()
        except Exception:
            pass
        try:
            if hasattr(level_editor, "set_exact_camera_view"):
                level_editor.set_exact_camera_view(False)
        except Exception:
            pass
        if temp_camera:
            try:
                actor_subsystem.destroy_actor(temp_camera)
            except Exception:
                pass
        if spawned_host:
            try:
                actor_subsystem.destroy_actor(spawned_host)
            except Exception:
                pass



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


__all__ = [
    "load_level",
    "spawn_host",
    "inspect_stage_anchors",
    "ensure_stage_anchors",
    "capture_frame",
    "capture_frame_for_actor_object",
    "build_visual_proof_shots",
    "explicit_shot_plans_from_request",
    "filtered_visual_shots",
    "capture_visual_shot",
    "run_scene_sweep",
]




