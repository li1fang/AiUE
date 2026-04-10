from __future__ import annotations

from .common import *
def load_existing_import_blueprint(manifest_path: Path) -> dict:
    candidate = manifest_path.parent / "ue_import_report.json"
    if candidate.exists():
        return read_json(candidate)
    return {}


def resolve_texture_files(manifest_path: Path, manifest: dict, output_fbx: Path) -> list[Path]:
    textures_dir = output_fbx.parent / "textures"
    resolved = []
    seen = set()
    for entry in manifest.get("textures", []):
        relocated = resolve_manifest_artifact(manifest_path, entry.get("relocated_path"))
        source = resolve_manifest_artifact(manifest_path, entry.get("original_path"))
        chosen = relocated if relocated and relocated.exists() else source
        if not chosen or not chosen.exists() or not chosen.is_file():
            continue
        key = str(chosen).lower()
        if key in seen:
            continue
        seen.add(key)
        resolved.append(chosen)
    if resolved:
        return resolved
    if textures_dir.exists():
        return [path for path in sorted(textures_dir.iterdir()) if path.is_file()]
    return []


def classify_imported_assets(object_paths: list[str]) -> dict:
    result = {
        "skeletal_mesh": None,
        "skeleton": None,
        "physics_asset": None,
        "textures": [],
        "other": [],
    }
    for object_path in object_paths:
        class_name = load_asset_class_name(object_path)
        if class_name == "SkeletalMesh" and not result["skeletal_mesh"]:
            result["skeletal_mesh"] = object_path
        elif class_name == "Skeleton" and not result["skeleton"]:
            result["skeleton"] = object_path
        elif class_name == "PhysicsAsset" and not result["physics_asset"]:
            result["physics_asset"] = object_path
        elif class_name == "Texture2D":
            result["textures"].append(object_path)
        else:
            result["other"].append(object_path)
    return result


def path_for_loaded_asset(asset) -> str | None:
    if not asset:
        return None
    try:
        return unreal.EditorAssetLibrary.get_path_name_for_loaded_asset(asset)
    except Exception:
        return None


def enrich_related_assets(imported_assets: dict, mesh_destination: str, mesh_name: str) -> dict:
    skeletal_mesh_path = imported_assets.get("skeletal_mesh")
    if not skeletal_mesh_path:
        expected_mesh = f"{mesh_destination}/{mesh_name}.{mesh_name}"
        if unreal.EditorAssetLibrary.does_asset_exist(expected_mesh):
            imported_assets["skeletal_mesh"] = expected_mesh
            skeletal_mesh_path = expected_mesh
    if not skeletal_mesh_path:
        return imported_assets

    skeletal_mesh = unreal.EditorAssetLibrary.load_asset(skeletal_mesh_path)
    if skeletal_mesh:
        if not imported_assets.get("skeleton"):
            imported_assets["skeleton"] = path_for_loaded_asset(skeletal_mesh.get_editor_property("skeleton"))
        if not imported_assets.get("physics_asset"):
            imported_assets["physics_asset"] = path_for_loaded_asset(skeletal_mesh.get_editor_property("physics_asset"))

    if not imported_assets.get("skeleton"):
        expected_skeleton = f"{mesh_destination}/{mesh_name}_Skeleton.{mesh_name}_Skeleton"
        if unreal.EditorAssetLibrary.does_asset_exist(expected_skeleton):
            imported_assets["skeleton"] = expected_skeleton
    if not imported_assets.get("physics_asset"):
        expected_physics = f"{mesh_destination}/{mesh_name}_PhysicsAsset.{mesh_name}_PhysicsAsset"
        if unreal.EditorAssetLibrary.does_asset_exist(expected_physics):
            imported_assets["physics_asset"] = expected_physics
    return imported_assets


def import_skeletal_mesh(output_fbx: Path, mesh_destination: str, create_physics_asset: bool) -> dict:
    ensure_directory(mesh_destination)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(output_fbx))
    task.set_editor_property("destination_path", mesh_destination)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("replace_existing_settings", True)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("options", build_fbx_import_options(create_physics_asset))
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported = list(task.get_editor_property("imported_object_paths") or [])
    return classify_imported_assets(imported)


def material_slot_names(skeletal_mesh_path: str | None) -> list[str]:
    if not skeletal_mesh_path:
        return []
    skeletal_mesh = unreal.EditorAssetLibrary.load_asset(skeletal_mesh_path)
    if not skeletal_mesh:
        return []
    names = []
    for material in skeletal_mesh.get_editor_property("materials") or []:
        try:
            names.append(str(material.get_editor_property("material_slot_name")))
        except Exception:
            pass
    return names


def create_physics_asset_for_mesh(skeletal_mesh_path: str | None, skeleton_path: str | None, mesh_destination: str, mesh_name: str) -> str | None:
    if not skeletal_mesh_path:
        return None
    skeletal_mesh = unreal.EditorAssetLibrary.load_asset(skeletal_mesh_path)
    skeleton = unreal.EditorAssetLibrary.load_asset(skeleton_path) if skeleton_path else None
    if not skeletal_mesh:
        return None

    if hasattr(unreal, "EditorSkeletalMeshLibrary") and hasattr(unreal.EditorSkeletalMeshLibrary, "create_physics_asset"):
        try:
            created = unreal.EditorSkeletalMeshLibrary.create_physics_asset(skeletal_mesh)
            if created:
                if not isinstance(created, bool):
                    save_loaded_asset(created)
                    return unreal.EditorAssetLibrary.get_path_name_for_loaded_asset(created)
                save_loaded_asset(skeletal_mesh)
                linked_asset = skeletal_mesh.get_editor_property("physics_asset")
                if linked_asset:
                    save_loaded_asset(linked_asset)
                    return unreal.EditorAssetLibrary.get_path_name_for_loaded_asset(linked_asset)
        except Exception:
            pass

    if hasattr(unreal, "PhysicsAssetUtils"):
        for method_name in ("create_from_skeletal_mesh", "create_physics_asset"):
            if not hasattr(unreal.PhysicsAssetUtils, method_name):
                continue
            method = getattr(unreal.PhysicsAssetUtils, method_name)
            try:
                created = method(skeletal_mesh)
                if created:
                    save_loaded_asset(created)
                    return unreal.EditorAssetLibrary.get_path_name_for_loaded_asset(created)
            except Exception:
                pass

    if hasattr(unreal, "PhysicsAssetFactory"):
        try:
            factory = unreal.PhysicsAssetFactory()
            set_if_present(factory, "target_skeletal_mesh", skeletal_mesh)
            set_if_present(factory, "preview_skeletal_mesh", skeletal_mesh)
            if skeleton:
                set_if_present(factory, "target_skeleton", skeleton)
            asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                f"{mesh_name}_PhysicsAsset",
                mesh_destination,
                unreal.PhysicsAsset,
                factory,
            )
            if asset:
                set_if_present(skeletal_mesh, "physics_asset", asset)
                save_loaded_asset(asset)
                save_loaded_asset(skeletal_mesh)
                return unreal.EditorAssetLibrary.get_path_name_for_loaded_asset(asset)
        except Exception:
            pass
    return None



    return f"{character_package_id or 'character'}_{weapon_package_id or 'weapon'}"


def derive_suite_identity(registry_path: Path, registry_payload: dict, request: dict) -> tuple[str, str]:
    if request.get("suite_name"):
        suite_name = str(request["suite_name"])
    else:
        suite_file = registry_payload.get("suite_file")
        suite_name = Path(suite_file).stem if suite_file else registry_path.parent.parent.name
    suite_slug = str(request.get("suite_slug") or sanitize_segment(suite_name))
    return suite_name, suite_slug


def find_latest_registry_json(conversion_root: Path) -> Path:
    candidates = sorted(conversion_root.rglob("ue_equipment_registry.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No ue_equipment_registry.json found under {conversion_root}")
    return candidates[0]


def create_or_load_data_asset(asset_name: str, package_path: str, asset_class):
    ensure_directory(package_path)
    object_path = f"{package_path}/{asset_name}.{asset_name}"
    if unreal.EditorAssetLibrary.does_asset_exist(object_path):
        asset = unreal.EditorAssetLibrary.load_asset(object_path)
        return asset, object_path, False

    factory = unreal.DataAssetFactory()
    set_if_present(factory, "data_asset_class", asset_class)
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(asset_name, package_path, asset_class, factory)
    if not asset:
        raise RuntimeError(f"Failed to create asset at {object_path}")
    return asset, object_path, True


def loadout_asset_path(asset_root: str, suite_slug: str, index: int, sample_id: str) -> tuple[str, str]:
    package_path = f"{asset_root}/Registry/Suites/{suite_slug}/Characters"
    asset_name = f"DA_PMXCharacterLoadout_{index:03d}_{sanitize_segment(sample_id)}"
    return package_path, asset_name


def pair_asset_path(asset_root: str, suite_slug: str, index: int, sample_id: str) -> tuple[str, str]:
    package_path = f"{asset_root}/Registry/Suites/{suite_slug}/Pairs"
    asset_name = f"DA_PMXEquipmentPair_{index:03d}_{sanitize_segment(sample_id)}"
    return package_path, asset_name


def registry_asset_path(asset_root: str, suite_slug: str) -> tuple[str, str]:
    package_path = f"{asset_root}/Registry/Suites/{suite_slug}"
    asset_name = f"DA_PMXEquipmentRegistry_{suite_slug}"
    return package_path, asset_name


def component_blueprint_path(asset_root: str, suite_slug: str, index: int, sample_id: str) -> str:
    return f"{asset_root}/Registry/Suites/{suite_slug}/Components/BP_PMXCharacterEquipmentComponent_{index:03d}_{sanitize_segment(sample_id)}"


def host_blueprint_path(asset_root: str, suite_slug: str, index: int, sample_id: str) -> str:
    return f"{asset_root}/Registry/Suites/{suite_slug}/Hosts/BP_PMXCharacterHost_{index:03d}_{sanitize_segment(sample_id)}"



    asset_name = asset_name_from_path(asset_path)
    return f"{asset_path}.{asset_name}"


def create_or_load_blueprint(asset_path: str, parent_class):
    object_path = object_path_from_asset_path(asset_path)
    if unreal.EditorAssetLibrary.does_asset_exist(object_path):
        blueprint = unreal.EditorAssetLibrary.load_asset(object_path)
        return blueprint, object_path, False

    package_path = asset_path.rsplit("/", 1)[0]
    ensure_directory(package_path)
    blueprint = unreal.BlueprintEditorLibrary.create_blueprint_asset_with_parent(asset_path, parent_class)
    if not blueprint:
        raise RuntimeError(f"Failed to create blueprint at {asset_path}")
    return blueprint, object_path, True


def compile_blueprint_asset(blueprint) -> None:
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    save_loaded_asset(blueprint)


def blueprint_generated_class(blueprint):
    generated_class = unreal.BlueprintEditorLibrary.generated_class(blueprint)
    if not generated_class:
        compile_blueprint_asset(blueprint)
        generated_class = unreal.BlueprintEditorLibrary.generated_class(blueprint)
    return generated_class


def blueprint_cdo(blueprint):
    generated_class = blueprint_generated_class(blueprint)
    if not generated_class:
        return None
    return unreal.get_default_object(generated_class)


def ensure_shared_blueprint_assets(asset_root: str) -> tuple[dict, list[str]]:
    definitions = [
        ("registry_blueprint_asset", f"{asset_root}/Registry/Blueprints/BP_PMXEquipmentRegistryAsset", unreal.PMXEquipmentRegistryAsset),
        ("pair_blueprint_asset", f"{asset_root}/Registry/Blueprints/BP_PMXEquipmentPairAsset", unreal.PMXEquipmentPairAsset),
        ("loadout_blueprint_asset", f"{asset_root}/Registry/Blueprints/BP_PMXCharacterEquipmentLoadoutAsset", unreal.PMXEquipmentLoadoutAsset),
        ("component_blueprint_asset", f"{asset_root}/Registry/Blueprints/BP_PMXCharacterEquipmentComponent", unreal.PMXCharacterEquipmentComponent),
        ("host_character_blueprint_asset", f"{asset_root}/Registry/Blueprints/BP_PMXCharacterHost", unreal.PMXCharacterHost),
    ]
    payload = {}
    warnings = []
    for key, asset_path, parent_class in definitions:
        try:
            blueprint, _, _ = create_or_load_blueprint(asset_path, parent_class)
            compile_blueprint_asset(blueprint)
            payload[key] = asset_path
        except Exception as exc:
            payload[key] = None
            warnings.append(f"shared_blueprint_create_failed:{key}:{exc}")
    return payload, warnings


def configure_pair_asset(asset, pair: dict) -> None:
    entry = asset.get_editor_property("pair")
    set_if_present(entry, "sample_id", str(pair.get("sample_id") or ""))
    set_if_present(entry, "pair_id", str(pair.get("pair_id") or pair_id_for(pair.get("character_package_id"), pair.get("weapon_package_id"))))
    set_if_present(entry, "character_package_id", str(pair.get("character_package_id") or ""))
    set_if_present(entry, "weapon_package_id", str(pair.get("weapon_package_id") or ""))
    set_if_present(entry, "character_mesh", load_asset(pair.get("character_skeletal_mesh")))
    set_if_present(entry, "weapon_mesh", load_asset(pair.get("weapon_skeletal_mesh")))
    set_if_present(entry, "equip_slot", pair.get("equip_slot") or "weapon")
    attach_target = pair.get("preferred_attach_target") or {}
    set_if_present(entry, "attach_socket_name", attach_target.get("name") or "WeaponSocket")
    set_if_present(entry, "b_consumer_ready", True)
    set_if_present(entry, "consumer_ready", True)
    asset.set_editor_property("pair", entry)
    save_loaded_asset(asset)


def configure_loadout_asset(asset, character: dict, default_pair_asset, related_pair_assets: list, related_pairs: list[dict]) -> None:
    loadout = asset.get_editor_property("loadout")
    default_pair = related_pairs[0] if related_pairs else {}
    set_if_present(loadout, "sample_id", str(character.get("sample_id") or ""))
    set_if_present(loadout, "character_package_id", str(character.get("package_id") or ""))
    set_if_present(loadout, "default_weapon_package_id", str(default_pair.get("weapon_package_id") or ""))
    set_if_present(loadout, "character_mesh", load_asset(character.get("skeletal_mesh")))
    set_if_present(loadout, "weapon_mesh", load_asset(default_pair.get("weapon_skeletal_mesh")))
    set_if_present(loadout, "equip_slot", default_pair.get("equip_slot") or "weapon")
    attach_target = default_pair.get("preferred_attach_target") or {}
    set_if_present(loadout, "attach_socket_name", attach_target.get("name") or "WeaponSocket")
    set_if_present(loadout, "default_pair_asset", default_pair_asset)
    set_if_present(loadout, "available_pair_assets", related_pair_assets)
    set_if_present(loadout, "available_weapon_package_ids", [str(pair.get("weapon_package_id") or "") for pair in related_pairs if pair.get("weapon_package_id")])
    set_if_present(loadout, "b_consumer_ready", bool(character.get("consumer_ready")))
    set_if_present(loadout, "consumer_ready", bool(character.get("consumer_ready")))
    asset.set_editor_property("loadout", loadout)
    save_loaded_asset(asset)


def configure_registry_asset(asset, suite_name: str, suite_slug: str, pair_assets: list, loadout_assets: list) -> None:
    asset.set_editor_property("suite_name", suite_name)
    asset.set_editor_property("suite_slug", suite_slug)
    asset.set_editor_property("pair_assets", pair_assets)
    asset.set_editor_property("character_loadouts", loadout_assets)
    save_loaded_asset(asset)


def validate_runtime_loadout(loadout_asset, asset_path: str) -> dict:
    loadout = loadout_asset.get_editor_property("loadout")
    character_mesh = getattr(loadout, "character_mesh", None)
    weapon_mesh = getattr(loadout, "weapon_mesh", None)
    if not character_mesh or not weapon_mesh:
        return {
            "loadout_asset_path": asset_path,
            "status": "skipped",
            "warnings": ["loadout_missing_character_or_weapon_mesh"],
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

        success = bool(weapon_component and managed_component and desired_weapon_mesh)
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


def configure_component_blueprint(blueprint, weapon_mesh_path: str | None, attach_socket_name: str | None) -> None:
    cdo = blueprint_cdo(blueprint)
    if not cdo:
        raise RuntimeError("Unable to resolve blueprint CDO for component blueprint")
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
        pair_asset_records.append(
            {
                "pair_id": enriched_pair["pair_id"],
                "asset_path": object_path.rsplit(".", 1)[0],
                "sample_id": pair.get("sample_id"),
                "character_package_id": pair.get("character_package_id"),
                "weapon_package_id": pair.get("weapon_package_id"),
                "equip_slot": pair.get("equip_slot"),
                "preferred_attach_target": pair.get("preferred_attach_target"),
                "created": created,
            }
        )

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
        loadout_asset_records.append(
            {
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
                "pair_asset_paths": [
                    f"{pair_asset_records[[entry['pair_id'] for entry in pair_asset_records].index(pair['pair_id'])]['asset_path']}.{Path(pair_asset_records[[entry['pair_id'] for entry in pair_asset_records].index(pair['pair_id'])]['asset_path']).name}"
                    for pair in related_pairs
                    if pair["pair_id"] in [entry["pair_id"] for entry in pair_asset_records]
                ],
                "created": created,
            }
        )
        loadout_assets_by_character_package_id[str(character.get("package_id") or "")] = asset

    component_blueprint_records = []
    component_blueprints_by_character_package_id = {}
    for index, loadout_record in enumerate(loadout_asset_records, start=1):
        asset_path = component_blueprint_path(asset_root, suite_slug, index, loadout_record.get("sample_id") or f"component_{index:03d}")
        blueprint, _, created = create_or_load_blueprint(asset_path, unreal.PMXCharacterEquipmentComponent)
        configure_component_blueprint(
            blueprint,
            loadout_record.get("default_weapon_skeletal_mesh"),
            loadout_record.get("default_attach_name") or "WeaponSocket",
        )
        component_blueprints_by_character_package_id[str(loadout_record.get("character_package_id") or "")] = blueprint
        component_blueprint_records.append(
            {
                "sample_id": loadout_record.get("sample_id"),
                "character_package_id": loadout_record.get("character_package_id"),
                "asset_path": asset_path,
                "loadout_asset_path": loadout_record.get("loadout_asset_path"),
                "default_weapon_package_id": loadout_record.get("default_weapon_package_id") or "",
                "consumer_ready": bool(loadout_record.get("consumer_ready")),
                "has_ready_weapon_pairs": bool(loadout_record.get("has_ready_weapon_pairs")),
                "parent_class": str(unreal.PMXCharacterEquipmentComponent),
                "native_runtime_available": True,
                "created": created,
            }
        )

    host_blueprint_records = []
    host_runtime_checks = []
    for index, loadout_record in enumerate(loadout_asset_records, start=1):
        character_package_id = str(loadout_record.get("character_package_id") or "")
        asset_path = host_blueprint_path(asset_root, suite_slug, index, loadout_record.get("sample_id") or f"host_{index:03d}")
        blueprint, _, created = create_or_load_blueprint(asset_path, unreal.PMXCharacterHost)
        loadout_asset = loadout_assets_by_character_package_id.get(character_package_id)
        component_blueprint = component_blueprints_by_character_package_id.get(character_package_id)
        configure_host_blueprint(
            blueprint,
            loadout_record.get("character_skeletal_mesh"),
            loadout_asset,
            component_blueprint,
        )
        host_validation = validate_host_blueprint(
            blueprint,
            asset_path,
            loadout_asset,
            loadout_record,
            next((entry["asset_path"] for entry in component_blueprint_records if entry["character_package_id"] == character_package_id), ""),
        )
        host_runtime_checks.append(host_validation)
        host_blueprint_records.append(
            {
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
                "equipment_component_parent_class": str(unreal.PMXCharacterEquipmentComponent),
                "native_runtime_available": True,
                "created": created,
            }
        )

    registry_package_path, registry_asset_name = registry_asset_path(asset_root, suite_slug)
    registry_asset, registry_object_path, registry_created = create_or_load_data_asset(
        registry_asset_name,
        registry_package_path,
        unreal.PMXEquipmentRegistryAsset,
    )
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


def derive_import_context(request: dict) -> dict:
    manifest_path = Path(request["manifest"]).expanduser().resolve()
    manifest = read_json(manifest_path)
    output_fbx = resolve_manifest_artifact(manifest_path, manifest.get("output_fbx"))
    if not output_fbx or not output_fbx.exists():
        raise FileNotFoundError(f"Resolved FBX not found for manifest: {manifest_path}")
    asset_root = request.get("asset_root") or "/Game/PMXPipeline"
    existing = load_existing_import_blueprint(manifest_path)
    pipeline_strategy = manifest.get("pipeline_strategy") or {}
    unreal_import_strategy = pipeline_strategy.get("unreal_import") or {}
    unreal_validation_strategy = pipeline_strategy.get("unreal_validation") or {}
    content_bucket = (
        request.get("content_bucket")
        or unreal_import_strategy.get("content_bucket")
        or existing.get("content_bucket")
        or "Characters"
    )
    mesh_name = output_fbx.stem.replace(".", "_")
    asset_label = existing.get("asset_label") or f"{sanitize_segment(manifest.get('sample_id') or output_fbx.parent.name)}_{sanitize_segment(output_fbx.stem)}"
    package_root = remap_asset_root((existing.get("destination_paths") or {}).get("package_root"), asset_root) or f"{asset_root}/{content_bucket}/{asset_label}"
    mesh_destination = remap_asset_root((existing.get("destination_paths") or {}).get("mesh_destination"), asset_root) or f"{package_root}/Meshes"
    texture_destination = remap_asset_root((existing.get("destination_paths") or {}).get("texture_destination"), asset_root) or f"{package_root}/Textures"
    import_report_path = manifest_path.parent / "ue_import_report.local.json"
    validation_report_path = manifest_path.parent / "ue_validation_report.local.json"
    consumer_contract_path = manifest_path.parent / "ue_consumer_contract.json"
    consumer_contract = read_json(consumer_contract_path) if consumer_contract_path.exists() else {}
    texture_files = resolve_texture_files(manifest_path, manifest, output_fbx)
    expected_slot_names = [entry.get("normalized_name") for entry in manifest.get("materials", []) if entry.get("normalized_name")]
    expected_texture_count = len(texture_files)
    create_physics_asset = bool(unreal_import_strategy.get("create_physics_asset", True))
    physics_asset_policy = str(unreal_validation_strategy.get("physics_asset_policy") or "required")
    physics_asset_required = physics_asset_policy.lower() != "optional"
    return {
        "manifest_path": manifest_path,
        "manifest": manifest,
        "output_fbx": output_fbx,
        "asset_root": asset_root,
        "content_bucket": content_bucket,
        "asset_label": asset_label,
        "mesh_name": mesh_name,
        "package_root": package_root,
        "mesh_destination": mesh_destination,
        "texture_destination": texture_destination,
        "import_report_path": import_report_path,
        "validation_report_path": validation_report_path,
        "consumer_contract_path": consumer_contract_path if consumer_contract_path.exists() else None,
        "consumer_contract": consumer_contract,
        "texture_files": texture_files,
        "expected_slot_names": expected_slot_names,
        "expected_texture_count": expected_texture_count,
        "package_role": request.get("package_role") or manifest.get("package_hints", {}).get("package_role") or consumer_contract.get("package_role"),
        "package_id": request.get("package_id") or manifest.get("package_id") or consumer_contract.get("package_id"),
        "source_relative_path": manifest.get("source_relative_path"),
        "pipeline_strategy": pipeline_strategy,
        "create_physics_asset": create_physics_asset,
        "physics_asset_policy": physics_asset_policy,
        "physics_asset_required": physics_asset_required,
        "profile": request.get("profile") or unreal_import_strategy.get("profile"),
    }



def import_package_dry_run(request: dict) -> dict:
    context = derive_import_context(request)
    imported_textures = []
    for texture_file in context["texture_files"]:
        name = texture_file.stem.replace(".", "_")
        imported_textures.append(f"{context['texture_destination']}/{name}.{name}")
    return {
        "manifest_path": str(context["manifest_path"]),
        "source_file": context["manifest"].get("source_file"),
        "sample_id": context["manifest"].get("sample_id"),
        "output_fbx": str(context["output_fbx"]),
        "original_output_fbx": context["manifest"].get("output_fbx"),
        "asset_root": context["asset_root"],
        "asset_label": context["asset_label"],
        "content_bucket": context["content_bucket"],
        "destination_paths": {
            "package_root": context["package_root"],
            "mesh_destination": context["mesh_destination"],
            "texture_destination": context["texture_destination"],
        },
        "imported_assets": {
            "skeletal_mesh": f"{context['mesh_destination']}/{context['mesh_name']}.{context['mesh_name']}",
            "skeleton": f"{context['mesh_destination']}/{context['mesh_name']}_Skeleton.{context['mesh_name']}_Skeleton",
            "physics_asset": (
                f"{context['mesh_destination']}/{context['mesh_name']}_PhysicsAsset.{context['mesh_name']}_PhysicsAsset"
                if context["create_physics_asset"] or context["physics_asset_required"]
                else None
            ),
            "textures": imported_textures,
            "other": [],
        },
        "dry_run": True,
        "warnings": [
            "dry_run_only_no_assets_imported",
            "package_role_and_contract_type_are_inferred_from_local_manifest_context",
        ],
        "errors": [],
    }


def import_package(request: dict) -> dict:
    context = derive_import_context(request)
    ensure_directory(context["package_root"])
    ensure_directory(context["mesh_destination"])
    ensure_directory(context["texture_destination"])

    imported_textures = import_files(context["texture_files"], context["texture_destination"])
    mesh_assets = import_skeletal_mesh(context["output_fbx"], context["mesh_destination"], context["create_physics_asset"])
    mesh_assets = enrich_related_assets(mesh_assets, context["mesh_destination"], context["mesh_name"])
    if (context["create_physics_asset"] or context["physics_asset_required"]) and not mesh_assets["physics_asset"]:
        mesh_assets["physics_asset"] = create_physics_asset_for_mesh(
            mesh_assets["skeletal_mesh"],
            mesh_assets["skeleton"],
            context["mesh_destination"],
            context["mesh_name"],
        )
        mesh_assets = enrich_related_assets(mesh_assets, context["mesh_destination"], context["mesh_name"])

    imported_assets = {
        "skeletal_mesh": mesh_assets["skeletal_mesh"],
        "skeleton": mesh_assets["skeleton"],
        "physics_asset": mesh_assets["physics_asset"],
        "textures": imported_textures,
        "other": mesh_assets["other"],
    }

    save_directory(context["package_root"])
    actual_slot_names = material_slot_names(imported_assets["skeletal_mesh"])
    failures = []
    warnings = []
    if not imported_assets["skeletal_mesh"]:
        failures.append("skeletal_mesh_missing_after_import")
    if not imported_assets["skeleton"]:
        failures.append("skeleton_missing_after_import")
    if context["physics_asset_required"] and not imported_assets["physics_asset"]:
        failures.append("physics_asset_missing_after_import")
    if len(imported_assets["textures"]) < context["expected_texture_count"]:
        warnings.append(f"imported_texture_count_below_expected:{len(imported_assets['textures'])}/{context['expected_texture_count']}")
    missing_slots = [name for name in context["expected_slot_names"] if name not in actual_slot_names]
    if missing_slots:
        warnings.append(f"missing_material_slots:{len(missing_slots)}")

    import_report = {
        "generated_at_utc": now_utc(),
        "sample_id": context["manifest"].get("sample_id"),
        "package_id": context["package_id"],
        "source_file": context["manifest"].get("source_file"),
        "source_relative_path": context["source_relative_path"],
        "manifest_path": str(context["manifest_path"]),
        "output_fbx": str(context["output_fbx"]),
        "profile_path": None,
        "requested_profile": context["profile"],
        "resolved_profile": context["profile"] or "default_skeletal_import",
        "asset_root": context["asset_root"],
        "asset_label": context["asset_label"],
        "content_bucket": context["content_bucket"],
        "package_role": context["package_role"],
        "pipeline_strategy": {
            "unreal_import": context["pipeline_strategy"].get("unreal_import", {}),
            "unreal_validation": context["pipeline_strategy"].get("unreal_validation", {}),
            "risk_level": context["pipeline_strategy"].get("risk_level"),
        },
        "destination_paths": {
            "package_root": context["package_root"],
            "mesh_destination": context["mesh_destination"],
            "texture_destination": context["texture_destination"],
        },
        "imported_assets": imported_assets,
        "warnings": warnings,
        "consumer_contract_path": str(context["consumer_contract_path"]) if context["consumer_contract_path"] else None,
        "consumer_contract_summary": {
            "contract_type": context["consumer_contract"].get("contract_type"),
            "consumer_ready": context["consumer_contract"].get("consumer_ready"),
            "preferred_owner_package_id": context["consumer_contract"].get("preferred_owner_package_id"),
        },
        "bundle_context": context["consumer_contract"].get("bundle_context"),
        "attachment": context["consumer_contract"].get("attachment"),
    }

    validation_report = {
        "generated_at_utc": now_utc(),
        "sample_id": context["manifest"].get("sample_id"),
        "package_id": context["package_id"],
        "source_file": context["manifest"].get("source_file"),
        "source_relative_path": context["source_relative_path"],
        "manifest_path": str(context["manifest_path"]),
        "import_report_path": str(context["import_report_path"]),
        "content_bucket": context["content_bucket"],
        "package_role": context["package_role"],
        "checks": {
            "skeletal_mesh_exists": bool(imported_assets["skeletal_mesh"]),
            "skeleton_exists": bool(imported_assets["skeleton"]),
            "physics_asset_exists": bool(imported_assets["physics_asset"]),
            "physics_asset_required": context["physics_asset_required"],
            "expected_material_slot_names": context["expected_slot_names"],
            "actual_material_slot_names": actual_slot_names,
            "tolerated_missing_material_slots": [],
            "expected_texture_count": context["expected_texture_count"],
            "imported_texture_count": len(imported_assets["textures"]),
        },
        "strategy": {
            "physics_asset_policy": context["physics_asset_policy"],
            "allow_minor_trailing_material_drops": False,
            "minor_trailing_material_candidates": [],
        },
        "consumer": {
            "contract_path": str(context["consumer_contract_path"]) if context["consumer_contract_path"] else None,
            "contract_type": context["consumer_contract"].get("contract_type"),
            "consumer_ready": context["consumer_contract"].get("consumer_ready"),
            "preferred_owner_package_id": context["consumer_contract"].get("preferred_owner_package_id"),
            "preferred_attach_target": context["consumer_contract"].get("preferred_attach_target"),
        },
        "failures": failures,
        "warnings": warnings,
        "score": 100 if not failures and not warnings else 90 if not failures else 0,
        "status": "pass" if not failures else "fail",
    }

    write_json(context["import_report_path"], import_report)
    write_json(context["validation_report_path"], validation_report)

    return {
        **import_report,
        "import_report_path": str(context["import_report_path"]),
        "validation_report_path": str(context["validation_report_path"]),
        "validation_status": validation_report["status"],
        "validation_score": validation_report["score"],
        "dry_run": False,
        "warnings": warnings,
        "errors": failures,
    }




