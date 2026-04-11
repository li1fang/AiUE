from __future__ import annotations

from .common import *
from .capture import *
from .preview_common import _apply_slot_binding_overrides

def apply_action_preview_to_actor(actor, request: dict) -> dict:
    before_transform = actor_transform_payload(actor)
    action_kind = str(request.get("action_kind") or "root_translate_and_turn")
    action_distance = float(request.get("action_distance") or 85.0)
    action_yaw_delta = float(request.get("action_yaw_delta") or 24.0)
    action_vertical_delta = float(request.get("action_vertical_delta") or 0.0)
    warnings = []

    before_location = actor.get_actor_location()
    before_rotation = actor.get_actor_rotation()
    target_location = before_location
    target_rotation = before_rotation

    if action_kind == "root_translate_and_turn":
        target_location = before_location + (actor.get_actor_forward_vector() * action_distance) + unreal.Vector(0.0, 0.0, action_vertical_delta)
        target_rotation = make_rotator(before_rotation.pitch, before_rotation.yaw + action_yaw_delta, before_rotation.roll)
    elif action_kind == "root_translate_forward":
        target_location = before_location + (actor.get_actor_forward_vector() * action_distance) + unreal.Vector(0.0, 0.0, action_vertical_delta)
    elif action_kind == "yaw_turn":
        target_rotation = make_rotator(before_rotation.pitch, before_rotation.yaw + action_yaw_delta, before_rotation.roll)
    else:
        warnings.append(f"unknown_action_kind_fallback:{action_kind}")
        action_kind = "root_translate_and_turn"
        target_location = before_location + (actor.get_actor_forward_vector() * action_distance) + unreal.Vector(0.0, 0.0, action_vertical_delta)
        target_rotation = make_rotator(before_rotation.pitch, before_rotation.yaw + action_yaw_delta, before_rotation.roll)

    try:
        actor.set_actor_location_and_rotation(target_location, target_rotation, False, False)
    except Exception:
        try:
            actor.set_actor_location(target_location, False, False)
        except Exception as exc:
            warnings.append(f"set_actor_location_failed:{exc}")
        try:
            actor.set_actor_rotation(target_rotation, False)
        except Exception as exc:
            warnings.append(f"set_actor_rotation_failed:{exc}")

    time.sleep(max(float(request.get("action_settle_seconds") or 0.2), 0.05))
    after_transform = actor_transform_payload(actor)
    delta = transform_delta_payload(before_transform, after_transform)
    return {
        "action_kind": action_kind,
        "requested_action_distance": action_distance,
        "requested_action_yaw_delta": action_yaw_delta,
        "requested_action_vertical_delta": action_vertical_delta,
        "before_actor_transform": before_transform,
        "after_actor_transform": after_transform,
        "transform_delta": delta,
        "warnings": warnings,
    }




def action_preview(request: dict) -> dict:
    warnings = []
    level_path = request.get("level_path") or request.get("scene_level_path")
    if level_path:
        load_result = load_level({"level_path": level_path})
        warnings.extend(load_result.get("warnings") or [])
        if load_result.get("errors"):
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": list(load_result.get("errors") or []),
            }

    host_asset_path, host_record, host_warnings = resolve_host_blueprint_asset_path(
        {
            **request,
            "runtime_ready_only": request.get("runtime_ready_only", True),
        }
    )
    warnings.extend(host_warnings)
    actor_subsystem = editor_actor_subsystem()
    blueprint_asset = unreal.EditorAssetLibrary.load_asset(object_path_from_asset_path(host_asset_path))
    if not blueprint_asset:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"host_blueprint_load_failed:{host_asset_path}"],
        }

    spawn_location = vector_from_request(request.get("location"), unreal.Vector(0.0, 0.0, 120.0))
    spawn_rotation = rotator_from_request(request.get("rotation"), make_rotator(0.0, 180.0, 0.0))
    actor_label = str(request.get("actor_label") or f"AIUE_ActionPreview_{sanitize_segment(host_record.get('character_package_id') if host_record else host_asset_path)}")

    spawned_host = actor_subsystem.spawn_actor_from_object(blueprint_asset, spawn_location, spawn_rotation, True)
    if not spawned_host:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"failed_to_spawn_host:{host_asset_path}"],
        }

    spawned_host.set_actor_label(actor_label)
    failed_requirements = []
    shots = []
    try:
        try:
            spawned_host.apply_configured_loadout()
        except Exception as exc:
            warnings.append(f"apply_configured_loadout_failed:{exc}")
        warnings.extend(_apply_slot_binding_overrides(spawned_host, request))

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

        if not main_mesh_component.get("component_name") or not character_mesh_asset:
            failed_requirements.append("mesh_missing")
        if not main_mesh_bounds.get("non_zero"):
            failed_requirements.append("bounds_invalid")
        if not weapon_mesh_component.get("component_name") or not weapon_mesh_asset:
            failed_requirements.append("weapon_missing")
        if equipment_diagnostics.get("resolved_attach_socket_exists") is False:
            failed_requirements.append("socket_resolution_failed")

        output_root = Path(request.get("output_root") or (Path(unreal.Paths.project_saved_dir()) / "pmx_pipeline" / "action_preview")).expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        shot_plans = filtered_visual_shots(spawned_host, request)
        if not shot_plans:
            failed_requirements.append("shot_plan_missing")

        before_root = output_root / "before"
        after_root = output_root / "after"
        before_root.mkdir(parents=True, exist_ok=True)
        after_root.mkdir(parents=True, exist_ok=True)

        before_capture_by_shot = {}
        for shot_plan in shot_plans:
            before_capture_by_shot[shot_plan["shot_id"]] = capture_visual_shot(
                spawned_host,
                primary_mesh,
                weapon_mesh,
                shot_plan,
                before_root / f"{shot_plan['shot_id']}.png",
                request,
                fallback_actor=spawned_host,
            )

        action_result = apply_action_preview_to_actor(spawned_host, request) if not failed_requirements else {
            "action_kind": str(request.get("action_kind") or "root_translate_and_turn"),
            "requested_action_distance": float(request.get("action_distance") or 85.0),
            "requested_action_yaw_delta": float(request.get("action_yaw_delta") or 24.0),
            "requested_action_vertical_delta": float(request.get("action_vertical_delta") or 0.0),
            "before_actor_transform": actor_transform_payload(spawned_host),
            "after_actor_transform": actor_transform_payload(spawned_host),
            "transform_delta": {
                "location_delta": {"x": 0.0, "y": 0.0, "z": 0.0},
                "distance_delta": 0.0,
                "yaw_delta": 0.0,
                "pitch_delta": 0.0,
                "roll_delta": 0.0,
            },
            "warnings": [],
        }
        warnings.extend(action_result.get("warnings") or [])
        if float((action_result.get("transform_delta") or {}).get("distance_delta") or 0.0) < float(request.get("min_distance_delta") or 10.0) and abs(float((action_result.get("transform_delta") or {}).get("yaw_delta") or 0.0)) < float(request.get("min_yaw_delta") or 5.0):
            failed_requirements.append("action_delta_too_small")

        for shot_plan in shot_plans:
            before_capture = before_capture_by_shot.get(shot_plan["shot_id"]) or {}
            after_capture = capture_visual_shot(
                spawned_host,
                primary_mesh,
                weapon_mesh,
                shot_plan,
                after_root / f"{shot_plan['shot_id']}.png",
                request,
                fallback_actor=spawned_host,
            )
            shot_errors = list(before_capture.get("errors") or []) + list(after_capture.get("errors") or [])
            shot_warnings = list(before_capture.get("warnings") or []) + list(after_capture.get("warnings") or [])
            shot_status = "pass" if not shot_errors else "fail"
            shots.append(
                {
                    "shot_id": shot_plan["shot_id"],
                    "camera_id": shot_plan["camera_id"],
                    "camera_source": shot_plan["camera_source"],
                    "camera_location": shot_plan["camera_location"],
                    "camera_rotation": shot_plan["camera_rotation"],
                    "before": before_capture,
                    "after": after_capture,
                    "status": shot_status,
                    "warnings": sorted(set(shot_warnings)),
                    "errors": sorted(set(shot_errors)),
                }
            )

        if any(shot.get("status") != "pass" for shot in shots):
            failed_requirements.append("capture_failed")
        if not any(
            (shot.get("before") or {}).get("subject_screen_coverage", 0.0) >= float(request.get("subject_min_screen_coverage") or 0.015)
            and (shot.get("after") or {}).get("subject_screen_coverage", 0.0) >= float(request.get("subject_min_screen_coverage") or 0.015)
            and (shot.get("before") or {}).get("line_of_sight_clear")
            and (shot.get("after") or {}).get("line_of_sight_clear")
            for shot in shots
        ):
            failed_requirements.append("subject_not_reliably_visible")

        return {
            "status": "pass" if not failed_requirements else "fail",
            "package_id": host_record.get("character_package_id") if host_record else request.get("package_id"),
            "sample_id": host_record.get("sample_id") if host_record else request.get("sample_id"),
            "host_id": spawned_host.get_path_name(),
            "host_blueprint_asset": host_asset_path,
            "level_path": level_path or get_current_level_path(),
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
            "component_visibility": component_visibility,
            "action_kind": action_result.get("action_kind"),
            "requested_action_distance": action_result.get("requested_action_distance"),
            "requested_action_yaw_delta": action_result.get("requested_action_yaw_delta"),
            "requested_action_vertical_delta": action_result.get("requested_action_vertical_delta"),
            "before_actor_transform": action_result.get("before_actor_transform"),
            "after_actor_transform": action_result.get("after_actor_transform"),
            "transform_delta": action_result.get("transform_delta"),
            "shots": shots,
            "failed_requirements": sorted(set(failed_requirements)),
            "warnings": warnings,
            "errors": [] if not failed_requirements else sorted(set(failed_requirements)),
        }
    finally:
        try:
            actor_subsystem.destroy_actor(spawned_host)
        except Exception:
            pass


