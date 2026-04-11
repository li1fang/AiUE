from __future__ import annotations

from .common import *
from .inspection_visual_shots import capture_visual_shot_set
from .inspection_visual_state import (
    apply_visual_slot_binding_overrides,
    collect_visual_host_state,
    evaluate_visual_host_requirements,
)


def capture_visual_state_for_host(
    spawned_host,
    request: dict,
    host_asset_path: str,
    host_record: dict | None,
    output_root: Path,
    override_bindings: list[dict] | None = None,
) -> dict:
    warnings = []
    failed_requirements = list(apply_visual_slot_binding_overrides(spawned_host, override_bindings))

    time.sleep(max(float(request.get("settle_delay_seconds") or 0.2), 0.05))
    visual_state = collect_visual_host_state(spawned_host)
    failed_requirements.extend(evaluate_visual_host_requirements(visual_state))
    shot_result = capture_visual_shot_set(
        spawned_host=spawned_host,
        request=request,
        output_root=output_root,
        primary_mesh=visual_state.get("primary_mesh"),
        weapon_mesh=visual_state.get("weapon_mesh"),
    )
    failed_requirements.extend(list(shot_result.get("failed_requirements") or []))

    return {
        "status": "pass" if not failed_requirements else "fail",
        "package_id": host_record.get("character_package_id") if host_record else request.get("package_id"),
        "host_id": spawned_host.get_path_name(),
        "host_blueprint_asset": host_asset_path,
        "character_mesh_asset": visual_state.get("character_mesh_asset"),
        "weapon_mesh_asset": visual_state.get("weapon_mesh_asset"),
        "main_mesh_component": {
            "component_name": dict(visual_state.get("main_mesh_component") or {}).get("component_name"),
            "class_name": dict(visual_state.get("main_mesh_component") or {}).get("class_name"),
        },
        "weapon_mesh_component": {
            "component_name": dict(visual_state.get("weapon_mesh_component") or {}).get("component_name"),
            "class_name": dict(visual_state.get("weapon_mesh_component") or {}).get("class_name"),
        },
        "main_mesh_bounds": visual_state.get("main_mesh_bounds"),
        "weapon_mesh_bounds": visual_state.get("weapon_mesh_bounds"),
        "main_mesh_world_transform": visual_state.get("main_mesh_world_transform"),
        "weapon_mesh_world_transform": visual_state.get("weapon_mesh_world_transform"),
        "weapon_attachment": visual_state.get("weapon_attachment"),
        "equipment_diagnostics": visual_state.get("equipment_diagnostics"),
        "slot_bindings": visual_state.get("slot_bindings"),
        "applied_slot_bindings": visual_state.get("applied_slot_bindings"),
        "managed_components_by_slot": visual_state.get("managed_components_by_slot"),
        "slot_attach_state": visual_state.get("slot_attach_state"),
        "slot_conflicts": visual_state.get("slot_conflicts"),
        "superseded_bindings": visual_state.get("slot_conflicts"),
        "tracked_slots": shot_result.get("tracked_slot_names"),
        "component_visibility": visual_state.get("component_visibility"),
        "shots": shot_result.get("shots"),
        "failed_requirements": sorted(set(failed_requirements)),
        "warnings": warnings,
        "errors": [] if not failed_requirements else sorted(set(failed_requirements)),
    }


__all__ = ["capture_visual_state_for_host"]
