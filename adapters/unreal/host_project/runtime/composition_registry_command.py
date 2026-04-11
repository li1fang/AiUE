from __future__ import annotations
from .common import *
from .composition_registry import *

def build_equipment_registry(request: dict) -> dict:
    registry_json = request.get("registry_json")
    if registry_json:
        registry_path = Path(registry_json).expanduser().resolve()
    else:
        conversion_root = Path(request["conversion_root"]).expanduser().resolve()
        registry_path = find_latest_registry_json(conversion_root)
    registry_payload = read_json(registry_path)
    asset_root = request.get("asset_root") or registry_payload.get("asset_root") or "/Game/PMXPipeline"
    suite_name, suite_slug = derive_suite_identity(registry_path, registry_payload, request)
    report_path = Path(request.get("report_path") or registry_path.with_name("ue_equipment_assets_report.local.json")).expanduser().resolve()
    shared_blueprints, shared_blueprint_warnings = ensure_shared_blueprint_assets(asset_root)
    pair_asset_records = []
    pair_assets = []
    pair_assets_by_id = {}
    for index, pair in enumerate(registry_payload.get("ready_pairs") or [], start=1):
        package_path, asset_name = pair_asset_path(asset_root, suite_slug, index, pair.get("sample_id") or f"pair_{index:03d}")
        asset, object_path, created = create_or_load_data_asset(asset_name, package_path, unreal.PMXEquipmentPairAsset)
        enriched_pair = dict(pair)
        enriched_pair["pair_id"] = pair_id_for(pair.get("character_package_id"), pair.get("weapon_package_id"))
        configure_pair_asset(asset, enriched_pair)
        pair_assets.append(asset)
        pair_assets_by_id[enriched_pair["pair_id"]] = asset
        pair_asset_records.append({
            "pair_id": enriched_pair["pair_id"],
            "asset_path": object_path.rsplit(".", 1)[0],
            "sample_id": pair.get("sample_id"),
            "character_package_id": pair.get("character_package_id"),
            "weapon_package_id": pair.get("weapon_package_id"),
            "equip_slot": pair.get("equip_slot"),
            "preferred_attach_target": pair.get("preferred_attach_target"),
            "slot_bindings": pair_slot_bindings(enriched_pair),
            "created": created,
        })
    loadout_asset_records = []
    loadout_assets = []
    runtime_preview_checks = []
    loadout_assets_by_character_package_id = {}
    ready_pair_groups: dict[str, list[dict]] = {}
    for pair in registry_payload.get("ready_pairs") or []:
        key = str(pair.get("character_package_id") or "")
        ready_pair_groups.setdefault(key, []).append(dict(pair, pair_id=pair_id_for(pair.get("character_package_id"), pair.get("weapon_package_id"))))
    for index, character in enumerate(registry_payload.get("characters") or [], start=1):
        package_path, asset_name = loadout_asset_path(asset_root, suite_slug, index, character.get("sample_id") or f"character_{index:03d}")
        asset, object_path, created = create_or_load_data_asset(asset_name, package_path, unreal.PMXEquipmentLoadoutAsset)
        related_pairs = ready_pair_groups.get(str(character.get("package_id") or ""), [])
        related_pair_assets = [pair_assets_by_id[pair["pair_id"]] for pair in related_pairs if pair["pair_id"] in pair_assets_by_id]
        default_pair_asset = related_pair_assets[0] if related_pair_assets else None
        configure_loadout_asset(asset, character, default_pair_asset, related_pair_assets, related_pairs)
        loadout_assets.append(asset)
        preview_result = validate_runtime_loadout(asset, object_path.rsplit(".", 1)[0]) if request.get("run_preview_validation", True) else {
            "loadout_asset_path": object_path.rsplit(".", 1)[0],
            "status": "skipped",
            "warnings": ["runtime_preview_validation_disabled"],
            "errors": [],
        }
        runtime_preview_checks.append(preview_result)
        default_pair = related_pairs[0] if related_pairs else {}
        default_attach_target = default_pair.get("preferred_attach_target") or {}
        slot_bindings = loadout_slot_bindings(related_pairs)
        loadout_asset_records.append({
            "sample_id": character.get("sample_id"),
            "character_package_id": character.get("package_id"),
            "loadout_asset_path": object_path.rsplit(".", 1)[0],
            "default_weapon_package_id": default_pair.get("weapon_package_id") or "",
            "default_equip_slot": default_pair.get("equip_slot") or "weapon",
            "default_attach_type": default_attach_target.get("type") or "",
            "default_attach_name": default_attach_target.get("name") or "",
            "ready_pair_ids": [pair["pair_id"] for pair in related_pairs],
            "available_weapon_package_ids": [pair.get("weapon_package_id") for pair in related_pairs if pair.get("weapon_package_id")],
            "warnings": list(character.get("warnings") or []) + list(preview_result.get("warnings") or []),
            "consumer_ready": bool(character.get("consumer_ready")),
            "has_ready_weapon_pairs": bool(related_pairs),
            "default_pair_asset_path": f"{pair_asset_records[[entry['pair_id'] for entry in pair_asset_records].index(default_pair['pair_id'])]['asset_path']}.{Path(pair_asset_records[[entry['pair_id'] for entry in pair_asset_records].index(default_pair['pair_id'])]['asset_path']).name}" if default_pair else "",
            "character_skeletal_mesh": character.get("skeletal_mesh") or "",
            "character_skeleton": character.get("skeleton") or "",
            "character_physics_asset": character.get("physics_asset") or "",
            "default_weapon_skeletal_mesh": default_pair.get("weapon_skeletal_mesh") or "",
            "weapon_mesh_paths": [pair.get("weapon_skeletal_mesh") for pair in related_pairs if pair.get("weapon_skeletal_mesh")],
            "slot_bindings": slot_bindings,
            "applied_slot_bindings": list(preview_result.get("applied_slot_bindings") or []),
            "managed_components_by_slot": dict(preview_result.get("managed_components_by_slot") or {}),
            "slot_attach_state": list(preview_result.get("slot_attach_state") or []),
            "slot_conflicts": list(preview_result.get("slot_conflicts") or []),
            "pair_asset_paths": [
                f"{pair_asset_records[[entry['pair_id'] for entry in pair_asset_records].index(pair['pair_id'])]['asset_path']}.{Path(pair_asset_records[[entry['pair_id'] for entry in pair_asset_records].index(pair['pair_id'])]['asset_path']).name}"
                for pair in related_pairs
                if pair["pair_id"] in [entry["pair_id"] for entry in pair_asset_records]
            ],
            "created": created,
        })
        loadout_assets_by_character_package_id[str(character.get("package_id") or "")] = asset
    component_blueprint_records = []
    component_blueprints_by_character_package_id = {}
    for index, loadout_record in enumerate(loadout_asset_records, start=1):
        asset_path = component_blueprint_path(asset_root, suite_slug, index, loadout_record.get("sample_id") or f"component_{index:03d}")
        blueprint, _, created = create_or_load_blueprint(asset_path, unreal.PMXCharacterEquipmentComponent)
        configure_component_blueprint(
            blueprint,
            loadout_record.get("slot_bindings") or [],
            loadout_record.get("default_weapon_skeletal_mesh"),
            loadout_record.get("default_attach_name") or "WeaponSocket",
        )
        component_blueprints_by_character_package_id[str(loadout_record.get("character_package_id") or "")] = blueprint
        component_blueprint_records.append({
            "sample_id": loadout_record.get("sample_id"),
            "character_package_id": loadout_record.get("character_package_id"),
            "asset_path": asset_path,
            "loadout_asset_path": loadout_record.get("loadout_asset_path"),
            "default_weapon_package_id": loadout_record.get("default_weapon_package_id") or "",
            "consumer_ready": bool(loadout_record.get("consumer_ready")),
            "has_ready_weapon_pairs": bool(loadout_record.get("has_ready_weapon_pairs")),
            "slot_bindings": list(loadout_record.get("slot_bindings") or []),
            "parent_class": str(unreal.PMXCharacterEquipmentComponent),
            "native_runtime_available": True,
            "created": created,
        })
    host_blueprint_records = []
    host_runtime_checks = []
    for index, loadout_record in enumerate(loadout_asset_records, start=1):
        character_package_id = str(loadout_record.get("character_package_id") or "")
        asset_path = host_blueprint_path(asset_root, suite_slug, index, loadout_record.get("sample_id") or f"host_{index:03d}")
        blueprint, _, created = create_or_load_blueprint(asset_path, unreal.PMXCharacterHost)
        loadout_asset = loadout_assets_by_character_package_id.get(character_package_id)
        component_blueprint = component_blueprints_by_character_package_id.get(character_package_id)
        configure_host_blueprint(blueprint, loadout_record.get("character_skeletal_mesh"), loadout_asset, component_blueprint)
        host_validation = validate_host_blueprint(
            blueprint,
            asset_path,
            loadout_asset,
            loadout_record,
            next((entry["asset_path"] for entry in component_blueprint_records if entry["character_package_id"] == character_package_id), ""),
        )
        host_runtime_checks.append(host_validation)
        host_blueprint_records.append({
            "sample_id": loadout_record.get("sample_id"),
            "character_package_id": character_package_id,
            "asset_path": asset_path,
            "loadout_asset_path": loadout_record.get("loadout_asset_path"),
            "component_blueprint_asset_path": next((entry["asset_path"] for entry in component_blueprint_records if entry["character_package_id"] == character_package_id), ""),
            "default_weapon_package_id": loadout_record.get("default_weapon_package_id") or "",
            "default_weapon_skeletal_mesh": loadout_record.get("default_weapon_skeletal_mesh") or "",
            "consumer_ready": bool(loadout_record.get("consumer_ready")),
            "has_ready_weapon_pairs": bool(loadout_record.get("has_ready_weapon_pairs")),
            "has_runtime_weapon_mesh_component": bool(host_validation.get("has_runtime_weapon_mesh_component")),
            "default_weapon_component_name": host_validation.get("default_weapon_component_name") or "DefaultWeaponMeshComponent",
            "default_weapon_component_created": False,
            "default_weapon_component_attach_ok": bool(host_validation.get("default_weapon_component_attach_ok", False)),
            "default_weapon_component_attach_parent": host_validation.get("default_weapon_component_attach_parent") or "CharacterMesh0",
            "default_weapon_component_attach_socket_name": host_validation.get("default_weapon_component_attach_socket_name") or "WeaponSocket",
            "slot_bindings": list(host_validation.get("slot_bindings") or loadout_record.get("slot_bindings") or []),
            "applied_slot_bindings": list(host_validation.get("applied_slot_bindings") or []),
            "managed_components_by_slot": dict(host_validation.get("managed_components_by_slot") or {}),
            "slot_attach_state": list(host_validation.get("slot_attach_state") or []),
            "slot_conflicts": list(host_validation.get("slot_conflicts") or []),
            "equipment_component_parent_class": str(unreal.PMXCharacterEquipmentComponent),
            "native_runtime_available": True,
            "created": created,
        })
    registry_package_path, registry_asset_name = registry_asset_path(asset_root, suite_slug)
    registry_asset, registry_object_path, registry_created = create_or_load_data_asset(registry_asset_name, registry_package_path, unreal.PMXEquipmentRegistryAsset)
    configure_registry_asset(registry_asset, suite_name, suite_slug, pair_assets, loadout_assets)
    save_directory(f"{asset_root}/Registry/Suites/{suite_slug}")
    save_directory(f"{asset_root}/Registry/Blueprints")
    counts = {
        "pair_assets": len(pair_asset_records),
        "loadout_assets": len(loadout_asset_records),
        "component_blueprints": len(component_blueprint_records),
        "host_blueprints": len(host_blueprint_records),
        "registry_assets": 1,
        "character_mesh_refs": len(loadout_asset_records),
        "weapon_mesh_refs": sum(1 for entry in loadout_asset_records if entry["default_weapon_skeletal_mesh"]),
        "slot_binding_refs": sum(len(entry.get("slot_bindings") or []) for entry in loadout_asset_records),
        "ready_pairs": len(pair_asset_records),
        "ready_character_loadouts": sum(1 for entry in loadout_asset_records if entry["has_ready_weapon_pairs"]),
        "ready_component_blueprints": sum(1 for entry in component_blueprint_records if entry["has_ready_weapon_pairs"]),
        "ready_host_blueprints": sum(1 for entry in host_blueprint_records if entry["has_ready_weapon_pairs"]),
        "runtime_ready_host_blueprints": sum(1 for entry in host_blueprint_records if entry["has_runtime_weapon_mesh_component"]),
        "native_runtime_component_blueprints": len(component_blueprint_records),
        "runtime_preview_pass": sum(1 for entry in runtime_preview_checks if entry["status"] == "pass"),
        "runtime_preview_fail": sum(1 for entry in runtime_preview_checks if entry["status"] == "fail"),
        "runtime_preview_skipped": sum(1 for entry in runtime_preview_checks if entry["status"] == "skipped"),
    }
    warnings = list(shared_blueprint_warnings)
    preview_failures = [entry for entry in runtime_preview_checks if entry["status"] == "fail"]
    if preview_failures:
        warnings.append(f"runtime_preview_failures:{len(preview_failures)}")
    host_failures = [entry for entry in host_runtime_checks if entry["status"] == "fail"]
    if host_failures:
        warnings.append(f"host_runtime_failures:{len(host_failures)}")
    report_payload = {
        "generated_at_utc": now_utc(),
        "suite_name": suite_name,
        "suite_slug": suite_slug,
        "asset_root": asset_root,
        "registry_json_path": str(registry_path),
        **shared_blueprints,
        "third_person_character_blueprint_asset": "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter",
        "native_runtime_available": hasattr(unreal, "PMXCharacterEquipmentComponent") and hasattr(unreal, "PMXEquipmentBlueprintLibrary"),
        "native_runtime_component_class": "PMXCharacterEquipmentComponent",
        "registry_asset": registry_object_path.rsplit(".", 1)[0],
        "pair_assets": pair_asset_records,
        "loadout_assets": loadout_asset_records,
        "runtime_preview_checks": runtime_preview_checks,
        "component_blueprints": component_blueprint_records,
        "host_blueprints": host_blueprint_records,
        "warnings": warnings,
        "counts": counts,
    }
    write_json(report_path, report_payload)
    return {
        **report_payload,
        "report_path": str(report_path),
        "registry_asset_object_path": registry_object_path,
        "created": registry_created,
        "errors": [],
    }

__all__ = ["build_equipment_registry"]
