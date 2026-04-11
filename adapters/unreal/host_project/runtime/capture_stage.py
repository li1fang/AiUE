from __future__ import annotations

from .common import *

def load_level(request: dict) -> dict:
    level_path = request.get("level_path") or request.get("scene_level_path")
    if not level_path:
        return {
            "warnings": [],
            "errors": ["level_path_missing"],
        }
    level_object_path = object_path_from_asset_path(str(level_path))
    if not unreal.EditorAssetLibrary.does_asset_exist(level_object_path):
        return {
            "requested_level_path": str(level_path),
            "loaded": False,
            "current_level_path": get_current_level_path(),
            "warnings": [],
            "errors": [f"level_asset_missing:{level_path}"],
        }
    loaded = level_editor_subsystem().load_level(str(level_path))
    current_level_path = get_current_level_path()
    level_loaded = bool(loaded and current_level_path.startswith(str(level_path)))
    return {
        "requested_level_path": str(level_path),
        "loaded": level_loaded,
        "current_level_path": current_level_path,
        "warnings": [] if level_loaded else [f"requested_level_not_active_after_load:{level_path}"],
        "errors": [] if level_loaded else [f"failed_to_load_level:{level_path}"],
    }


def spawn_host(request: dict) -> dict:
    host_asset_path, host_record, warnings = resolve_host_blueprint_asset_path(request)
    actor_subsystem = editor_actor_subsystem()
    actor_label = str(request.get("actor_label") or asset_name_from_path(host_asset_path))
    spawn_location = vector_from_request(request.get("location"), unreal.Vector(0.0, 0.0, 0.0))
    spawn_rotation = rotator_from_request(request.get("rotation"), make_rotator(0.0, 0.0, 0.0))

    existing_actor = find_actor_by_label_or_path(actor_label=actor_label)
    if existing_actor and request.get("replace_existing", True):
        try:
            actor_subsystem.destroy_actor(existing_actor)
        except Exception as exc:
            warnings.append(f"failed_to_destroy_existing_actor:{exc}")

    blueprint_asset = unreal.EditorAssetLibrary.load_asset(object_path_from_asset_path(host_asset_path))
    if not blueprint_asset:
        return {
            "warnings": warnings,
            "errors": [f"host_blueprint_load_failed:{host_asset_path}"],
        }

    actor = actor_subsystem.spawn_actor_from_object(blueprint_asset, spawn_location, spawn_rotation)
    if not actor:
        return {
            "warnings": warnings,
            "errors": [f"failed_to_spawn_host:{host_asset_path}"],
        }

    actor.set_actor_label(actor_label)
    try:
        actor.apply_configured_loadout()
    except Exception as exc:
        warnings.append(f"apply_configured_loadout_failed:{exc}")

    camera_plan = build_capture_camera_for_actor(actor, request)
    return {
        "host_blueprint_asset_path": host_asset_path,
        "host_record": host_record,
        "spawned_actor_label": actor.get_actor_label(),
        "spawned_actor_name": actor.get_name(),
        "spawned_actor_path": actor.get_path_name(),
        "spawn_location": serialize_vector(actor.get_actor_location()),
        "spawn_rotation": serialize_rotator(actor.get_actor_rotation()),
        "current_level_path": get_current_level_path(),
        "camera_plan": camera_plan,
        "warnings": warnings,
        "errors": [],
    }


def inspect_stage_anchors(request: dict) -> dict:
    warnings = []
    level_path = request.get("level_path") or request.get("scene_level_path")
    if level_path:
        load_result = load_level({"level_path": level_path})
        warnings.extend(load_result.get("warnings") or [])
        if load_result.get("errors"):
            return {
                "stage_id": str(request.get("stage_id") or "stage"),
                "stage_level_path": str(level_path),
                "current_level_path": get_current_level_path(),
                "resolved_stage_anchors": {},
                "warnings": warnings,
                "errors": list(load_result.get("errors") or []),
            }
    expected_labels = []
    for scenario_name in list(request.get("scenario_order") or []):
        stage_entry = dict((request.get("scenario_stage_map") or {}).get(scenario_name) or {})
        expected_labels.extend(
            [
                str(stage_entry.get("spawn_anchor_actor_label") or ""),
                str(stage_entry.get("camera_anchor_actor_label") or ""),
            ]
        )
    if expected_labels and not wait_for_actor_labels(expected_labels):
        warnings.append("stage_anchor_labels_not_all_visible_before_inspection")

    scenario_order = list(request.get("scenario_order") or [])
    scenario_stage_map = dict(request.get("scenario_stage_map") or {})
    resolved_stage_anchors = {}
    errors = []
    for scenario_name in scenario_order:
        stage_entry = dict(scenario_stage_map.get(scenario_name) or {})
        spawn_anchor, spawn_record = resolve_stage_anchor_actor(
            stage_entry.get("spawn_anchor_actor_label"),
            "TargetPoint",
            "spawn",
        )
        camera_anchor, camera_record = resolve_stage_anchor_actor(
            stage_entry.get("camera_anchor_actor_label"),
            "CineCameraActor",
            "camera",
        )
        resolved_stage_anchors[scenario_name] = {
            "spawn": spawn_record,
            "camera": camera_record,
        }
        errors.extend(list(spawn_record.get("errors") or []))
        errors.extend(list(camera_record.get("errors") or []))

    return {
        "stage_id": str(request.get("stage_id") or "stage"),
        "stage_level_path": str(level_path or get_current_level_path()),
        "current_level_path": get_current_level_path(),
        "resolved_stage_anchors": resolved_stage_anchors,
        "visible_actor_snapshot": snapshot_visible_actors(),
        "warnings": warnings,
        "errors": errors,
    }


def ensure_stage_anchors(request: dict) -> dict:
    warnings = []
    level_path = request.get("level_path") or request.get("scene_level_path")
    if level_path:
        load_result = load_level({"level_path": level_path})
        warnings.extend(load_result.get("warnings") or [])
        if load_result.get("errors"):
            return {
                "stage_id": str(request.get("stage_id") or "stage"),
                "stage_level_path": str(level_path),
                "current_level_path": get_current_level_path(),
                "resolved_stage_anchors": [],
                "warnings": warnings,
                "errors": list(load_result.get("errors") or []),
            }

    actor_subsystem = editor_actor_subsystem()
    resolved_stage_anchors = []
    errors = []
    for anchor_spec in list(request.get("anchors") or []):
        label = str(anchor_spec.get("label") or "")
        anchor_class_name = str(anchor_spec.get("actor_class") or "")
        if not label:
            errors.append("stage_anchor_label_missing")
            continue
        if not anchor_class_name:
            errors.append(f"stage_anchor_class_missing:{label}")
            continue

        try:
            desired_class = stage_anchor_class(anchor_class_name)
        except Exception as exc:
            errors.append(str(exc))
            continue

        location = vector_from_request(anchor_spec.get("location"))
        rotation = rotator_from_request(anchor_spec.get("rotation"))
        existing_actor = find_actor_by_label_or_path(actor_label=label)
        action = "updated"
        if existing_actor and actor_class_name(existing_actor) != anchor_class_name:
            try:
                actor_subsystem.destroy_actor(existing_actor)
                existing_actor = None
                action = "recreated"
            except Exception as exc:
                errors.append(f"stage_anchor_destroy_failed:{label}:{exc}")
                continue

        if not existing_actor:
            existing_actor = actor_subsystem.spawn_actor_from_class(desired_class, location, rotation, False)
            action = "created" if action != "recreated" else action
        if not existing_actor:
            errors.append(f"stage_anchor_spawn_failed:{label}")
            continue

        try:
            existing_actor.set_actor_label(label)
        except Exception:
            pass
        ensure_actor_tag(existing_actor, label)
        set_if_present(existing_actor, "is_spatially_loaded", False)
        set_if_present(existing_actor, "b_is_spatially_loaded", False)
        try:
            existing_actor.set_actor_location(location, False, False)
        except Exception:
            existing_actor.set_actor_location(location, False)
        try:
            existing_actor.set_actor_rotation(rotation, False)
        except Exception:
            existing_actor.set_actor_rotation(rotation)

        resolved_entry = serialize_actor_reference(existing_actor, label)
        resolved_entry.update(
            {
                "requested_class_name": anchor_class_name,
                "action": action,
                "status": "pass",
                "warnings": [],
                "errors": [],
            }
        )
        resolved_stage_anchors.append(resolved_entry)

    saved, save_warnings = save_current_level()
    warnings.extend(save_warnings)
    if not saved:
        warnings.append("stage_anchor_level_save_not_confirmed")

    return {
        "stage_id": str(request.get("stage_id") or "stage"),
        "stage_level_path": str(level_path or get_current_level_path()),
        "current_level_path": get_current_level_path(),
        "resolved_stage_anchors": resolved_stage_anchors,
        "saved_level": saved,
        "warnings": warnings,
        "errors": errors,
    }


