from __future__ import annotations

from .common import *

def prime_niagara_for_capture(actor, request: dict) -> dict:
    payload = niagara_capture_warmup_payload(None)
    if not actor or not hasattr(unreal, "PMXEquipmentBlueprintLibrary"):
        return payload
    if not bool(request.get("prime_niagara_before_capture", True)):
        payload["warnings"] = ["niagara_capture_priming_disabled"]
        return payload

    slot_names = [
        to_name(slot_name_text(value, default=""))
        for value in list(request.get("niagara_slot_names") or request.get("tracked_slots") or [])
        if str(value)
    ]
    desired_age_seconds = float(request.get("niagara_desired_age_seconds") or 0.35)
    seek_delta_seconds = float(request.get("niagara_seek_delta_seconds") or (1.0 / 30.0))
    advance_step_count = int(request.get("niagara_advance_step_count") or 8)
    advance_step_delta_seconds = float(request.get("niagara_advance_step_delta_seconds") or (1.0 / 60.0))
    flush_world = bool(request.get("niagara_flush_world", True))
    try:
        result = unreal.PMXEquipmentBlueprintLibrary.prime_niagara_for_capture(
            actor,
            slot_names,
            desired_age_seconds,
            seek_delta_seconds,
            advance_step_count,
            advance_step_delta_seconds,
            flush_world,
        )
        return niagara_capture_warmup_payload(result)
    except Exception as exc:
        payload["errors"] = [f"niagara_capture_priming_failed:{exc}"]
        return payload



def capture_frame_for_actor_object(target_actor, request: dict, output_path: Path, host_asset_path: str | None = None, host_record: dict | None = None) -> dict:
    warnings = []
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    actor_subsystem = editor_actor_subsystem()
    camera_mode = str(request.get("camera_mode") or "explicit_pose")
    if camera_mode == "explicit_pose":
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
    level_editor = level_editor_subsystem()
    temp_camera = None
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
        subject_visibility = evaluate_subject_visibility(target_actor, temp_camera, camera_location, camera_rotation, width, height)
        if not subject_visibility.get("visible"):
            warnings.append("subject_not_visible_in_camera_plan")
        try:
            level_editor.pilot_level_actor(temp_camera)
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
                temp_camera,
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
            )
            warnings.extend(render_target_capture.get("warnings") or [])
            actual_output_path = Path(render_target_capture["output_path"]).resolve() if render_target_capture.get("output_path") else None
            task_done = bool(render_target_capture.get("task_done"))
            screenshot_exists = bool(render_target_capture.get("output_exists"))
            capture_backend = str(render_target_capture.get("capture_backend") or "")
            resolved_scene_capture_source = str(render_target_capture.get("scene_capture_source") or "")
            if screenshot_exists and int(render_target_capture.get("file_size_bytes") or 0) < 400000:
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
                temp_camera,
                False,
                capture_hdr,
                unreal.ComparisonTolerance.LOW,
                "AiUE action preview capture",
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


def build_visual_proof_shots(actor, request: dict) -> list[dict]:
    origin, extent = actor_bounds(actor)
    forward = actor.get_actor_forward_vector()
    right = actor.get_actor_right_vector()
    up = unreal.Vector(0.0, 0.0, 1.0)
    distance_scale = max(float(request.get("camera_distance_scale") or 1.0), 0.1)
    height_scale = max(float(request.get("camera_height_scale") or 1.0), 0.1)
    base_distance = max(float(request.get("camera_distance") or 0.0), max(extent.x, extent.y, 90.0) * 2.4 * distance_scale)
    base_height = max(float(request.get("camera_height") or 0.0), max(extent.z * 1.15, 110.0) * height_scale)
    top_height = max(float(request.get("top_camera_height") or 0.0), base_distance * 1.65)
    target_location = origin + unreal.Vector(0.0, 0.0, max(extent.z * 0.6, 90.0))

    shot_specs = [
        {
            "shot_id": "front",
            "camera_id": "front",
            "camera_location": origin - (forward * base_distance) + (up * base_height),
        },
        {
            "shot_id": "side",
            "camera_id": "side",
            "camera_location": origin + (right * (base_distance * 0.95)) + (up * base_height),
        },
        {
            "shot_id": "top",
            "camera_id": "top",
            "camera_location": origin - (forward * (base_distance * 0.25)) + (up * top_height),
        },
    ]
    payload = []
    for item in shot_specs:
        camera_rotation = unreal.MathLibrary.find_look_at_rotation(item["camera_location"], target_location)
        payload.append(
            {
                "shot_id": item["shot_id"],
                "camera_id": item["camera_id"],
                "camera_source": "explicit_pose",
                "camera_location": serialize_vector(item["camera_location"]),
                "camera_rotation": serialize_rotator(camera_rotation),
                "target_location": serialize_vector(target_location),
            }
        )
    return payload


def explicit_shot_plans_from_request(request: dict) -> list[dict]:
    payload = []
    for index, entry in enumerate(list(request.get("shot_plans") or []), start=1):
        shot_id = str(entry.get("shot_id") or entry.get("camera_id") or f"shot_{index:02d}")
        camera_id = str(entry.get("camera_id") or shot_id)
        payload.append(
            {
                "shot_id": shot_id,
                "camera_id": camera_id,
                "camera_source": str(entry.get("camera_source") or "explicit_pose"),
                "camera_location": serialize_vector(vector_from_request(entry.get("camera_location"))),
                "camera_rotation": serialize_rotator(rotator_from_request(entry.get("camera_rotation"))),
                "target_location": dict(entry.get("target_location") or {}),
            }
        )
    return payload


def filtered_visual_shots(actor, request: dict) -> list[dict]:
    requested_order = [str(item) for item in (request.get("shot_order") or ["front", "side"]) if str(item)]
    explicit_plans = explicit_shot_plans_from_request(request)
    source_plans = explicit_plans or build_visual_proof_shots(actor, request)
    available = {item.get("shot_id"): item for item in source_plans}
    payload = []
    for shot_id in requested_order or [str(item.get("shot_id") or "") for item in source_plans]:
        shot = available.get(shot_id)
        if shot:
            payload.append(shot)
    if not payload and explicit_plans:
        return explicit_plans
    return payload


def capture_visual_shot(
    target_actor,
    primary_mesh,
    weapon_mesh,
    shot_plan: dict,
    output_path: Path,
    request: dict,
    fallback_actor=None,
) -> dict:
    actor_subsystem = editor_actor_subsystem()
    width = int(request.get("width") or request.get("capture_width") or 1280)
    height = int(request.get("height") or request.get("capture_height") or 720)
    subject_min_screen_coverage = float(request.get("subject_min_screen_coverage") or 0.015)
    weapon_min_screen_coverage = float(request.get("weapon_min_screen_coverage") or 0.001)
    metric_camera = actor_subsystem.spawn_actor_from_class(
        unreal.CameraActor,
        vector_from_request(shot_plan["camera_location"]),
        rotator_from_request(shot_plan["camera_rotation"]),
        True,
    )
    line_of_sight = {"clear": False, "reason": "metric_camera_spawn_failed"}
    subject_coverage = {"coverage_ratio": 0.0, "reason": "metric_camera_spawn_failed"}
    weapon_coverage = {"coverage_ratio": 0.0, "reason": "metric_camera_spawn_failed"}
    tracked_slot_names = [slot_name_text(value) for value in list(request.get("tracked_slots") or []) if str(value)]
    tracked_slot_coverages = {
        slot_name: {"coverage_ratio": 0.0, "reason": "metric_camera_spawn_failed"}
        for slot_name in tracked_slot_names
    }
    if metric_camera:
        try:
            line_of_sight = line_of_sight_to_actor(metric_camera, target_actor)
            subject_coverage = screen_coverage_for_component(primary_mesh, metric_camera, width, height, fallback_actor=fallback_actor)
            weapon_coverage = screen_coverage_for_component(weapon_mesh, metric_camera, width, height)
            for slot_name in tracked_slot_names:
                tracked_component = actor_managed_component_for_slot(target_actor, slot_name, primary_component=primary_mesh)
                tracked_slot_coverages[slot_name] = screen_coverage_for_component(tracked_component, metric_camera, width, height)
        finally:
            try:
                actor_subsystem.destroy_actor(metric_camera)
            except Exception:
                pass

    capture_result = capture_frame_for_actor_object(
        target_actor,
        {
            "width": width,
            "height": height,
            "camera_mode": "explicit_pose",
            "camera_source": shot_plan["camera_source"],
            "camera_location": shot_plan["camera_location"],
            "camera_rotation": shot_plan["camera_rotation"],
            "capture_delay_seconds": float(request.get("capture_delay_seconds") or 0.2),
            "timeout_seconds": float(request.get("timeout_seconds") or 15.0),
            "file_stability_window_seconds": float(request.get("file_stability_window_seconds") or 0.75),
            "poll_interval_seconds": float(request.get("poll_interval_seconds") or 0.1),
            "tracked_slots": tracked_slot_names,
            "force_automation_capture": bool(request.get("force_automation_capture", False)),
            "scene_capture_source": str(request.get("scene_capture_source") or ""),
            "scene_capture_warmup_count": int(request.get("scene_capture_warmup_count") or 2),
            "scene_capture_warmup_delay_seconds": float(request.get("scene_capture_warmup_delay_seconds") or 0.05),
            "capture_profile": str(request.get("capture_profile") or ""),
            "prime_niagara_before_capture": bool(request.get("prime_niagara_before_capture", True)),
            "niagara_desired_age_seconds": float(request.get("niagara_desired_age_seconds") or 0.35),
            "niagara_seek_delta_seconds": float(request.get("niagara_seek_delta_seconds") or (1.0 / 30.0)),
            "niagara_advance_step_count": int(request.get("niagara_advance_step_count") or 8),
            "niagara_advance_step_delta_seconds": float(request.get("niagara_advance_step_delta_seconds") or (1.0 / 60.0)),
            "niagara_flush_world": bool(request.get("niagara_flush_world", True)),
        },
        output_path,
    )
    shot_quality = build_shot_quality_payload(
        capture_result,
        subject_coverage,
        weapon_coverage,
        line_of_sight,
        subject_min_screen_coverage,
        weapon_min_screen_coverage,
    )
    return {
        "shot_id": shot_plan["shot_id"],
        "camera_id": shot_plan["camera_id"],
        "camera_source": shot_plan["camera_source"],
        "camera_location": shot_plan["camera_location"],
        "camera_rotation": shot_plan["camera_rotation"],
        "image_path": str(output_path.resolve()),
        "subject_screen_coverage": float(subject_coverage.get("coverage_ratio") or 0.0),
        "weapon_screen_coverage": float(weapon_coverage.get("coverage_ratio") or 0.0),
        "line_of_sight_clear": bool((shot_quality.get("quality_gate") or {}).get("line_of_sight_clear")),
        "line_of_sight": line_of_sight,
        "subject_coverage": subject_coverage,
        "weapon_coverage": weapon_coverage,
        "tracked_slot_coverages": tracked_slot_coverages,
        "niagara_capture_prep": dict(capture_result.get("niagara_capture_prep") or {}),
        "scene_capture_source": str(capture_result.get("scene_capture_source") or ""),
        "capture_backend": capture_result.get("capture_backend"),
        "status": shot_quality["status"],
        "warnings": shot_quality["warnings"],
        "errors": shot_quality["errors"],
        "quality_gate": shot_quality["quality_gate"],
        "camera_plan_assessment": shot_quality["camera_plan_assessment"],
    }



