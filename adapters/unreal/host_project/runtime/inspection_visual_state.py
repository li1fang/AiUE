from __future__ import annotations

from .common import *


def _material_asset_path(material) -> str:
    if not material:
        return ""
    if hasattr(material, "get_path_name"):
        try:
            return str(material.get_path_name() or "")
        except Exception:
            return ""
    return ""


def _component_material_slot_count(component) -> int:
    if not component or not hasattr(component, "get_num_materials"):
        return 0
    try:
        return int(component.get_num_materials() or 0)
    except Exception:
        return 0


def _component_material_slot_names(component) -> list[str]:
    if not component:
        return []
    if hasattr(component, "get_material_slot_names"):
        try:
            names = [str(item) for item in list(component.get_material_slot_names() or []) if str(item)]
            if names:
                return names
        except Exception:
            pass
    asset = None
    for property_name in ("skeletal_mesh_asset", "skeletal_mesh", "static_mesh"):
        try:
            asset = component.get_editor_property(property_name)
        except Exception:
            asset = None
        if asset:
            break
    if not asset:
        return []
    for property_name in ("materials", "static_materials"):
        try:
            entries = list(asset.get_editor_property(property_name) or [])
        except Exception:
            entries = []
        if not entries:
            continue
        slot_names = []
        for entry in entries:
            slot_name = None
            for entry_property in ("material_slot_name", "imported_material_slot_name", "slot_name"):
                try:
                    slot_name = entry.get_editor_property(entry_property)
                except Exception:
                    slot_name = getattr(entry, entry_property, None)
                if slot_name:
                    break
            slot_names.append(str(slot_name or ""))
        if any(slot_names):
            return slot_names
    return []


def _component_material_asset_paths(component) -> list[str]:
    paths = []
    slot_count = _component_material_slot_count(component)
    for index in range(slot_count):
        try:
            material = component.get_material(index)
        except Exception:
            material = None
        paths.append(_material_asset_path(material))
    return paths


def _component_texture_reference_summary(component) -> dict:
    # First M1 only needs a recoverable summary envelope; full material->texture
    # tracing can be strengthened later without changing the response shape.
    material_asset_paths = [path for path in _component_material_asset_paths(component) if path]
    return {
        "status": "unavailable" if material_asset_paths else "missing",
        "texture_asset_paths": [],
        "warnings": [] if material_asset_paths else ["material_assets_missing"],
        "detection_method": "material_path_only_v1",
    }


def _component_material_evidence(component) -> dict:
    slot_names = _component_material_slot_names(component)
    material_asset_paths = _component_material_asset_paths(component)
    return {
        "material_slot_count": _component_material_slot_count(component),
        "material_slot_names": slot_names,
        "material_asset_paths": material_asset_paths,
        "non_empty_material_asset_paths": [path for path in material_asset_paths if path],
        "texture_reference_summary": _component_texture_reference_summary(component),
    }


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
    material_evidence = {
        "main_mesh": _component_material_evidence(primary_mesh),
        "weapon_mesh": _component_material_evidence(weapon_mesh),
        "managed_slots": {
            str(slot_name or ""): _component_material_evidence(actor_managed_component_for_slot(spawned_host, slot_name, primary_component=primary_mesh))
            for slot_name in managed_components_by_slot
            if str(slot_name or "")
        },
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
        "material_evidence": material_evidence,
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
