from __future__ import annotations

from .common import *
from .composition_registry_assets import blueprint_cdo, blueprint_generated_class, compile_blueprint_asset
from .composition_registry_slot_bindings import unreal_slot_bindings


def validate_runtime_loadout(loadout_asset, asset_path: str) -> dict:
    loadout = loadout_asset.get_editor_property("loadout")
    character_mesh = getattr(loadout, "character_mesh", None)
    loadout_slot_bindings_payload = [slot_binding_payload(binding) for binding in list(getattr(loadout, "slot_bindings", []) or [])]
    has_binding_assets = any(binding.get("asset_path") for binding in loadout_slot_bindings_payload)
    weapon_mesh = getattr(loadout, "weapon_mesh", None)
    if not character_mesh or not (has_binding_assets or weapon_mesh):
        return {
            "loadout_asset_path": asset_path,
            "status": "skipped",
            "warnings": ["loadout_missing_character_or_slot_binding_mesh"],
            "errors": [],
        }
    if not hasattr(unreal, "PMXEquipmentBlueprintLibrary"):
        return {
            "loadout_asset_path": asset_path,
            "status": "skipped",
            "warnings": ["pmx_blueprint_library_unavailable"],
            "errors": [],
        }

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = None
    try:
        actor = actor_subsystem.spawn_actor_from_class(unreal.Character.static_class(), unreal.Vector(0.0, 0.0, 0.0), make_rotator(0.0, 0.0, 0.0))
        if not actor:
            return {
                "loadout_asset_path": asset_path,
                "status": "skipped",
                "warnings": ["failed_to_spawn_preview_character"],
                "errors": [],
            }
        owner_mesh = actor.get_editor_property("mesh")
        owner_mesh.set_skeletal_mesh(character_mesh)
        weapon_component = unreal.PMXEquipmentBlueprintLibrary.apply_equipment_loadout(actor, loadout_asset)
        pmx_component = actor.get_component_by_class(unreal.PMXCharacterEquipmentComponent)
        desired_weapon_mesh = pmx_component.get_desired_weapon_mesh() if pmx_component else None
        attach_socket_name = str(pmx_component.get_attach_socket_name()) if pmx_component else ""
        managed_component = pmx_component.get_managed_weapon_mesh_component() if pmx_component else None
        slot_bindings = pmx_slot_bindings_payload(pmx_component)
        slot_attach_state = pmx_slot_attach_states_payload(pmx_component)
        slot_conflicts = pmx_slot_conflicts_payload(pmx_component)
        managed_components_by_slot = actor_managed_components_by_slot(actor, pmx_component, primary_component=owner_mesh)
        applied_slot_bindings = [
            {
                **binding,
                "managed_component": dict(managed_components_by_slot.get(binding.get("slot_name")) or {}),
                "attach_state": next((state for state in slot_attach_state if state.get("slot_name") == binding.get("slot_name")), {}),
            }
            for binding in slot_bindings
        ]
        success = bool(weapon_component and managed_component and desired_weapon_mesh and any(binding.get("slot_name") == "weapon" for binding in slot_bindings or loadout_slot_bindings_payload))
        warnings = []
        if success and attach_socket_name != str(loadout.attach_socket_name):
            warnings.append(f"attach_socket_mismatch:{attach_socket_name}:{loadout.attach_socket_name}")
        return {
            "loadout_asset_path": asset_path,
            "status": "pass" if success else "fail",
            "warnings": warnings,
            "errors": [] if success else ["preview_apply_equipment_loadout_failed"],
            "attach_socket_name": attach_socket_name,
            "desired_weapon_mesh_path": path_for_loaded_asset(desired_weapon_mesh),
            "managed_weapon_component_name": managed_component.get_name() if managed_component else None,
            "slot_bindings": slot_bindings or loadout_slot_bindings_payload,
            "applied_slot_bindings": applied_slot_bindings,
            "managed_components_by_slot": managed_components_by_slot,
            "slot_attach_state": slot_attach_state,
            "slot_conflicts": slot_conflicts,
            "superseded_bindings": slot_conflicts,
        }
    except Exception as exc:
        return {
            "loadout_asset_path": asset_path,
            "status": "fail",
            "warnings": [],
            "errors": [str(exc)],
        }
    finally:
        if actor:
            try:
                actor_subsystem.destroy_actor(actor)
            except Exception:
                pass


def configure_component_blueprint(blueprint, slot_bindings: list[dict], weapon_mesh_path: str | None, attach_socket_name: str | None) -> None:
    cdo = blueprint_cdo(blueprint)
    if not cdo:
        raise RuntimeError("Unable to resolve blueprint CDO for component blueprint")
    set_if_present(cdo, "desired_slot_bindings", unreal_slot_bindings(slot_bindings))
    set_if_present(cdo, "desired_weapon_mesh", load_asset(weapon_mesh_path))
    set_if_present(cdo, "attach_socket_name", attach_socket_name or "WeaponSocket")
    set_if_present(cdo, "b_create_component_if_missing", True)
    set_if_present(cdo, "create_component_if_missing", True)
    compile_blueprint_asset(blueprint)


def configure_host_blueprint(blueprint, character_mesh_path: str | None, loadout_asset, component_blueprint) -> None:
    cdo = blueprint_cdo(blueprint)
    if not cdo:
        raise RuntimeError("Unable to resolve blueprint CDO for host blueprint")
    component_class = blueprint_generated_class(component_blueprint) if component_blueprint else unreal.PMXCharacterEquipmentComponent
    set_if_present(cdo, "character_mesh_asset", load_asset(character_mesh_path))
    set_if_present(cdo, "default_loadout_asset", loadout_asset)
    set_if_present(cdo, "equipment_component_class", component_class)
    compile_blueprint_asset(blueprint)


def validate_host_blueprint(host_blueprint, host_asset_path: str, loadout_asset, loadout_record: dict, component_blueprint_asset_path: str) -> dict:
    generated_class = blueprint_generated_class(host_blueprint)
    if not generated_class:
        return {
            "asset_path": host_asset_path,
            "status": "fail",
            "warnings": [],
            "errors": ["host_blueprint_generated_class_missing"],
        }
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = None
    try:
        actor = actor_subsystem.spawn_actor_from_class(generated_class, unreal.Vector(0.0, 0.0, 0.0), make_rotator(0.0, 0.0, 0.0))
        if not actor:
            return {
                "asset_path": host_asset_path,
                "status": "fail",
                "warnings": [],
                "errors": ["failed_to_spawn_host_blueprint"],
            }
        actor.apply_configured_loadout()
        equipment_component = actor.get_component_by_class(unreal.PMXCharacterEquipmentComponent)
        managed_component = equipment_component.get_managed_weapon_mesh_component() if equipment_component else None
        desired_weapon_mesh = equipment_component.get_desired_weapon_mesh() if equipment_component else None
        attach_socket_name = str(equipment_component.get_attach_socket_name()) if equipment_component else ""
        mesh_component = actor.get_editor_property("mesh") if hasattr(actor, "get_editor_property") else None
        slot_bindings = pmx_slot_bindings_payload(equipment_component)
        slot_attach_state = pmx_slot_attach_states_payload(equipment_component)
        slot_conflicts = pmx_slot_conflicts_payload(equipment_component)
        managed_components_by_slot = actor_managed_components_by_slot(actor, equipment_component, primary_component=mesh_component)
        applied_slot_bindings = [
            {
                **binding,
                "managed_component": dict(managed_components_by_slot.get(binding.get("slot_name")) or {}),
                "attach_state": next((state for state in slot_attach_state if state.get("slot_name") == binding.get("slot_name")), {}),
            }
            for binding in slot_bindings
        ]
        has_ready_weapon_pairs = bool(loadout_record.get("has_ready_weapon_pairs"))
        has_runtime_weapon_mesh_component = bool(managed_component and desired_weapon_mesh)
        success = has_runtime_weapon_mesh_component if has_ready_weapon_pairs else True
        return {
            "asset_path": host_asset_path,
            "loadout_asset_path": loadout_record.get("loadout_asset_path"),
            "component_blueprint_asset_path": component_blueprint_asset_path,
            "default_weapon_package_id": loadout_record.get("default_weapon_package_id") or "",
            "default_weapon_skeletal_mesh": loadout_record.get("default_weapon_skeletal_mesh") or "",
            "consumer_ready": bool(loadout_record.get("consumer_ready")),
            "has_ready_weapon_pairs": has_ready_weapon_pairs,
            "has_runtime_weapon_mesh_component": has_runtime_weapon_mesh_component,
            "default_weapon_component_name": managed_component.get_name() if managed_component else "DefaultWeaponMeshComponent",
            "default_weapon_component_created": False,
            "default_weapon_component_attach_ok": bool(not has_ready_weapon_pairs or has_runtime_weapon_mesh_component),
            "default_weapon_component_attach_parent": mesh_component.get_name() if mesh_component else "CharacterMesh0",
            "default_weapon_component_attach_socket_name": attach_socket_name or "WeaponSocket",
            "equipment_component_parent_class": str(unreal.PMXCharacterEquipmentComponent),
            "native_runtime_available": True,
            "slot_bindings": slot_bindings,
            "applied_slot_bindings": applied_slot_bindings,
            "managed_components_by_slot": managed_components_by_slot,
            "slot_attach_state": slot_attach_state,
            "slot_conflicts": slot_conflicts,
            "superseded_bindings": slot_conflicts,
            "status": "pass" if success else "fail",
            "warnings": [],
            "errors": [] if success else ["host_runtime_weapon_mesh_component_missing"],
        }
    except Exception as exc:
        return {
            "asset_path": host_asset_path,
            "status": "fail",
            "warnings": [],
            "errors": [str(exc)],
        }
    finally:
        if actor:
            try:
                actor_subsystem.destroy_actor(actor)
            except Exception:
                pass


__all__ = [
    "validate_runtime_loadout",
    "configure_component_blueprint",
    "configure_host_blueprint",
    "validate_host_blueprint",
]
