from __future__ import annotations

from .common import *
from .capture import load_level
from .retarget_profile import load_asset_from_any_path


def prepare_retarget_host_session(
    request: dict,
    *,
    actor_label_prefix: str,
    default_location,
    default_rotation,
    require_animation_asset: bool = True,
) -> dict:
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

    animation_asset_path = str(request.get("animation_asset_path") or "")
    animation_asset = None
    if require_animation_asset:
        animation_asset = load_asset_from_any_path(animation_asset_path)
        if not animation_asset:
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": [f"animation_asset_load_failed:{animation_asset_path or 'missing'}"],
            }

    spawn_location = vector_from_request(request.get("location"), default_location)
    spawn_rotation = rotator_from_request(request.get("rotation"), default_rotation)
    actor_label = str(
        request.get("actor_label")
        or f"{actor_label_prefix}_{sanitize_segment(host_record.get('character_package_id') if host_record else host_asset_path)}"
    )
    spawned_host = actor_subsystem.spawn_actor_from_object(blueprint_asset, spawn_location, spawn_rotation, True)
    if not spawned_host:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"failed_to_spawn_host:{host_asset_path}"],
        }

    spawned_host.set_actor_label(actor_label)
    return {
        "status": "pass",
        "warnings": warnings,
        "errors": [],
        "level_path": level_path or get_current_level_path(),
        "host_asset_path": host_asset_path,
        "host_record": host_record,
        "animation_asset_path": animation_asset_path,
        "animation_asset": animation_asset,
        "actor_subsystem": actor_subsystem,
        "spawned_host": spawned_host,
    }


def apply_retarget_configured_loadout(spawned_host, warnings: list[str]) -> None:
    try:
        spawned_host.apply_configured_loadout()
    except Exception as exc:
        warnings.append(f"apply_configured_loadout_failed:{exc}")


def destroy_retarget_host(actor_subsystem, spawned_host) -> None:
    try:
        actor_subsystem.destroy_actor(spawned_host)
    except Exception:
        pass


__all__ = [
    "apply_retarget_configured_loadout",
    "destroy_retarget_host",
    "prepare_retarget_host_session",
]
