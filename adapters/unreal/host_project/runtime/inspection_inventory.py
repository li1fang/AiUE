from __future__ import annotations

from .common import *
from .capture import *


def inspect_slot_runtime(request: dict) -> dict:
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

    spawn_location = vector_from_request(request.get("location") or request.get("cell_origin"), unreal.Vector(0.0, 0.0, 120.0))
    spawn_rotation = rotator_from_request(request.get("rotation") or request.get("cell_rotation"), make_rotator(0.0, 180.0, 0.0))
    actor_label = str(request.get("actor_label") or f"AIUE_SlotRuntime_{sanitize_segment(host_record.get('character_package_id') if host_record else host_asset_path)}")
    spawned_host = actor_subsystem.spawn_actor_from_object(blueprint_asset, spawn_location, spawn_rotation, True)
    if not spawned_host:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"failed_to_spawn_host:{host_asset_path}"],
        }

    spawned_host.set_actor_label(actor_label)
    failed_requirements = []
    try:
        try:
            spawned_host.apply_configured_loadout()
        except Exception as exc:
            warnings.append(f"apply_configured_loadout_failed:{exc}")

        override_bindings = list(request.get("slot_binding_overrides") or [])
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
        required_slots = [slot_name_text(value) for value in list(request.get("required_slots") or []) if str(value)]
        if not required_slots:
            required_slots = [binding.get("slot_name") for binding in slot_bindings if binding.get("slot_name")]
        required_slots = sorted(set(required_slots))

        for slot_name in required_slots:
            managed_component = dict(managed_components_by_slot.get(slot_name) or {})
            attach_state = next((state for state in slot_attach_state if state.get("slot_name") == slot_name), {})
            binding = next((item for item in slot_bindings if item.get("slot_name") == slot_name), {})
            if not managed_component.get("component_name"):
                failed_requirements.append(f"slot_missing:{slot_name}")
            if not managed_component.get("asset_path") and not binding.get("asset_path"):
                failed_requirements.append(f"slot_asset_missing:{slot_name}")
            if attach_state and attach_state.get("resolved_attach_socket_exists") is False:
                failed_requirements.append(f"slot_attach_unresolved:{slot_name}")

        return {
            "status": "pass" if not failed_requirements else "fail",
            "package_id": host_record.get("character_package_id") if host_record else request.get("package_id"),
            "sample_id": host_record.get("sample_id") if host_record else request.get("sample_id"),
            "host_id": spawned_host.get_path_name(),
            "host_blueprint_asset": host_asset_path,
            "level_path": level_path or get_current_level_path(),
            "character_mesh_asset": component_asset_path(primary_mesh),
            "weapon_mesh_asset": component_asset_path(weapon_mesh),
            "slot_bindings": slot_bindings,
            "applied_slot_bindings": applied_slot_bindings,
            "managed_components_by_slot": managed_components_by_slot,
            "slot_attach_state": slot_attach_state,
            "slot_conflicts": slot_conflicts,
            "superseded_bindings": slot_conflicts,
            "required_slots": required_slots,
            "equipment_diagnostics": pmx_equipment_diagnostics(pmx_component, primary_mesh),
            "warnings": warnings,
            "errors": sorted(set(failed_requirements)),
        }
    finally:
        try:
            actor_subsystem.destroy_actor(spawned_host)
        except Exception:
            pass


def list_assets(request: dict) -> dict:
    asset_path = request.get("asset_path") or request.get("asset_root") or "/Game"
    recursive = bool(request.get("recursive", True))
    limit = int(request.get("limit") or 200)

    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    assets = list(registry.get_assets_by_path(to_name(asset_path), recursive=recursive))
    entries = []
    for asset_data in assets[:limit]:
        entries.append(
            {
                "object_path": asset_object_path(asset_data),
                "package_name": str(asset_data.package_name),
                "package_path": str(asset_data.package_path),
                "asset_name": str(asset_data.asset_name),
                "asset_class": asset_class_name(asset_data),
            }
        )
    warnings = []
    if len(assets) > limit:
        warnings.append(f"result_truncated_to_{limit}")
    return {
        "asset_path": asset_path,
        "recursive": recursive,
        "total_count": len(assets),
        "returned_count": len(entries),
        "assets": entries,
        "warnings": warnings,
        "errors": [],
    }


def inspect_host(request: dict) -> dict:
    asset_root = request.get("asset_root") or "/Game"
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    root_assets = list(registry.get_assets_by_path(to_name(asset_root), recursive=True))
    startup_map = None
    if hasattr(unreal.Paths, "get_project_file_path"):
        project_file_path = unreal.Paths.get_project_file_path()
    else:
        project_file_path = ""
    if hasattr(unreal.SystemLibrary, "get_project_content_directory"):
        project_content_dir = unreal.SystemLibrary.get_project_content_directory()
    else:
        project_content_dir = unreal.Paths.project_content_dir()
    try:
        game_maps = unreal.GameMapsSettings.get_game_maps_settings()
        startup_map = game_maps.get_editor_startup_map()
    except Exception:
        startup_map = None
    plugin_root = Path(unreal.Paths.project_plugins_dir()) / "AiUEPmxRuntime"
    return {
        "project_file_path": project_file_path,
        "project_content_dir": project_content_dir,
        "project_saved_dir": unreal.Paths.project_saved_dir(),
        "project_plugins_dir": unreal.Paths.project_plugins_dir(),
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "asset_root": asset_root,
        "asset_root_exists": unreal.EditorAssetLibrary.does_directory_exist(asset_root),
        "asset_count_under_root": len(root_assets),
        "startup_map": startup_map,
        "aiue_pmx_runtime_plugin_root": str(plugin_root.resolve()),
        "aiue_pmx_runtime_plugin_installed": plugin_root.exists(),
        "native_runtime_available": hasattr(unreal, "PMXCharacterHost") and hasattr(unreal, "PMXCharacterEquipmentComponent"),
        "python_script_plugin_enabled": True,
        "warnings": [],
        "errors": [],
    }


def debug_physics_api(_: dict) -> dict:
    payload = {
        "physics_asset_utils_present": hasattr(unreal, "PhysicsAssetUtils"),
        "physics_asset_factory_present": hasattr(unreal, "PhysicsAssetFactory"),
        "editor_skeletal_mesh_library_present": hasattr(unreal, "EditorSkeletalMeshLibrary"),
        "physics_asset_utils_methods": [],
        "physics_asset_factory_members": [],
        "editor_skeletal_mesh_library_methods": [],
    }
    if hasattr(unreal, "PhysicsAssetUtils"):
        payload["physics_asset_utils_methods"] = sorted(
            name for name in dir(unreal.PhysicsAssetUtils) if not name.startswith("_")
        )
    if hasattr(unreal, "PhysicsAssetFactory"):
        payload["physics_asset_factory_members"] = sorted(
            name for name in dir(unreal.PhysicsAssetFactory) if not name.startswith("_")
        )
    if hasattr(unreal, "EditorSkeletalMeshLibrary"):
        payload["editor_skeletal_mesh_library_methods"] = sorted(
            name for name in dir(unreal.EditorSkeletalMeshLibrary) if not name.startswith("_")
        )
    payload["warnings"] = []
    payload["errors"] = []
    return payload
