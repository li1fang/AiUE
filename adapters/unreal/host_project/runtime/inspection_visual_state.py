from __future__ import annotations

from .common import *


def apply_visual_slot_binding_overrides(spawned_host, override_bindings: list[dict] | None = None) -> list[str]:
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
    return failed_requirements


def collect_visual_host_state(spawned_host) -> dict:
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
    return {
        "pmx_component": pmx_component,
        "primary_mesh": primary_mesh,
        "weapon_mesh": weapon_mesh,
        "main_mesh_component": main_mesh_component,
        "weapon_mesh_component": weapon_mesh_component,
        "main_mesh_bounds": main_mesh_bounds,
        "weapon_mesh_bounds": weapon_mesh_bounds,
        "main_mesh_world_transform": main_mesh_world_transform,
        "weapon_mesh_world_transform": weapon_mesh_world_transform,
        "weapon_attachment": weapon_attachment,
        "equipment_diagnostics": equipment_diagnostics,
        "slot_bindings": slot_bindings,
        "slot_attach_state": slot_attach_state,
        "slot_conflicts": slot_conflicts,
        "managed_components_by_slot": managed_components_by_slot,
        "applied_slot_bindings": applied_slot_bindings,
        "component_visibility": component_visibility,
        "character_mesh_asset": str(main_mesh_component.get("asset_path") or ""),
        "weapon_mesh_asset": str(weapon_mesh_component.get("asset_path") or ""),
    }


def evaluate_visual_host_requirements(state: dict) -> list[str]:
    failed_requirements = []
    main_mesh_component = dict(state.get("main_mesh_component") or {})
    weapon_mesh_component = dict(state.get("weapon_mesh_component") or {})
    main_mesh_bounds = dict(state.get("main_mesh_bounds") or {})
    equipment_diagnostics = dict(state.get("equipment_diagnostics") or {})
    if not main_mesh_component.get("component_name"):
        failed_requirements.append("mesh_missing")
    if not state.get("character_mesh_asset"):
        failed_requirements.append("mesh_missing")
    if not main_mesh_bounds.get("non_zero"):
        failed_requirements.append("bounds_invalid")
    if not weapon_mesh_component.get("component_name"):
        failed_requirements.append("weapon_missing")
    if not state.get("weapon_mesh_asset"):
        failed_requirements.append("weapon_missing")
    if equipment_diagnostics.get("resolved_attach_socket_exists") is False:
        failed_requirements.append("socket_resolution_failed")
    return failed_requirements


__all__ = [
    "apply_visual_slot_binding_overrides",
    "collect_visual_host_state",
    "evaluate_visual_host_requirements",
]
