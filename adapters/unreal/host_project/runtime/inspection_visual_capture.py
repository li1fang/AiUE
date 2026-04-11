from __future__ import annotations

from .common import *
from .capture import *


def _capture_visual_shot(
    *,
    actor_subsystem,
    spawned_host,
    request: dict,
    shot_plan: dict,
    output_root: Path,
    primary_mesh,
    weapon_mesh,
    tracked_slot_names: list[str],
    width: int,
    height: int,
    subject_min_screen_coverage: float,
    weapon_min_screen_coverage: float,
) -> dict:
    metric_camera = actor_subsystem.spawn_actor_from_class(
        unreal.CameraActor,
        vector_from_request(shot_plan["camera_location"]),
        rotator_from_request(shot_plan["camera_rotation"]),
        True,
    )
    line_of_sight = {"clear": False, "reason": "metric_camera_spawn_failed"}
    subject_coverage = {"coverage_ratio": 0.0, "reason": "metric_camera_spawn_failed"}
    weapon_coverage = {"coverage_ratio": 0.0, "reason": "metric_camera_spawn_failed"}
    tracked_slot_coverages = {
        slot_name: {"coverage_ratio": 0.0, "reason": "metric_camera_spawn_failed"}
        for slot_name in tracked_slot_names
    }
    if metric_camera:
        try:
            line_of_sight = line_of_sight_to_actor(metric_camera, spawned_host)
            subject_coverage = screen_coverage_for_component(primary_mesh, metric_camera, width, height, fallback_actor=spawned_host)
            weapon_coverage = screen_coverage_for_component(weapon_mesh, metric_camera, width, height)
            for slot_name in tracked_slot_names:
                tracked_component = actor_managed_component_for_slot(spawned_host, slot_name, primary_component=primary_mesh)
                tracked_slot_coverages[slot_name] = screen_coverage_for_component(tracked_component, metric_camera, width, height)
        finally:
            try:
                actor_subsystem.destroy_actor(metric_camera)
            except Exception:
                pass

    image_path = output_root / f"{shot_plan['shot_id']}.png"
    capture_result = capture_frame(
        {
            "actor_path": spawned_host.get_path_name(),
            "actor_label": spawned_host.get_actor_label(),
            "output_path": str(image_path),
            "width": width,
            "height": height,
            "tracked_slots": tracked_slot_names,
            "force_automation_capture": bool(request.get("force_automation_capture", False)),
            "scene_capture_source": str(request.get("scene_capture_source") or ""),
            "scene_capture_warmup_count": int(request.get("scene_capture_warmup_count") or 2),
            "scene_capture_warmup_delay_seconds": float(request.get("scene_capture_warmup_delay_seconds") or 0.05),
            "prime_niagara_before_capture": bool(request.get("prime_niagara_before_capture", True)),
            "niagara_desired_age_seconds": float(request.get("niagara_desired_age_seconds") or 0.35),
            "niagara_seek_delta_seconds": float(request.get("niagara_seek_delta_seconds") or (1.0 / 30.0)),
            "niagara_advance_step_count": int(request.get("niagara_advance_step_count") or 8),
            "niagara_advance_step_delta_seconds": float(request.get("niagara_advance_step_delta_seconds") or (1.0 / 60.0)),
            "niagara_flush_world": bool(request.get("niagara_flush_world", True)),
            "camera_mode": "explicit_pose",
            "camera_source": shot_plan["camera_source"],
            "camera_location": shot_plan["camera_location"],
            "camera_rotation": shot_plan["camera_rotation"],
            "capture_delay_seconds": float(request.get("capture_delay_seconds") or 0.2),
            "timeout_seconds": float(request.get("timeout_seconds") or 15.0),
            "file_stability_window_seconds": float(request.get("file_stability_window_seconds") or 0.75),
            "poll_interval_seconds": float(request.get("poll_interval_seconds") or 0.1),
        }
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
        "shot": {
            "shot_id": shot_plan["shot_id"],
            "camera_id": shot_plan["camera_id"],
            "image_path": str(image_path.resolve()),
            "camera_source": shot_plan["camera_source"],
            "camera_location": shot_plan["camera_location"],
            "camera_rotation": shot_plan["camera_rotation"],
            "subject_screen_coverage": float(subject_coverage.get("coverage_ratio") or 0.0),
            "weapon_screen_coverage": float(weapon_coverage.get("coverage_ratio") or 0.0),
            "line_of_sight_clear": bool((shot_quality.get("quality_gate") or {}).get("line_of_sight_clear")),
            "line_of_sight": line_of_sight,
            "subject_coverage": subject_coverage,
            "weapon_coverage": weapon_coverage,
            "tracked_slot_coverages": tracked_slot_coverages,
            "niagara_capture_prep": dict(capture_result.get("niagara_capture_prep") or {}),
            "capture_backend": str(capture_result.get("capture_backend") or ""),
            "scene_capture_source": str(capture_result.get("scene_capture_source") or ""),
            "status": shot_quality["status"],
            "warnings": shot_quality["warnings"],
            "errors": shot_quality["errors"],
            "quality_gate": shot_quality["quality_gate"],
            "camera_plan_assessment": shot_quality["camera_plan_assessment"],
        },
        "subject_passed": bool((shot_quality.get("quality_gate") or {}).get("subject_visible"))
        and bool((shot_quality.get("quality_gate") or {}).get("line_of_sight_clear"))
        and bool((shot_quality.get("quality_gate") or {}).get("capture_succeeded")),
        "weapon_passed": bool((shot_quality.get("quality_gate") or {}).get("weapon_visible")),
    }


def capture_visual_state_for_host(
    spawned_host,
    request: dict,
    host_asset_path: str,
    host_record: dict | None,
    output_root: Path,
    override_bindings: list[dict] | None = None,
) -> dict:
    warnings = []
    failed_requirements = []
    override_bindings = list(override_bindings or [])
    if override_bindings:
        if hasattr(unreal, "PMXEquipmentBlueprintLibrary"):
            unreal.PMXEquipmentBlueprintLibrary.apply_slot_bindings(
                spawned_host,
                runtime_slot_binding_entries_from_request(override_bindings),
            )
        else:
            failed_requirements.append("pmx_blueprint_library_unavailable")

    time.sleep(max(float(request.get("settle_delay_seconds") or 0.2), 0.05))
    try:
        pmx_component = spawned_host.get_component_by_class(unreal.PMXCharacterEquipmentComponent)
    except Exception:
        pmx_component = None
    primary_mesh = actor_primary_mesh_component(spawned_host)
    weapon_mesh = actor_weapon_mesh_component(spawned_host, primary_mesh)
    main_mesh_component = component_visibility_record(primary_mesh)
    weapon_mesh_component = component_visibility_record(weapon_mesh)
    main_mesh_bounds = component_bounds_payload(primary_mesh, fallback_actor=spawned_host)
    weapon_mesh_bounds = component_bounds_payload(weapon_mesh)
    main_mesh_world_transform = component_transform_payload(primary_mesh)
    weapon_mesh_world_transform = component_transform_payload(weapon_mesh)
    weapon_attachment = component_attach_payload(weapon_mesh)
    equipment_diagnostics = pmx_equipment_diagnostics(pmx_component, primary_mesh)
    slot_bindings = pmx_slot_bindings_payload(pmx_component)
    slot_attach_state = pmx_slot_attach_states_payload(pmx_component)
    slot_conflicts = pmx_slot_conflicts_payload(pmx_component)
    managed_components_by_slot = actor_managed_components_by_slot(spawned_host, pmx_component, primary_component=primary_mesh)
    applied_slot_bindings = [
        {
            **binding,
            "managed_component": dict(managed_components_by_slot.get(binding.get("slot_name")) or {}),
            "attach_state": next((state for state in slot_attach_state if state.get("slot_name") == binding.get("slot_name")), {}),
        }
        for binding in slot_bindings
    ]
    component_visibility = {
        "main_mesh": main_mesh_component,
        "weapon_mesh": weapon_mesh_component,
    }
    character_mesh_asset = main_mesh_component.get("asset_path") or ""
    weapon_mesh_asset = weapon_mesh_component.get("asset_path") or ""

    if not main_mesh_component.get("component_name"):
        failed_requirements.append("mesh_missing")
    if not character_mesh_asset:
        failed_requirements.append("mesh_missing")
    if not main_mesh_bounds.get("non_zero"):
        failed_requirements.append("bounds_invalid")
    if not weapon_mesh_component.get("component_name"):
        failed_requirements.append("weapon_missing")
    if not weapon_mesh_asset:
        failed_requirements.append("weapon_missing")
    if equipment_diagnostics.get("resolved_attach_socket_exists") is False:
        failed_requirements.append("socket_resolution_failed")

    output_root.mkdir(parents=True, exist_ok=True)
    width = int(request.get("width") or request.get("capture_width") or 1280)
    height = int(request.get("height") or request.get("capture_height") or 720)
    subject_min_screen_coverage = float(request.get("subject_min_screen_coverage") or 0.015)
    weapon_min_screen_coverage = float(request.get("weapon_min_screen_coverage") or 0.001)
    tracked_slot_names = [slot_name_text(value) for value in list(request.get("tracked_slots") or []) if str(value)]
    shot_plans = build_visual_proof_shots(spawned_host, request)
    requested_shot_ids = [str(value) for value in list(request.get("requested_shot_ids") or []) if str(value)]
    if requested_shot_ids:
        requested_id_set = set(requested_shot_ids)
        shot_plans = [shot_plan for shot_plan in shot_plans if str(shot_plan.get("shot_id") or "") in requested_id_set]
        if not shot_plans:
            failed_requirements.append("requested_shots_missing")

    subject_pass_count = 0
    weapon_pass_count = 0
    shots = []
    actor_subsystem = editor_actor_subsystem()
    for shot_plan in shot_plans:
        shot_result = _capture_visual_shot(
            actor_subsystem=actor_subsystem,
            spawned_host=spawned_host,
            request=request,
            shot_plan=shot_plan,
            output_root=output_root,
            primary_mesh=primary_mesh,
            weapon_mesh=weapon_mesh,
            tracked_slot_names=tracked_slot_names,
            width=width,
            height=height,
            subject_min_screen_coverage=subject_min_screen_coverage,
            weapon_min_screen_coverage=weapon_min_screen_coverage,
        )
        subject_pass_count += int(shot_result["subject_passed"])
        weapon_pass_count += int(shot_result["weapon_passed"])
        shots.append(shot_result["shot"])

    required_subject_pass_count = min(2, len(shot_plans)) if shot_plans else 1
    required_weapon_pass_count = 1 if shot_plans else 0
    if subject_pass_count < required_subject_pass_count:
        failed_requirements.append("out_of_frame")
    if weapon_pass_count < required_weapon_pass_count:
        failed_requirements.append("weapon_invisible")
    if any(shot.get("status") != "pass" for shot in shots) and "capture_failed" not in failed_requirements:
        if any("capture_failed" in (shot.get("errors") or []) for shot in shots):
            failed_requirements.append("capture_failed")
        if any("occluded" in (shot.get("errors") or []) for shot in shots):
            failed_requirements.append("occluded")

    return {
        "status": "pass" if not failed_requirements else "fail",
        "package_id": host_record.get("character_package_id") if host_record else request.get("package_id"),
        "host_id": spawned_host.get_path_name(),
        "host_blueprint_asset": host_asset_path,
        "character_mesh_asset": character_mesh_asset,
        "weapon_mesh_asset": weapon_mesh_asset,
        "main_mesh_component": {
            "component_name": main_mesh_component.get("component_name"),
            "class_name": main_mesh_component.get("class_name"),
        },
        "weapon_mesh_component": {
            "component_name": weapon_mesh_component.get("component_name"),
            "class_name": weapon_mesh_component.get("class_name"),
        },
        "main_mesh_bounds": main_mesh_bounds,
        "weapon_mesh_bounds": weapon_mesh_bounds,
        "main_mesh_world_transform": main_mesh_world_transform,
        "weapon_mesh_world_transform": weapon_mesh_world_transform,
        "weapon_attachment": weapon_attachment,
        "equipment_diagnostics": equipment_diagnostics,
        "slot_bindings": slot_bindings,
        "applied_slot_bindings": applied_slot_bindings,
        "managed_components_by_slot": managed_components_by_slot,
        "slot_attach_state": slot_attach_state,
        "slot_conflicts": slot_conflicts,
        "superseded_bindings": slot_conflicts,
        "tracked_slots": tracked_slot_names,
        "component_visibility": component_visibility,
        "shots": shots,
        "failed_requirements": sorted(set(failed_requirements)),
        "warnings": warnings,
        "errors": [] if not failed_requirements else sorted(set(failed_requirements)),
    }


__all__ = ["capture_visual_state_for_host"]
