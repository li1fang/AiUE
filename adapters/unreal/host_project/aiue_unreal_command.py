from __future__ import annotations

import json
import math
import os
import re
import shutil
import sys
import time
import traceback
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import unreal


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def to_name(text: str) -> unreal.Name:
    return unreal.Name(text)


def asset_class_name(asset_data: unreal.AssetData) -> str:
    class_path = asset_data.asset_class_path
    if hasattr(class_path, "asset_name"):
        return str(class_path.asset_name)
    return str(class_path)


def asset_object_path(asset_data: unreal.AssetData) -> str:
    if hasattr(asset_data, "object_path"):
        return str(asset_data.object_path)
    package_name = str(asset_data.package_name)
    asset_name = str(asset_data.asset_name)
    return f"{package_name}.{asset_name}"


def sanitize_segment(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "asset"


def resolve_manifest_artifact(manifest_path: Path, artifact_path: str | None) -> Path | None:
    if not artifact_path:
        return None
    candidate = Path(artifact_path).expanduser()
    if candidate.exists():
        return candidate.resolve()
    local_sibling = manifest_path.parent / candidate.name
    if local_sibling.exists():
        return local_sibling.resolve()
    return candidate.resolve(strict=False)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def remap_asset_root(path: str | None, asset_root: str) -> str | None:
    if not path:
        return path
    parts = path.split("/")
    if len(parts) >= 3 and parts[1] == "Game":
        remainder = "/".join(parts[3:])
        return asset_root.rstrip("/") + ("/" + remainder if remainder else "")
    return path


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


def ensure_directory(path: str) -> None:
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        unreal.EditorAssetLibrary.make_directory(path)


def import_files(file_paths: list[Path], destination_path: str) -> list[str]:
    if not file_paths:
        return []
    ensure_directory(destination_path)
    tasks = []
    for file_path in file_paths:
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", str(file_path))
        task.set_editor_property("destination_path", destination_path)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("replace_existing_settings", True)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    imported = []
    for task in tasks:
        imported.extend(list(task.get_editor_property("imported_object_paths") or []))
    return imported


def set_if_present(obj, property_name: str, value) -> None:
    try:
        obj.set_editor_property(property_name, value)
    except Exception:
        pass


def build_fbx_import_options(create_physics_asset: bool) -> unreal.FbxImportUI:
    options = unreal.FbxImportUI()
    set_if_present(options, "automated_import_should_detect_type", False)
    set_if_present(options, "import_mesh", True)
    set_if_present(options, "import_as_skeletal", True)
    set_if_present(options, "import_animations", False)
    set_if_present(options, "import_materials", False)
    set_if_present(options, "import_textures", False)
    set_if_present(options, "create_physics_asset", create_physics_asset)
    if hasattr(unreal, "FBXImportType"):
        set_if_present(options, "original_import_type", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
        set_if_present(options, "mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    skeletal_data = options.get_editor_property("skeletal_mesh_import_data")
    set_if_present(skeletal_data, "convert_scene", True)
    set_if_present(skeletal_data, "convert_scene_unit", False)
    set_if_present(skeletal_data, "import_uniform_scale", 1.0)
    set_if_present(skeletal_data, "update_skeleton_reference_pose", False)
    set_if_present(skeletal_data, "use_t0_as_ref_pose", True)
    set_if_present(skeletal_data, "preserve_smoothing_groups", True)
    set_if_present(skeletal_data, "import_meshes_in_bone_hierarchy", True)
    return options


def load_asset_class_name(object_path: str) -> str:
    asset = unreal.EditorAssetLibrary.load_asset(object_path)
    if not asset:
        return ""
    return asset.get_class().get_name()


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


def save_directory(path: str) -> None:
    try:
        unreal.EditorAssetLibrary.save_directory(path, only_if_is_dirty=False, recursive=True)
    except Exception:
        pass


def save_loaded_asset(asset) -> None:
    try:
        unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False)
    except Exception:
        pass


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


def load_asset(object_path: str | None):
    if not object_path:
        return None
    return unreal.EditorAssetLibrary.load_asset(object_path)


def pair_id_for(character_package_id: str | None, weapon_package_id: str | None) -> str:
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


def asset_name_from_path(asset_path: str) -> str:
    return asset_path.rstrip("/").split("/")[-1]


def object_path_from_asset_path(asset_path: str) -> str:
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


def serialize_vector(vector) -> dict[str, float]:
    return {
        "x": float(vector.x),
        "y": float(vector.y),
        "z": float(vector.z),
    }


def serialize_rotator(rotator) -> dict[str, float]:
    return {
        "pitch": float(rotator.pitch),
        "yaw": float(rotator.yaw),
        "roll": float(rotator.roll),
    }


def make_rotator(pitch: float = 0.0, yaw: float = 0.0, roll: float = 0.0) -> unreal.Rotator:
    rotator = unreal.Rotator()
    rotator.pitch = float(pitch)
    rotator.yaw = float(yaw)
    rotator.roll = float(roll)
    return rotator


def vector_from_request(value, default: unreal.Vector | None = None) -> unreal.Vector:
    if isinstance(value, unreal.Vector):
        return value
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return unreal.Vector(float(value[0]), float(value[1]), float(value[2]))
    if isinstance(value, dict):
        return unreal.Vector(
            float(value.get("x", 0.0)),
            float(value.get("y", 0.0)),
            float(value.get("z", 0.0)),
        )
    return default or unreal.Vector(0.0, 0.0, 0.0)


def rotator_from_request(value, default: unreal.Rotator | None = None) -> unreal.Rotator:
    if isinstance(value, unreal.Rotator):
        return value
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return make_rotator(float(value[0]), float(value[1]), float(value[2]))
    if isinstance(value, dict):
        return make_rotator(
            float(value.get("pitch", 0.0)),
            float(value.get("yaw", 0.0)),
            float(value.get("roll", 0.0)),
        )
    return default or make_rotator(0.0, 0.0, 0.0)


def editor_actor_subsystem():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def level_editor_subsystem():
    return unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)


def get_current_level_path() -> str:
    try:
        current_level = level_editor_subsystem().get_current_level()
        if current_level:
            return current_level.get_path_name()
    except Exception:
        pass
    world = unreal.EditorLevelLibrary.get_editor_world()
    return world.get_path_name() if world else ""


def find_actor_by_label_or_path(actor_label: str | None = None, actor_path: str | None = None):
    for actor in editor_actor_subsystem().get_all_level_actors():
        try:
            if actor_path and actor.get_path_name() == actor_path:
                return actor
            if actor_label and (actor.get_actor_label() == actor_label or actor.get_name() == actor_label):
                return actor
            if actor_label:
                tags = [str(tag) for tag in (actor.tags or [])]
                if actor_label in tags:
                    return actor
        except Exception:
            continue
    return None


def ensure_actor_tag(actor, tag_value: str) -> None:
    if not actor or not tag_value:
        return
    try:
        existing = [str(tag) for tag in (actor.tags or [])]
        if tag_value in existing:
            return
        actor.tags = list(actor.tags or []) + [to_name(tag_value)]
    except Exception:
        pass


def wait_for_actor_labels(labels: list[str], timeout_seconds: float = 5.0, poll_interval_seconds: float = 0.1) -> bool:
    pending = {str(label) for label in labels if label}
    if not pending:
        return True
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        pending = {label for label in pending if not find_actor_by_label_or_path(actor_label=label)}
        if not pending:
            return True
        time.sleep(poll_interval_seconds)
    return not pending


def snapshot_visible_actors(limit: int = 200) -> list[dict]:
    snapshot = []
    for actor in editor_actor_subsystem().get_all_level_actors():
        try:
            snapshot.append(
                {
                    "label": actor.get_actor_label(),
                    "name": actor.get_name(),
                    "class_name": actor_class_name(actor),
                    "tags": [str(tag) for tag in (actor.tags or [])],
                    "location": serialize_vector(actor.get_actor_location()),
                    "rotation": serialize_rotator(actor.get_actor_rotation()),
                }
            )
        except Exception:
            continue
        if len(snapshot) >= limit:
            break
    return snapshot


def actor_class_name(actor) -> str:
    try:
        return actor.get_class().get_name()
    except Exception:
        return ""


def component_class_name(component) -> str:
    try:
        return component.get_class().get_name()
    except Exception:
        return ""


def summarize_render_components(actor) -> list[dict]:
    records = []
    if not actor:
        return records
    component_sets = []
    for component_class in (getattr(unreal, "PrimitiveComponent", None), getattr(unreal, "ChildActorComponent", None)):
        if component_class is None:
            continue
        try:
            component_sets.extend(list(actor.get_components_by_class(component_class) or []))
        except Exception:
            continue
    components = component_sets
    for component in components or []:
        class_name = component_class_name(component)
        if class_name not in {
            "SkeletalMeshComponent",
            "StaticMeshComponent",
            "ChildActorComponent",
            "CapsuleComponent",
        }:
            continue
        record = {
            "component_name": str(getattr(component, "get_name", lambda: "")() or ""),
            "class_name": class_name,
        }
        for property_name in ("visible", "hidden_in_game", "cast_shadow"):
            try:
                record[property_name] = component.get_editor_property(property_name)
            except Exception:
                continue
        if class_name == "SkeletalMeshComponent":
            try:
                skeletal_mesh = component.get_editor_property("skeletal_mesh_asset")
            except Exception:
                skeletal_mesh = None
            if skeletal_mesh:
                record["asset_path"] = skeletal_mesh.get_path_name()
        if class_name == "StaticMeshComponent":
            try:
                static_mesh = component.get_editor_property("static_mesh")
            except Exception:
                static_mesh = None
            if static_mesh:
                record["asset_path"] = static_mesh.get_path_name()
        try:
            origin, extent = component.bounds.origin, component.bounds.box_extent
            record["bounds_origin"] = serialize_vector(origin)
            record["bounds_extent"] = serialize_vector(extent)
        except Exception:
            pass
        records.append(record)
    return records


def component_world_location(component):
    if not component:
        return None
    for method_name in ("get_world_location", "get_component_location", "k2_get_component_location"):
        if hasattr(component, method_name):
            try:
                return getattr(component, method_name)()
            except Exception:
                continue
    return None


def component_world_rotation(component):
    if not component:
        return None
    for method_name in ("get_world_rotation", "get_component_rotation", "k2_get_component_rotation"):
        if hasattr(component, method_name):
            try:
                return getattr(component, method_name)()
            except Exception:
                continue
    return None


def camera_view_transform(camera_actor) -> tuple[unreal.Vector, unreal.Rotator, str]:
    if camera_actor:
        component = None
        if hasattr(camera_actor, "get_cine_camera_component"):
            try:
                component = camera_actor.get_cine_camera_component()
            except Exception:
                component = None
        if component is None and hasattr(camera_actor, "get_camera_component"):
            try:
                component = camera_actor.get_camera_component()
            except Exception:
                component = None
        component_location = component_world_location(component)
        component_rotation = component_world_rotation(component)
        if component_location is not None and component_rotation is not None:
            return component_location, component_rotation, "camera_component_world_transform"
        return camera_actor.get_actor_location(), camera_actor.get_actor_rotation(), "actor_transform"
    return unreal.Vector(0.0, 0.0, 0.0), make_rotator(0.0, 0.0, 0.0), "fallback_identity"


def serialize_actor_reference(actor, label: str | None = None) -> dict:
    if not actor:
        return {}
    view_location = None
    view_rotation = None
    view_transform_source = ""
    if actor_class_name(actor) in {"CameraActor", "CineCameraActor"}:
        view_location, view_rotation, view_transform_source = camera_view_transform(actor)
    return {
        "label": label or actor.get_actor_label(),
        "actor_label": actor.get_actor_label(),
        "actor_name": actor.get_name(),
        "actor_path": actor.get_path_name(),
        "class_name": actor_class_name(actor),
        "location": serialize_vector(actor.get_actor_location()),
        "rotation": serialize_rotator(actor.get_actor_rotation()),
        "view_location": serialize_vector(view_location) if view_location is not None else {},
        "view_rotation": serialize_rotator(view_rotation) if view_rotation is not None else {},
        "view_transform_source": view_transform_source,
    }


def resolve_stage_anchor_actor(actor_label: str | None, expected_class_name: str, role: str) -> tuple[object | None, dict]:
    if not actor_label:
        return None, {
            "label": "",
            "role": role,
            "expected_class_name": expected_class_name,
            "exists": False,
            "status": "fail",
            "warnings": [],
            "errors": [f"{role}_anchor_label_missing"],
        }

    actor = find_actor_by_label_or_path(actor_label=actor_label)
    if not actor:
        return None, {
            "label": str(actor_label),
            "role": role,
            "expected_class_name": expected_class_name,
            "exists": False,
            "status": "fail",
            "warnings": [],
            "errors": [f"{role}_anchor_missing:{actor_label}"],
        }

    record = serialize_actor_reference(actor, str(actor_label))
    record.update(
        {
            "role": role,
            "expected_class_name": expected_class_name,
            "exists": True,
            "status": "pass",
            "warnings": [],
            "errors": [],
        }
    )
    actual_class_name = record.get("class_name") or ""
    if expected_class_name and actual_class_name != expected_class_name:
        record["status"] = "fail"
        record["errors"] = [f"{role}_anchor_class_mismatch:{actor_label}:{expected_class_name}:{actual_class_name}"]
        return None, record
    return actor, record


def build_anchor_camera_plan(camera_anchor, target_actor, request: dict) -> dict:
    expected_camera_location = request.get("expected_camera_location")
    expected_camera_rotation = request.get("expected_camera_rotation")
    if expected_camera_location and expected_camera_rotation:
        camera_location = vector_from_request(expected_camera_location)
        reference_camera_rotation = rotator_from_request(expected_camera_rotation)
        camera_transform_source = "request_expected_stage_transform"
    else:
        camera_location, reference_camera_rotation, camera_transform_source = camera_view_transform(camera_anchor)
    camera_rotation = reference_camera_rotation
    payload = {
        "camera_source": "anchor_actor",
        "camera_anchor_actor_label": str(request.get("camera_anchor_actor_label") or camera_anchor.get_actor_label()),
        "camera_anchor_actor_path": camera_anchor.get_path_name(),
        "camera_location": serialize_vector(camera_location),
        "camera_rotation": serialize_rotator(camera_rotation),
        "camera_reference_rotation": serialize_rotator(reference_camera_rotation),
        "camera_view_transform_source": camera_transform_source,
        "camera_rotation_source": "anchor_reference_rotation",
        "spawn_anchor_actor_label": str(request.get("spawn_anchor_actor_label") or ""),
    }
    if target_actor:
        origin, extent = actor_bounds(target_actor)
        target_height_offset = float(request.get("target_height_offset") or max(extent.z * 0.65, 90.0))
        look_at_target_location = origin + unreal.Vector(0.0, 0.0, target_height_offset)
        camera_rotation = unreal.MathLibrary.find_look_at_rotation(camera_location, look_at_target_location)
        payload["camera_rotation"] = serialize_rotator(camera_rotation)
        payload["camera_rotation_source"] = "look_at_target_from_fixed_anchor_position"
        payload["look_at_target_location"] = serialize_vector(look_at_target_location)
        payload["target_bounds_origin"] = serialize_vector(origin)
        payload["target_bounds_extent"] = serialize_vector(extent)
        payload.update(
            {
                "target_actor_label": target_actor.get_actor_label(),
                "target_actor_path": target_actor.get_path_name(),
                "target_location": serialize_vector(target_actor.get_actor_location()),
                "target_rotation": serialize_rotator(target_actor.get_actor_rotation()),
            }
        )
    return payload


def stage_anchor_class(anchor_class_name: str):
    class_map = {
        "TargetPoint": getattr(unreal, "TargetPoint", None),
        "CineCameraActor": getattr(unreal, "CineCameraActor", None),
    }
    resolved = class_map.get(anchor_class_name)
    if resolved is None:
        raise ValueError(f"unsupported_stage_anchor_class:{anchor_class_name}")
    return resolved


def save_current_level() -> tuple[bool, list[str]]:
    warnings = []
    try:
        saved = unreal.EditorLevelLibrary.save_current_level()
        if saved:
            return True, warnings
        warnings.append("save_current_level_returned_false")
    except Exception as exc:
        warnings.append(f"save_current_level_failed:{exc}")

    if hasattr(unreal, "EditorLoadingAndSavingUtils"):
        try:
            saved = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
            if saved:
                return True, warnings
            warnings.append("save_dirty_packages_returned_false")
        except Exception as exc:
            warnings.append(f"save_dirty_packages_failed:{exc}")
    return False, warnings


def resolve_equipment_report_path(request: dict) -> Path | None:
    explicit = request.get("report_path")
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if candidate.exists():
            return candidate
    related_paths = [
        request.get("summary"),
        request.get("suite_output"),
        request.get("capture_manifest_output"),
    ]
    sibling_names = [
        "ue_equipment_assets_report.local.json",
        "ue_equipment_assets_report.json",
    ]
    for raw_path in related_paths:
        if not raw_path:
            continue
        base_path = Path(raw_path).expanduser().resolve()
        for candidate_name in sibling_names:
            candidate = base_path.parent / candidate_name
            if candidate.exists():
                return candidate
    return None


def resolve_host_record(request: dict) -> tuple[dict | None, list[str]]:
    warnings = []
    report_path = resolve_equipment_report_path(request)
    if not report_path:
        return None, warnings
    payload = read_json(report_path)
    host_records = list(payload.get("host_blueprints") or [])
    host_asset_path = request.get("host_blueprint_asset_path")
    sample_id = request.get("sample_id")
    character_package_id = request.get("package_id") or request.get("character_package_id")
    runtime_ready_only = bool(request.get("runtime_ready_only"))

    filtered = host_records
    if runtime_ready_only:
        filtered = [record for record in filtered if record.get("has_runtime_weapon_mesh_component")]
    if host_asset_path:
        for record in filtered:
            if record.get("asset_path") == host_asset_path:
                return record, warnings
    if character_package_id:
        for record in filtered:
            if record.get("character_package_id") == character_package_id:
                return record, warnings
    if sample_id:
        for record in filtered:
            if record.get("sample_id") == sample_id:
                return record, warnings
    if runtime_ready_only and filtered:
        warnings.append("host_record_not_specified_defaulted_to_first_runtime_ready_host")
        return filtered[0], warnings
    if filtered:
        warnings.append("host_record_not_specified_defaulted_to_first_available_host")
        return filtered[0], warnings
    return None, warnings


def resolve_host_blueprint_asset_path(request: dict) -> tuple[str, dict | None, list[str]]:
    warnings = []
    host_asset_path = request.get("host_blueprint_asset_path")
    host_record = None
    if not host_asset_path:
        host_record, record_warnings = resolve_host_record(request)
        warnings.extend(record_warnings)
        host_asset_path = host_record.get("asset_path") if host_record else None
    if host_asset_path and unreal.EditorAssetLibrary.does_asset_exist(object_path_from_asset_path(str(host_asset_path))):
        return str(host_asset_path), host_record, warnings
    discovered_record = discover_live_host_record(
        request.get("asset_root") or "/Game/PMXPipeline",
        request.get("package_id") or request.get("character_package_id"),
        request.get("sample_id"),
    )
    if discovered_record:
        if host_asset_path and host_asset_path != discovered_record.get("asset_path"):
            warnings.append("stale_host_asset_path_replaced_from_live_registry")
        return str(discovered_record["asset_path"]), discovered_record, warnings
    if not host_asset_path:
        raise ValueError("host_blueprint_asset_path_missing")
    return str(host_asset_path), host_record, warnings


def discover_live_host_record(asset_root: str, package_id: str | None, sample_id: str | None) -> dict | None:
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    suite_root = f"{asset_root.rstrip('/')}/Registry/Suites"
    assets = list(registry.get_assets_by_path(to_name(suite_root), recursive=True))
    sample_slug = sanitize_segment(sample_id) if sample_id else None
    matched_loadout = None
    for asset_data in assets:
        if asset_class_name(asset_data) != "PMXEquipmentLoadoutAsset":
            continue
        object_path = asset_object_path(asset_data)
        asset = unreal.EditorAssetLibrary.load_asset(object_path)
        if not asset:
            continue
        loadout = asset.get_editor_property("loadout")
        record_package_id = str(getattr(loadout, "character_package_id", "") or "")
        record_sample_id = str(getattr(loadout, "sample_id", "") or "")
        if package_id and record_package_id == package_id:
            matched_loadout = {
                "sample_id": record_sample_id,
                "character_package_id": record_package_id,
                "loadout_asset_path": object_path.rsplit(".", 1)[0],
                "default_weapon_skeletal_mesh": str(getattr(loadout, "default_weapon_skeletal_mesh", "") or ""),
            }
            break
        if sample_slug and sanitize_segment(record_sample_id) == sample_slug:
            matched_loadout = {
                "sample_id": record_sample_id,
                "character_package_id": record_package_id,
                "loadout_asset_path": object_path.rsplit(".", 1)[0],
                "default_weapon_skeletal_mesh": str(getattr(loadout, "default_weapon_skeletal_mesh", "") or ""),
            }

    if matched_loadout:
        loadout_asset_path = matched_loadout["loadout_asset_path"]
        host_asset_path = loadout_asset_path.replace("/Characters/DA_PMXCharacterLoadout_", "/Hosts/BP_PMXCharacterHost_")
        component_asset_path = loadout_asset_path.replace("/Characters/DA_PMXCharacterLoadout_", "/Components/BP_PMXCharacterEquipmentComponent_")
        if unreal.EditorAssetLibrary.does_asset_exist(object_path_from_asset_path(host_asset_path)):
            return {
                "sample_id": matched_loadout["sample_id"],
                "character_package_id": matched_loadout["character_package_id"],
                "asset_path": host_asset_path,
                "loadout_asset_path": loadout_asset_path,
                "component_blueprint_asset_path": component_asset_path,
                "default_weapon_skeletal_mesh": matched_loadout["default_weapon_skeletal_mesh"],
                "has_runtime_weapon_mesh_component": bool(matched_loadout["default_weapon_skeletal_mesh"]),
            }

    for asset_data in assets:
        asset_path = str(asset_data.package_name)
        if asset_class_name(asset_data) != "Blueprint":
            continue
        asset_name = str(asset_data.asset_name)
        if not asset_name.startswith("BP_PMXCharacterHost_"):
            continue
        if sample_slug and sample_slug not in sanitize_segment(asset_name):
            continue
        return {
            "sample_id": sample_id,
            "character_package_id": package_id,
            "asset_path": asset_path,
        }
    return None


def load_suite_summary_record(summary_path: str | None, package_id: str | None) -> dict:
    if not summary_path or not package_id:
        return {}
    candidate = Path(summary_path).expanduser().resolve()
    if not candidate.exists():
        return {}
    payload = read_json(candidate)
    for entry in payload.get("successes") or []:
        if entry.get("package_id") == package_id:
            return entry
    for entry in payload.get("entries") or []:
        if entry.get("package_id") == package_id:
            return entry
    return {}


def scenario_capture_overrides(index: int, scenario_name: str, request: dict) -> dict:
    stage_map = dict(request.get("scenario_stage_map") or {})
    stage_entry = dict(stage_map.get(scenario_name) or {})
    camera_mode = str(stage_entry.get("camera_mode") or request.get("camera_mode") or "auto_framing")
    if camera_mode == "anchor_actor":
        return {
            "camera_mode": "anchor_actor",
            "spawn_anchor_actor_label": stage_entry.get("spawn_anchor_actor_label") or request.get("spawn_anchor_actor_label"),
            "camera_anchor_actor_label": stage_entry.get("camera_anchor_actor_label") or request.get("camera_anchor_actor_label"),
            "expected_spawn_location": stage_entry.get("expected_spawn_location"),
            "expected_spawn_rotation": stage_entry.get("expected_spawn_rotation"),
            "expected_camera_location": stage_entry.get("expected_camera_location"),
            "expected_camera_rotation": stage_entry.get("expected_camera_rotation"),
        }
    base_location = vector_from_request(request.get("location"), unreal.Vector(0.0, 0.0, 120.0))
    base_rotation = rotator_from_request(request.get("rotation"), make_rotator(0.0, 180.0, 0.0))
    base_distance = float(request.get("camera_distance") or 320.0)
    base_lateral = float(request.get("camera_lateral_offset") or -160.0)
    base_height = float(request.get("camera_height") or 120.0)
    presets = {
        "idle_2s": {
            "location": base_location,
            "rotation": base_rotation,
            "camera_distance": base_distance,
            "camera_lateral_offset": base_lateral,
            "camera_height": base_height,
        },
        "walk_forward_2s": {
            "location": unreal.Vector(base_location.x + 110.0 + (index * 5.0), base_location.y + 30.0, base_location.z),
            "rotation": make_rotator(base_rotation.pitch, base_rotation.yaw - 15.0, base_rotation.roll),
            "camera_distance": base_distance - 20.0,
            "camera_lateral_offset": base_lateral + 15.0,
            "camera_height": base_height,
        },
        "run_forward_2s": {
            "location": unreal.Vector(base_location.x + 220.0 + (index * 10.0), base_location.y - 55.0, base_location.z),
            "rotation": make_rotator(base_rotation.pitch, base_rotation.yaw - 32.0, base_rotation.roll),
            "camera_distance": base_distance - 35.0,
            "camera_lateral_offset": base_lateral + 40.0,
            "camera_height": base_height + 6.0,
        },
        "jump_land_1cycle": {
            "location": unreal.Vector(base_location.x + 90.0, base_location.y + 95.0, base_location.z + 95.0),
            "rotation": make_rotator(base_rotation.pitch, base_rotation.yaw - 8.0, base_rotation.roll),
            "camera_distance": base_distance + 25.0,
            "camera_lateral_offset": base_lateral - 10.0,
            "camera_height": base_height + 55.0,
            "target_height_offset": float(request.get("target_height_offset") or 150.0),
        },
    }
    selected = presets.get(scenario_name, presets["idle_2s"])
    return {
        "camera_mode": "auto_framing",
        "location": serialize_vector(selected["location"]),
        "rotation": serialize_rotator(selected["rotation"]),
        "camera_distance": float(selected.get("camera_distance", base_distance)),
        "camera_lateral_offset": float(selected.get("camera_lateral_offset", base_lateral)),
        "camera_height": float(selected.get("camera_height", base_height)),
        "target_height_offset": float(selected.get("target_height_offset", request.get("target_height_offset") or 0.0)),
    }


def actor_bounds(actor) -> tuple[unreal.Vector, unreal.Vector]:
    try:
        origin, extent = actor.get_actor_bounds(False)
        return origin, extent
    except Exception:
        origin = actor.get_actor_location()
        return origin, unreal.Vector(50.0, 50.0, 100.0)


def build_capture_camera_for_actor(actor, request: dict) -> dict:
    origin, extent = actor_bounds(actor)
    actor_location = actor.get_actor_location()
    actor_rotation = actor.get_actor_rotation()
    forward = actor.get_actor_forward_vector()
    right = actor.get_actor_right_vector()
    distance = float(request.get("camera_distance") or max(extent.x, extent.y, 80.0) * 3.0)
    lateral_offset = float(request.get("camera_lateral_offset") or (-0.5 * distance))
    camera_height = float(request.get("camera_height") or max(extent.z * 1.2, 120.0))
    target_height_offset = float(request.get("target_height_offset") or max(extent.z * 0.65, 90.0))
    camera_location = (
        origin
        - (forward * distance)
        + (right * lateral_offset)
        + unreal.Vector(0.0, 0.0, camera_height)
    )
    target_location = origin + unreal.Vector(0.0, 0.0, target_height_offset)
    camera_rotation = unreal.MathLibrary.find_look_at_rotation(camera_location, target_location)
    return {
        "camera_source": "auto_framing",
        "actor_location": serialize_vector(actor_location),
        "actor_rotation": serialize_rotator(actor_rotation),
        "bounds_origin": serialize_vector(origin),
        "bounds_extent": serialize_vector(extent),
        "camera_location": serialize_vector(camera_location),
        "camera_rotation": serialize_rotator(camera_rotation),
        "target_location": serialize_vector(target_location),
        "distance": distance,
        "lateral_offset": lateral_offset,
        "camera_height": camera_height,
        "target_height_offset": target_height_offset,
    }


def normalize_degrees(value: float) -> float:
    normalized = (float(value) + 180.0) % 360.0 - 180.0
    if normalized == -180.0:
        return 180.0
    return normalized


def camera_horizontal_fov_degrees(camera_actor) -> float:
    fallback = 90.0
    if not camera_actor:
        return fallback
    try:
        if hasattr(camera_actor, "get_cine_camera_component"):
            component = camera_actor.get_cine_camera_component()
            for property_name in ("current_horizontal_fov", "field_of_view", "fov_angle"):
                try:
                    value = component.get_editor_property(property_name)
                    if value:
                        return float(value)
                except Exception:
                    continue
        if hasattr(camera_actor, "get_camera_component"):
            component = camera_actor.get_camera_component()
            for property_name in ("field_of_view", "fov_angle"):
                try:
                    value = component.get_editor_property(property_name)
                    if value:
                        return float(value)
                except Exception:
                    continue
    except Exception:
        pass
    return fallback


def evaluate_subject_visibility(target_actor, camera_actor, camera_location, camera_rotation, width: int, height: int) -> dict:
    origin, extent = actor_bounds(target_actor)
    target_location = origin + unreal.Vector(0.0, 0.0, max(extent.z * 0.25, 40.0))
    look_at_rotation = unreal.MathLibrary.find_look_at_rotation(camera_location, target_location)
    delta_pitch = normalize_degrees(look_at_rotation.pitch - camera_rotation.pitch)
    delta_yaw = normalize_degrees(look_at_rotation.yaw - camera_rotation.yaw)
    to_target = target_location - camera_location
    target_distance = float(to_target.length())
    if target_distance <= 0.001:
        return {
            "visible": False,
            "reason": "camera_and_target_coincident",
            "delta_pitch": delta_pitch,
            "delta_yaw": delta_yaw,
            "target_distance": target_distance,
            "horizontal_fov": 0.0,
            "vertical_fov": 0.0,
        }

    horizontal_fov = max(10.0, min(170.0, camera_horizontal_fov_degrees(camera_actor)))
    aspect_ratio = float(width) / float(height) if height else (16.0 / 9.0)
    vertical_fov = float(
        2.0
        * math.degrees(math.atan(math.tan(math.radians(horizontal_fov) / 2.0) / max(aspect_ratio, 0.1)))
    )
    horizontal_margin = (horizontal_fov * 0.5) * 0.92
    vertical_margin = (vertical_fov * 0.5) * 0.92
    extent_yaw_margin = float(math.degrees(math.atan2(max(extent.x, extent.y, 1.0), max(target_distance, 1.0))))
    extent_pitch_margin = float(math.degrees(math.atan2(max(extent.z, 1.0), max(target_distance, 1.0))))
    subject_visible = abs(delta_yaw) <= (horizontal_margin + extent_yaw_margin) and abs(delta_pitch) <= (vertical_margin + extent_pitch_margin)
    return {
        "visible": bool(subject_visible),
        "reason": "within_camera_frustum_estimate" if subject_visible else "target_origin_outside_camera_frustum_estimate",
        "delta_pitch": delta_pitch,
        "delta_yaw": delta_yaw,
        "target_distance": target_distance,
        "horizontal_fov": horizontal_fov,
        "vertical_fov": vertical_fov,
        "horizontal_margin": horizontal_margin,
        "vertical_margin": vertical_margin,
        "extent_yaw_margin": extent_yaw_margin,
        "extent_pitch_margin": extent_pitch_margin,
        "target_location": serialize_vector(target_location),
        "target_bounds_origin": serialize_vector(origin),
        "target_bounds_extent": serialize_vector(extent),
        "camera_location": serialize_vector(camera_location),
        "camera_rotation": serialize_rotator(camera_rotation),
        "look_at_rotation": serialize_rotator(look_at_rotation),
    }


def component_asset_path(component) -> str:
    if not component:
        return ""
    for property_name in ("skeletal_mesh_asset", "skeletal_mesh", "static_mesh"):
        try:
            asset = component.get_editor_property(property_name)
        except Exception:
            asset = None
        if asset:
            try:
                return asset.get_path_name()
            except Exception:
                continue
    return ""


def component_visibility_record(component) -> dict:
    payload = {
        "visible": None,
        "hidden_in_game": None,
        "component_name": str(getattr(component, "get_name", lambda: "")() or "") if component else "",
        "class_name": component_class_name(component) if component else "",
        "asset_path": component_asset_path(component),
    }
    if not component:
        return payload
    for property_name in ("visible", "hidden_in_game", "cast_shadow"):
        try:
            payload[property_name] = component.get_editor_property(property_name)
        except Exception:
            continue
    return payload


def bounds_payload_from_origin_extent(origin, extent, source: str) -> dict:
    diagonal_length = float(math.sqrt((extent.x * extent.x) + (extent.y * extent.y) + (extent.z * extent.z)))
    return {
        "origin": serialize_vector(origin),
        "extent": serialize_vector(extent),
        "diagonal_length": diagonal_length,
        "non_zero": diagonal_length > 1.0,
        "source": source,
    }


def asset_bounds_payload_for_component(component) -> dict:
    if not component:
        return {
            "origin": {},
            "extent": {},
            "diagonal_length": 0.0,
            "non_zero": False,
            "source": "asset_bounds_unavailable",
        }
    asset = None
    for property_name in ("skeletal_mesh_asset", "skeletal_mesh", "static_mesh"):
        try:
            asset = component.get_editor_property(property_name)
        except Exception:
            asset = None
        if asset:
            break
    if not asset:
        return {
            "origin": {},
            "extent": {},
            "diagonal_length": 0.0,
            "non_zero": False,
            "source": "asset_missing",
        }
    local_origin = local_extent = None
    for property_name in ("extended_bounds", "imported_bounds", "bounds"):
        try:
            bounds_value = asset.get_editor_property(property_name)
        except Exception:
            bounds_value = None
        if bounds_value and hasattr(bounds_value, "origin") and hasattr(bounds_value, "box_extent"):
            local_origin = bounds_value.origin
            local_extent = bounds_value.box_extent
            break
    if local_origin is None or local_extent is None:
        if hasattr(asset, "get_bounds"):
            try:
                bounds_value = asset.get_bounds()
            except Exception:
                bounds_value = None
            if bounds_value and hasattr(bounds_value, "origin") and hasattr(bounds_value, "box_extent"):
                local_origin = bounds_value.origin
                local_extent = bounds_value.box_extent
    if local_origin is None or local_extent is None:
        return {
            "origin": {},
            "extent": {},
            "diagonal_length": 0.0,
            "non_zero": False,
            "source": "asset_bounds_unavailable",
        }
    component_location = component_world_location(component) or unreal.Vector(0.0, 0.0, 0.0)
    world_origin = unreal.Vector(
        component_location.x + float(local_origin.x),
        component_location.y + float(local_origin.y),
        component_location.z + float(local_origin.z),
    )
    return bounds_payload_from_origin_extent(world_origin, local_extent, "asset_bounds_fallback")


def component_bounds_payload(component, fallback_actor=None) -> dict:
    payload = {
        "origin": {},
        "extent": {},
        "diagonal_length": 0.0,
        "non_zero": False,
        "source": "component_bounds",
    }
    if not component:
        if fallback_actor:
            origin, extent = actor_bounds(fallback_actor)
            return bounds_payload_from_origin_extent(origin, extent, "fallback_actor_bounds")
        return payload
    origin = extent = None
    try:
        origin = component.bounds.origin
        extent = component.bounds.box_extent
        payload = bounds_payload_from_origin_extent(origin, extent, "component_bounds")
    except Exception:
        location = component_world_location(component)
        origin = location or unreal.Vector(0.0, 0.0, 0.0)
        extent = unreal.Vector(0.0, 0.0, 0.0)
        payload = bounds_payload_from_origin_extent(origin, extent, "component_bounds")
    if not payload.get("non_zero") and hasattr(component, "get_component_bounds"):
        try:
            component_origin, component_extent = component.get_component_bounds()
        except Exception:
            component_origin = component_extent = None
        if component_origin is not None and component_extent is not None:
            component_payload = bounds_payload_from_origin_extent(component_origin, component_extent, "component_get_component_bounds")
            if component_payload.get("non_zero"):
                payload = component_payload
    if not payload.get("non_zero") and hasattr(component, "calc_bounds") and hasattr(component, "get_component_transform"):
        try:
            calc_bounds = component.calc_bounds(component.get_component_transform())
        except Exception:
            calc_bounds = None
        if calc_bounds and hasattr(calc_bounds, "origin") and hasattr(calc_bounds, "box_extent"):
            calc_payload = bounds_payload_from_origin_extent(calc_bounds.origin, calc_bounds.box_extent, "component_calc_bounds")
            if calc_payload.get("non_zero"):
                payload = calc_payload
    if not payload.get("non_zero"):
        asset_payload = asset_bounds_payload_for_component(component)
        if asset_payload.get("non_zero"):
            payload = asset_payload
    if (not payload["non_zero"]) and fallback_actor:
        fallback_origin, fallback_extent = actor_bounds(fallback_actor)
        payload = bounds_payload_from_origin_extent(fallback_origin, fallback_extent, "fallback_actor_bounds")
    return payload


def component_transform_payload(component) -> dict:
    location = component_world_location(component)
    rotation = component_world_rotation(component)
    scale = None
    if component:
        for method_name in ("get_component_scale", "get_world_scale"):
            if hasattr(component, method_name):
                try:
                    scale = getattr(component, method_name)()
                    break
                except Exception:
                    continue
    return {
        "location": serialize_vector(location) if location is not None else {},
        "rotation": serialize_rotator(rotation) if rotation is not None else {},
        "scale": serialize_vector(scale) if scale is not None else {},
    }


def component_relative_transform_payload(component) -> dict:
    location = rotation = scale = None
    if component:
        for method_name in ("get_relative_location",):
            if hasattr(component, method_name):
                try:
                    location = getattr(component, method_name)()
                    break
                except Exception:
                    continue
        for method_name in ("get_relative_rotation",):
            if hasattr(component, method_name):
                try:
                    rotation = getattr(component, method_name)()
                    break
                except Exception:
                    continue
        for method_name in ("get_relative_scale3d",):
            if hasattr(component, method_name):
                try:
                    scale = getattr(component, method_name)()
                    break
                except Exception:
                    continue
    return {
        "location": serialize_vector(location) if location is not None else {},
        "rotation": serialize_rotator(rotation) if rotation is not None else {},
        "scale": serialize_vector(scale) if scale is not None else {},
    }


def component_attach_payload(component) -> dict:
    payload = {
        "attach_parent_name": "",
        "attach_parent_class": "",
        "attach_socket_name": "",
        "world_transform": component_transform_payload(component),
        "relative_transform": component_relative_transform_payload(component),
    }
    if not component:
        return payload
    attach_parent = None
    if hasattr(component, "get_attach_parent"):
        try:
            attach_parent = component.get_attach_parent()
        except Exception:
            attach_parent = None
    if attach_parent:
        payload["attach_parent_name"] = str(getattr(attach_parent, "get_name", lambda: "")() or "")
        payload["attach_parent_class"] = component_class_name(attach_parent)
    if hasattr(component, "get_attach_socket_name"):
        try:
            payload["attach_socket_name"] = str(component.get_attach_socket_name() or "")
        except Exception:
            pass
    return payload


def interesting_attach_targets(component) -> list[str]:
    if not component or not hasattr(component, "get_all_socket_names"):
        return []
    try:
        names = [str(item) for item in (component.get_all_socket_names() or [])]
    except Exception:
        return []
    interesting = []
    for name in names:
        lower = name.lower()
        if any(token in lower for token in ("weapon", "wpn", "hand_r", "r_hand", "right", "ik_hand_r")):
            interesting.append(name)
    if interesting:
        return interesting[:32]
    return names[:16]


def pmx_equipment_diagnostics(pmx_component, owner_mesh) -> dict:
    payload = {
        "component_name": str(getattr(pmx_component, "get_name", lambda: "")() or "") if pmx_component else "",
        "component_class": component_class_name(pmx_component) if pmx_component else "",
        "desired_weapon_mesh_asset": "",
        "requested_attach_socket_name": "",
        "resolved_attach_socket_name": "",
        "resolved_attach_socket_exists": None,
        "attach_resolution_mode": "",
        "owner_socket_exists_for_requested_name": None,
        "owner_interesting_attach_targets": interesting_attach_targets(owner_mesh),
    }
    if not pmx_component:
        return payload
    try:
        desired_weapon_mesh = pmx_component.get_desired_weapon_mesh()
    except Exception:
        desired_weapon_mesh = None
    if desired_weapon_mesh:
        try:
            payload["desired_weapon_mesh_asset"] = desired_weapon_mesh.get_path_name()
        except Exception:
            pass
    if hasattr(pmx_component, "get_attach_socket_name"):
        try:
            requested_name = pmx_component.get_attach_socket_name()
            payload["requested_attach_socket_name"] = str(requested_name or "")
            if owner_mesh and requested_name and hasattr(owner_mesh, "does_socket_exist"):
                try:
                    payload["owner_socket_exists_for_requested_name"] = bool(owner_mesh.does_socket_exist(requested_name))
                except Exception:
                    pass
        except Exception:
            pass
    if hasattr(pmx_component, "get_resolved_attach_socket_name"):
        try:
            payload["resolved_attach_socket_name"] = str(pmx_component.get_resolved_attach_socket_name() or "")
        except Exception:
            pass
    if hasattr(pmx_component, "has_resolved_attach_socket"):
        try:
            payload["resolved_attach_socket_exists"] = bool(pmx_component.has_resolved_attach_socket())
        except Exception:
            pass
    if hasattr(pmx_component, "get_attach_resolution_mode"):
        try:
            payload["attach_resolution_mode"] = str(pmx_component.get_attach_resolution_mode() or "")
        except Exception:
            pass
    return payload


def actor_primary_mesh_component(actor):
    if not actor:
        return None
    if hasattr(actor, "get_editor_property"):
        try:
            mesh = actor.get_editor_property("mesh")
            if mesh:
                return mesh
        except Exception:
            pass
    try:
        components = list(actor.get_components_by_class(unreal.SkeletalMeshComponent) or [])
    except Exception:
        components = []
    return components[0] if components else None


def actor_weapon_mesh_component(actor, primary_component=None):
    if not actor:
        return None
    try:
        pmx_component = actor.get_component_by_class(unreal.PMXCharacterEquipmentComponent)
    except Exception:
        pmx_component = None
    if pmx_component:
        try:
            managed = pmx_component.get_managed_weapon_mesh_component()
            if managed:
                return managed
        except Exception:
            pass
    try:
        components = list(actor.get_components_by_class(unreal.SkeletalMeshComponent) or [])
    except Exception:
        components = []
    for component in components:
        if primary_component and component == primary_component:
            continue
        asset_path = component_asset_path(component)
        if asset_path:
            return component
    return components[1] if len(components) > 1 else None


def bounds_corners(origin: unreal.Vector, extent: unreal.Vector) -> list[unreal.Vector]:
    corners = []
    for x_sign in (-1.0, 1.0):
        for y_sign in (-1.0, 1.0):
            for z_sign in (-1.0, 1.0):
                corners.append(
                    unreal.Vector(
                        origin.x + (extent.x * x_sign),
                        origin.y + (extent.y * y_sign),
                        origin.z + (extent.z * z_sign),
                    )
                )
    return corners


def dot_vector(a, b) -> float:
    return float((a.x * b.x) + (a.y * b.y) + (a.z * b.z))


def project_world_to_camera_screen(world_point, camera_actor, width: int, height: int) -> dict | None:
    camera_location = camera_actor.get_actor_location()
    forward = camera_actor.get_actor_forward_vector()
    right = camera_actor.get_actor_right_vector()
    up = camera_actor.get_actor_up_vector()
    relative = world_point - camera_location
    depth = dot_vector(relative, forward)
    if depth <= 0.001:
        return None
    horizontal_fov = max(10.0, min(170.0, camera_horizontal_fov_degrees(camera_actor)))
    aspect_ratio = float(width) / float(height) if height else (16.0 / 9.0)
    vertical_fov = float(
        2.0 * math.degrees(math.atan(math.tan(math.radians(horizontal_fov) / 2.0) / max(aspect_ratio, 0.1)))
    )
    half_width = math.tan(math.radians(horizontal_fov) / 2.0) * depth
    half_height = math.tan(math.radians(vertical_fov) / 2.0) * depth
    if abs(half_width) <= 1e-6 or abs(half_height) <= 1e-6:
        return None
    screen_x = dot_vector(relative, right) / half_width
    screen_y = dot_vector(relative, up) / half_height
    return {
        "depth": depth,
        "ndc_x": screen_x,
        "ndc_y": screen_y,
        "screen_x": ((screen_x + 1.0) * 0.5) * float(width),
        "screen_y": ((1.0 - screen_y) * 0.5) * float(height),
    }


def screen_coverage_for_component(component, camera_actor, width: int, height: int, fallback_actor=None) -> dict:
    if not component:
        return {
            "coverage_ratio": 0.0,
            "projected_points": 0,
            "in_frame": False,
            "reason": "component_missing",
        }
    bounds = component_bounds_payload(component, fallback_actor=fallback_actor)
    if not bounds.get("non_zero"):
        return {
            "coverage_ratio": 0.0,
            "projected_points": 0,
            "in_frame": False,
            "reason": "bounds_invalid",
            "bounds": bounds,
        }
    origin = vector_from_request(bounds["origin"])
    extent = vector_from_request(bounds["extent"])
    projected = []
    for point in bounds_corners(origin, extent):
        screen_point = project_world_to_camera_screen(point, camera_actor, width, height)
        if screen_point is not None:
            projected.append(screen_point)
    if not projected:
        return {
            "coverage_ratio": 0.0,
            "projected_points": 0,
            "in_frame": False,
            "reason": "all_points_behind_camera",
            "bounds": bounds,
        }
    screen_x_values = [item["screen_x"] for item in projected]
    screen_y_values = [item["screen_y"] for item in projected]
    min_x = max(0.0, min(screen_x_values))
    max_x = min(float(width), max(screen_x_values))
    min_y = max(0.0, min(screen_y_values))
    max_y = min(float(height), max(screen_y_values))
    visible_width = max(0.0, max_x - min_x)
    visible_height = max(0.0, max_y - min_y)
    coverage_ratio = (visible_width * visible_height) / max(float(width * height), 1.0)
    projected_center = project_world_to_camera_screen(origin, camera_actor, width, height)
    center_in_frame = bool(
        projected_center
        and 0.0 <= projected_center["screen_x"] <= float(width)
        and 0.0 <= projected_center["screen_y"] <= float(height)
    )
    return {
        "coverage_ratio": float(coverage_ratio),
        "projected_points": len(projected),
        "in_frame": bool(coverage_ratio > 0.0 and center_in_frame),
        "center_in_frame": center_in_frame,
        "screen_rect": {
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
        },
        "projected_center": projected_center or {},
        "bounds": bounds,
        "reason": "projected_bounds" if coverage_ratio > 0.0 else "projected_bounds_outside_frame",
    }


def line_of_sight_to_actor(camera_actor, target_actor) -> dict:
    if not camera_actor or not target_actor:
        return {
            "clear": False,
            "reason": "camera_or_target_missing",
        }
    origin, extent = actor_bounds(target_actor)
    target_location = origin + unreal.Vector(0.0, 0.0, max(extent.z * 0.45, 65.0))
    try:
        hit_result = unreal.SystemLibrary.line_trace_single(
            unreal.EditorLevelLibrary.get_editor_world(),
            camera_actor.get_actor_location(),
            target_location,
            unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
            False,
            [camera_actor, target_actor],
            unreal.DrawDebugTrace.NONE,
            True,
        )
    except Exception as exc:
        return {
            "clear": False,
            "reason": f"trace_api_failed:{exc}",
            "target_location": serialize_vector(target_location),
        }
    if not hit_result:
        return {
            "clear": True,
            "reason": "no_blocking_hit",
            "target_location": serialize_vector(target_location),
        }
    hit_actor = None
    try:
        hit_actor = hit_result.get_actor()
    except Exception:
        hit_actor = None
    if not hit_actor or hit_actor == target_actor:
        return {
            "clear": True,
            "reason": "target_hit_or_clear",
            "target_location": serialize_vector(target_location),
            "hit_actor_path": hit_actor.get_path_name() if hit_actor else "",
        }
    return {
        "clear": False,
        "reason": "blocked_by_other_actor",
        "target_location": serialize_vector(target_location),
        "hit_actor_label": hit_actor.get_actor_label(),
        "hit_actor_path": hit_actor.get_path_name(),
        "hit_actor_class": actor_class_name(hit_actor),
    }


def find_screenshot_output_path(output_path: Path) -> Path | None:
    if output_path.exists():
        return output_path
    project_saved_dir = Path(unreal.Paths.project_saved_dir())
    fallback_roots = [
        project_saved_dir / "Screenshots" / "WindowsEditor",
        project_saved_dir / "Screenshots" / "Windows",
    ]
    for root in fallback_roots:
        candidate = root / output_path.name
        if candidate.exists():
            return candidate
    return None


def wait_for_screenshot(task, desired_output_path: Path, timeout_seconds: float, stability_window_seconds: float, poll_interval_seconds: float) -> tuple[Path | None, bool]:
    deadline = time.time() + timeout_seconds
    stable_since = None
    last_size = None
    while time.time() < deadline:
        candidate = find_screenshot_output_path(desired_output_path)
        task_done = bool(task and task.is_valid_task() and task.is_task_done()) if task else False
        if candidate and candidate.exists():
            current_size = candidate.stat().st_size
            if last_size == current_size:
                if stable_since is None:
                    stable_since = time.time()
                elif time.time() - stable_since >= stability_window_seconds:
                    return candidate, task_done
            else:
                stable_since = None
                last_size = current_size
        elif task_done:
            return None, True
        time.sleep(poll_interval_seconds)
    return find_screenshot_output_path(desired_output_path), bool(task and task.is_valid_task() and task.is_task_done()) if task else False


def capture_to_render_target(
    capture_camera,
    width: int,
    height: int,
    output_path: Path,
    capture_hdr: bool,
    delay_seconds: float,
    timeout_seconds: float,
    stability_window_seconds: float,
    poll_interval_seconds: float,
) -> dict:
    world = unreal.EditorLevelLibrary.get_editor_world()
    actor_subsystem = editor_actor_subsystem()
    scene_capture_actor = None
    render_target = None
    warnings = []
    try:
        scene_capture_actor = actor_subsystem.spawn_actor_from_class(
            unreal.SceneCapture2D,
            capture_camera.get_actor_location(),
            capture_camera.get_actor_rotation(),
            True,
        )
        if not scene_capture_actor:
            return {
                "output_exists": False,
                "warnings": warnings,
                "errors": ["scene_capture_actor_spawn_failed"],
            }
        component = getattr(scene_capture_actor, "capture_component2d", None)
        if not component:
            return {
                "output_exists": False,
                "warnings": warnings,
                "errors": ["scene_capture_component_missing"],
            }
        render_target = unreal.RenderingLibrary.create_render_target2d(
            world,
            int(width),
            int(height),
            unreal.TextureRenderTargetFormat.RTF_RGBA8 if not capture_hdr else unreal.TextureRenderTargetFormat.RTF_RGBA16F,
        )
        if not render_target:
            return {
                "output_exists": False,
                "warnings": warnings,
                "errors": ["render_target_create_failed"],
            }
        component.set_editor_property("texture_target", render_target)
        component.set_editor_property(
            "capture_source",
            unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR if not capture_hdr else unreal.SceneCaptureSource.SCS_FINAL_COLOR_HDR,
        )
        component.set_editor_property("capture_every_frame", False)
        component.set_editor_property("capture_on_movement", False)
        if hasattr(component, "fov_angle") and hasattr(capture_camera, "get_camera_component"):
            try:
                camera_component = capture_camera.get_camera_component()
                fov_angle = camera_component.get_editor_property("field_of_view")
                component.set_editor_property("fov_angle", float(fov_angle))
            except Exception:
                pass
        time.sleep(max(delay_seconds, 0.05))
        component.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, render_target, str(output_path.parent), output_path.name)
        actual_output_path, _ = wait_for_screenshot(
            None,
            output_path,
            timeout_seconds,
            stability_window_seconds,
            poll_interval_seconds,
        )
        output_exists = bool(actual_output_path and actual_output_path.exists())
        return {
            "output_exists": output_exists,
            "output_path": str((actual_output_path or output_path).resolve()),
            "file_size_bytes": int(actual_output_path.stat().st_size) if output_exists else 0,
            "task_done": output_exists,
            "warnings": warnings,
            "errors": [] if output_exists else ["render_target_export_missing"],
            "capture_backend": "scene_capture_render_target",
        }
    except Exception as exc:
        return {
            "output_exists": False,
            "warnings": warnings,
            "errors": [f"render_target_capture_failed:{exc}"],
        }
    finally:
        if scene_capture_actor:
            try:
                actor_subsystem.destroy_actor(scene_capture_actor)
            except Exception:
                pass


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


def capture_frame(request: dict) -> dict:
    raw_output_path = request.get("output_path")
    output_path = Path(raw_output_path).expanduser() if raw_output_path else None
    if output_path is None:
        capture_root = Path(request.get("capture_root") or (Path(unreal.Paths.project_saved_dir()) / "Screenshots" / "AiUE"))
        shot_name = sanitize_segment(str(request.get("shot_name") or request.get("actor_label") or request.get("target_actor_label") or "capture"))
        output_path = capture_root / f"{shot_name}.png"
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    warnings = []
    camera_mode = str(request.get("camera_mode") or "auto_framing")
    level_path = request.get("level_path") or request.get("scene_level_path")
    if level_path:
        load_result = load_level({"level_path": level_path})
        warnings.extend(load_result.get("warnings") or [])
        if load_result.get("errors"):
            return {
                "warnings": warnings,
                "errors": list(load_result.get("errors") or []),
            }

    spawn_anchor_actor_label = str(request.get("spawn_anchor_actor_label") or "")
    camera_anchor_actor_label = str(request.get("camera_anchor_actor_label") or "")
    expected_spawn_location = request.get("expected_spawn_location")
    expected_spawn_rotation = request.get("expected_spawn_rotation")
    resolved_stage_anchors = {}
    spawn_anchor = None
    camera_anchor = None
    if camera_mode == "anchor_actor":
        wait_for_actor_labels([spawn_anchor_actor_label, camera_anchor_actor_label])
        spawn_anchor, spawn_anchor_record = resolve_stage_anchor_actor(spawn_anchor_actor_label, "TargetPoint", "spawn")
        camera_anchor, camera_anchor_record = resolve_stage_anchor_actor(camera_anchor_actor_label, "CineCameraActor", "camera")
        resolved_stage_anchors = {
            "spawn": spawn_anchor_record,
            "camera": camera_anchor_record,
        }
        anchor_errors = list(spawn_anchor_record.get("errors") or []) + list(camera_anchor_record.get("errors") or [])
        if anchor_errors:
            return {
                "camera_mode": camera_mode,
                "camera_source": "anchor_actor",
                "spawn_anchor_actor_label": spawn_anchor_actor_label,
                "camera_anchor_actor_label": camera_anchor_actor_label,
                "resolved_stage_anchors": resolved_stage_anchors,
                "warnings": warnings,
                "errors": anchor_errors,
            }

    actor_label = request.get("actor_label") or request.get("target_actor_label")
    actor_path = request.get("actor_path") or request.get("target_actor_path")
    target_actor = find_actor_by_label_or_path(actor_label=actor_label, actor_path=actor_path)
    actor_subsystem = editor_actor_subsystem()
    spawned_host = None
    host_asset_path = None
    host_record = None
    if not target_actor:
        try:
            host_asset_path, host_record, host_warnings = resolve_host_blueprint_asset_path(request)
            warnings.extend(host_warnings)
            blueprint_asset = unreal.EditorAssetLibrary.load_asset(object_path_from_asset_path(host_asset_path))
            if not blueprint_asset:
                return {
                    "warnings": warnings,
                    "errors": [f"host_blueprint_load_failed:{host_asset_path}"],
                }
            if camera_mode == "anchor_actor" and spawn_anchor:
                if expected_spawn_location and expected_spawn_rotation:
                    spawn_location = vector_from_request(expected_spawn_location)
                    spawn_rotation = rotator_from_request(expected_spawn_rotation)
                else:
                    spawn_location = spawn_anchor.get_actor_location()
                    spawn_rotation = spawn_anchor.get_actor_rotation()
            else:
                spawn_location = vector_from_request(request.get("location"), unreal.Vector(0.0, 0.0, 120.0))
                spawn_rotation = rotator_from_request(request.get("rotation"), make_rotator(0.0, 180.0, 0.0))
            spawned_host = actor_subsystem.spawn_actor_from_object(blueprint_asset, spawn_location, spawn_rotation, True)
            if not spawned_host:
                return {
                    "warnings": warnings,
                    "errors": ["target_actor_not_found", f"failed_to_spawn_host_for_capture:{host_asset_path}"],
                }
            spawned_host.set_actor_label(str(actor_label or asset_name_from_path(host_asset_path)))
            try:
                spawned_host.apply_configured_loadout()
            except Exception as exc:
                warnings.append(f"apply_configured_loadout_failed:{exc}")
            target_actor = spawned_host
            warnings.append("target_actor_not_found_spawned_host_for_capture")
        except Exception:
            return {
                "warnings": warnings,
                "errors": ["target_actor_not_found"],
            }

    if camera_mode == "anchor_actor" and spawn_anchor and target_actor:
        if expected_spawn_location and expected_spawn_rotation:
            spawn_location = vector_from_request(expected_spawn_location)
            spawn_rotation = rotator_from_request(expected_spawn_rotation)
        else:
            spawn_location = spawn_anchor.get_actor_location()
            spawn_rotation = spawn_anchor.get_actor_rotation()
        try:
            target_actor.set_actor_location(spawn_location, False, False)
        except Exception:
            target_actor.set_actor_location(spawn_location, False)
        try:
            target_actor.set_actor_rotation(spawn_rotation, False)
        except Exception:
            target_actor.set_actor_rotation(spawn_rotation)

    if camera_mode == "anchor_actor":
        camera_plan = build_anchor_camera_plan(camera_anchor, target_actor, request)
    elif camera_mode == "explicit_pose":
        explicit_camera_location = vector_from_request(request.get("camera_location"))
        explicit_camera_rotation = rotator_from_request(request.get("camera_rotation"))
        origin, extent = actor_bounds(target_actor)
        camera_plan = {
            "camera_source": str(request.get("camera_source") or "explicit_pose"),
            "camera_location": serialize_vector(explicit_camera_location),
            "camera_rotation": serialize_rotator(explicit_camera_rotation),
            "target_location": serialize_vector(origin + unreal.Vector(0.0, 0.0, max(extent.z * 0.45, 65.0))),
            "bounds_origin": serialize_vector(origin),
            "bounds_extent": serialize_vector(extent),
        }
    else:
        camera_plan = build_capture_camera_for_actor(target_actor, request)
    camera_location = vector_from_request(camera_plan["camera_location"])
    camera_rotation = rotator_from_request(camera_plan["camera_rotation"])
    width = int(request.get("width") or request.get("capture_width") or 1280)
    height = int(request.get("height") or request.get("capture_height") or 720)
    delay_seconds = float(request.get("delay") or request.get("capture_delay_seconds") or 0.2)
    timeout_seconds = float(request.get("timeout_seconds") or 30.0)
    stability_window_seconds = float(request.get("file_stability_window_seconds") or 0.75)
    poll_interval_seconds = float(request.get("poll_interval_seconds") or 0.2)
    capture_hdr = bool(request.get("capture_hdr", False))
    force_game_view = bool(request.get("force_game_view", True))
    level_editor = level_editor_subsystem()
    temp_camera = None
    capture_camera = None
    try:
        temp_camera = actor_subsystem.spawn_actor_from_class(unreal.CameraActor, camera_location, camera_rotation, True)
        if not temp_camera:
            return {
                "warnings": warnings,
                "errors": ["temporary_camera_spawn_failed"],
            }
        temp_camera.set_actor_label(f"AIUE_CaptureCamera_{sanitize_segment(target_actor.get_actor_label())}")
        capture_camera = temp_camera

        subject_visibility = evaluate_subject_visibility(target_actor, capture_camera, camera_location, camera_rotation, width, height)
        if not subject_visibility.get("visible"):
            warnings.append("subject_not_visible_in_camera_plan")
        try:
            level_editor.pilot_level_actor(capture_camera)
        except Exception as exc:
            warnings.append(f"pilot_level_actor_failed:{exc}")
        try:
            if hasattr(level_editor, "set_allows_cinematic_control"):
                level_editor.set_allows_cinematic_control(True)
        except Exception:
            pass
        try:
            if hasattr(level_editor, "set_exact_camera_view"):
                level_editor.set_exact_camera_view(True)
        except Exception:
            pass
        render_target_capture = capture_to_render_target(
            capture_camera,
            width,
            height,
            output_path,
            capture_hdr,
            delay_seconds,
            timeout_seconds,
            stability_window_seconds,
            poll_interval_seconds,
        )
        warnings.extend(render_target_capture.get("warnings") or [])
        actual_output_path = Path(render_target_capture["output_path"]).resolve() if render_target_capture.get("output_path") else None
        task_done = bool(render_target_capture.get("task_done"))
        screenshot_exists = bool(render_target_capture.get("output_exists"))
        capture_backend = str(render_target_capture.get("capture_backend") or "")
        if screenshot_exists and int(render_target_capture.get("file_size_bytes") or 0) < 400000:
            warnings.append("render_target_capture_too_small_fallback_to_automation")
            screenshot_exists = False

        if not screenshot_exists:
            unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera_location, camera_rotation)
            level_editor.editor_set_viewport_realtime(True)
            try:
                level_editor.editor_set_game_view(True)
            except Exception:
                pass
            level_editor.editor_invalidate_viewports()
            task = unreal.AutomationLibrary.take_high_res_screenshot(
                width,
                height,
                str(output_path),
                capture_camera,
                False,
                capture_hdr,
                unreal.ComparisonTolerance.LOW,
                "AiUE capture",
                delay_seconds,
                force_game_view,
            )
            actual_output_path, task_done = wait_for_screenshot(task, output_path, timeout_seconds, stability_window_seconds, poll_interval_seconds)
            if actual_output_path and actual_output_path != output_path:
                shutil.copyfile(actual_output_path, output_path)
                actual_output_path = output_path
            screenshot_exists = bool(actual_output_path and actual_output_path.exists())
            capture_backend = capture_backend or "automation_high_res_screenshot"
        return {
            "target_actor_label": target_actor.get_actor_label(),
            "target_actor_path": target_actor.get_path_name(),
            "host_blueprint_asset_path": host_asset_path,
            "host_record": host_record,
            "target_render_components": summarize_render_components(target_actor),
            "camera_mode": camera_mode,
            "camera_source": str(camera_plan.get("camera_source") or camera_mode),
            "spawn_anchor_actor_label": spawn_anchor_actor_label,
            "camera_anchor_actor_label": camera_anchor_actor_label,
            "resolved_stage_anchors": resolved_stage_anchors,
            "output_path": str(actual_output_path or output_path),
            "requested_output_path": str(output_path),
            "output_exists": screenshot_exists,
            "file_size_bytes": actual_output_path.stat().st_size if actual_output_path and actual_output_path.exists() else 0,
            "width": width,
            "height": height,
            "delay_seconds": delay_seconds,
            "camera_plan": camera_plan,
            "capture_backend": capture_backend,
            "subject_visibility": subject_visibility,
            "subject_visible": bool(subject_visibility.get("visible")),
            "task_done": task_done,
            "warnings": warnings if screenshot_exists else warnings + ["screenshot_output_missing_after_task_completion"],
            "errors": [] if screenshot_exists else ["capture_frame_failed"],
        }
    finally:
        try:
            if hasattr(level_editor, "eject_pilot_level_actor"):
                level_editor.eject_pilot_level_actor()
        except Exception:
            pass
        try:
            if hasattr(level_editor, "set_exact_camera_view"):
                level_editor.set_exact_camera_view(False)
        except Exception:
            pass
        if temp_camera:
            try:
                actor_subsystem.destroy_actor(temp_camera)
            except Exception:
                pass
        if spawned_host:
            try:
                actor_subsystem.destroy_actor(spawned_host)
            except Exception:
                pass


def capture_frame_for_actor_object(target_actor, request: dict, output_path: Path, host_asset_path: str | None = None, host_record: dict | None = None) -> dict:
    warnings = []
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    actor_subsystem = editor_actor_subsystem()
    camera_mode = str(request.get("camera_mode") or "explicit_pose")
    if camera_mode == "explicit_pose":
        explicit_camera_location = vector_from_request(request.get("camera_location"))
        explicit_camera_rotation = rotator_from_request(request.get("camera_rotation"))
        origin, extent = actor_bounds(target_actor)
        camera_plan = {
            "camera_source": str(request.get("camera_source") or "explicit_pose"),
            "camera_location": serialize_vector(explicit_camera_location),
            "camera_rotation": serialize_rotator(explicit_camera_rotation),
            "target_location": serialize_vector(origin + unreal.Vector(0.0, 0.0, max(extent.z * 0.45, 65.0))),
            "bounds_origin": serialize_vector(origin),
            "bounds_extent": serialize_vector(extent),
        }
    else:
        camera_plan = build_capture_camera_for_actor(target_actor, request)

    camera_location = vector_from_request(camera_plan["camera_location"])
    camera_rotation = rotator_from_request(camera_plan["camera_rotation"])
    width = int(request.get("width") or request.get("capture_width") or 1280)
    height = int(request.get("height") or request.get("capture_height") or 720)
    delay_seconds = float(request.get("delay") or request.get("capture_delay_seconds") or 0.2)
    timeout_seconds = float(request.get("timeout_seconds") or 30.0)
    stability_window_seconds = float(request.get("file_stability_window_seconds") or 0.75)
    poll_interval_seconds = float(request.get("poll_interval_seconds") or 0.2)
    capture_hdr = bool(request.get("capture_hdr", False))
    force_game_view = bool(request.get("force_game_view", True))
    level_editor = level_editor_subsystem()
    temp_camera = None
    try:
        temp_camera = actor_subsystem.spawn_actor_from_class(unreal.CameraActor, camera_location, camera_rotation, True)
        if not temp_camera:
            return {
                "warnings": warnings,
                "errors": ["temporary_camera_spawn_failed"],
            }
        temp_camera.set_actor_label(f"AIUE_CaptureCamera_{sanitize_segment(target_actor.get_actor_label())}")
        subject_visibility = evaluate_subject_visibility(target_actor, temp_camera, camera_location, camera_rotation, width, height)
        if not subject_visibility.get("visible"):
            warnings.append("subject_not_visible_in_camera_plan")
        try:
            level_editor.pilot_level_actor(temp_camera)
        except Exception as exc:
            warnings.append(f"pilot_level_actor_failed:{exc}")
        try:
            if hasattr(level_editor, "set_allows_cinematic_control"):
                level_editor.set_allows_cinematic_control(True)
        except Exception:
            pass
        try:
            if hasattr(level_editor, "set_exact_camera_view"):
                level_editor.set_exact_camera_view(True)
        except Exception:
            pass
        render_target_capture = capture_to_render_target(
            temp_camera,
            width,
            height,
            output_path,
            capture_hdr,
            delay_seconds,
            timeout_seconds,
            stability_window_seconds,
            poll_interval_seconds,
        )
        warnings.extend(render_target_capture.get("warnings") or [])
        actual_output_path = Path(render_target_capture["output_path"]).resolve() if render_target_capture.get("output_path") else None
        task_done = bool(render_target_capture.get("task_done"))
        screenshot_exists = bool(render_target_capture.get("output_exists"))
        capture_backend = str(render_target_capture.get("capture_backend") or "")
        if screenshot_exists and int(render_target_capture.get("file_size_bytes") or 0) < 400000:
            warnings.append("render_target_capture_too_small_fallback_to_automation")
            screenshot_exists = False
        if not screenshot_exists:
            unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera_location, camera_rotation)
            level_editor.editor_set_viewport_realtime(True)
            try:
                level_editor.editor_set_game_view(True)
            except Exception:
                pass
            level_editor.editor_invalidate_viewports()
            task = unreal.AutomationLibrary.take_high_res_screenshot(
                width,
                height,
                str(output_path),
                temp_camera,
                False,
                capture_hdr,
                unreal.ComparisonTolerance.LOW,
                "AiUE action preview capture",
                delay_seconds,
                force_game_view,
            )
            actual_output_path, task_done = wait_for_screenshot(task, output_path, timeout_seconds, stability_window_seconds, poll_interval_seconds)
            if actual_output_path and actual_output_path != output_path:
                shutil.copyfile(actual_output_path, output_path)
                actual_output_path = output_path
            screenshot_exists = bool(actual_output_path and actual_output_path.exists())
            capture_backend = capture_backend or "automation_high_res_screenshot"
        return {
            "target_actor_label": target_actor.get_actor_label(),
            "target_actor_path": target_actor.get_path_name(),
            "host_blueprint_asset_path": host_asset_path,
            "host_record": host_record,
            "target_render_components": summarize_render_components(target_actor),
            "camera_mode": camera_mode,
            "camera_source": str(camera_plan.get("camera_source") or camera_mode),
            "output_path": str(actual_output_path or output_path),
            "requested_output_path": str(output_path),
            "output_exists": screenshot_exists,
            "file_size_bytes": actual_output_path.stat().st_size if actual_output_path and actual_output_path.exists() else 0,
            "width": width,
            "height": height,
            "delay_seconds": delay_seconds,
            "camera_plan": camera_plan,
            "capture_backend": capture_backend,
            "subject_visibility": subject_visibility,
            "subject_visible": bool(subject_visibility.get("visible")),
            "task_done": task_done,
            "warnings": warnings if screenshot_exists else warnings + ["screenshot_output_missing_after_task_completion"],
            "errors": [] if screenshot_exists else ["capture_frame_failed"],
        }
    finally:
        try:
            if hasattr(level_editor, "eject_pilot_level_actor"):
                level_editor.eject_pilot_level_actor()
        except Exception:
            pass
        try:
            if hasattr(level_editor, "set_exact_camera_view"):
                level_editor.set_exact_camera_view(False)
        except Exception:
            pass
        if temp_camera:
            try:
                actor_subsystem.destroy_actor(temp_camera)
            except Exception:
                pass


def build_visual_proof_shots(actor, request: dict) -> list[dict]:
    origin, extent = actor_bounds(actor)
    forward = actor.get_actor_forward_vector()
    right = actor.get_actor_right_vector()
    up = unreal.Vector(0.0, 0.0, 1.0)
    base_distance = max(float(request.get("camera_distance") or 0.0), max(extent.x, extent.y, 90.0) * 2.4)
    base_height = max(float(request.get("camera_height") or 0.0), max(extent.z * 1.15, 110.0))
    top_height = max(float(request.get("top_camera_height") or 0.0), base_distance * 1.65)
    target_location = origin + unreal.Vector(0.0, 0.0, max(extent.z * 0.6, 90.0))

    shot_specs = [
        {
            "shot_id": "front",
            "camera_id": "front",
            "camera_location": origin - (forward * base_distance) + (up * base_height),
        },
        {
            "shot_id": "side",
            "camera_id": "side",
            "camera_location": origin + (right * (base_distance * 0.95)) + (up * base_height),
        },
        {
            "shot_id": "top",
            "camera_id": "top",
            "camera_location": origin - (forward * (base_distance * 0.25)) + (up * top_height),
        },
    ]
    payload = []
    for item in shot_specs:
        camera_rotation = unreal.MathLibrary.find_look_at_rotation(item["camera_location"], target_location)
        payload.append(
            {
                "shot_id": item["shot_id"],
                "camera_id": item["camera_id"],
                "camera_source": "explicit_pose",
                "camera_location": serialize_vector(item["camera_location"]),
                "camera_rotation": serialize_rotator(camera_rotation),
                "target_location": serialize_vector(target_location),
            }
        )
    return payload


def actor_transform_payload(actor) -> dict:
    if not actor:
        return {
            "location": {},
            "rotation": {},
            "scale": {},
        }
    scale = None
    if hasattr(actor, "get_actor_scale3d"):
        try:
            scale = actor.get_actor_scale3d()
        except Exception:
            scale = None
    return {
        "location": serialize_vector(actor.get_actor_location()),
        "rotation": serialize_rotator(actor.get_actor_rotation()),
        "scale": serialize_vector(scale) if scale is not None else {},
    }


def transform_delta_payload(before: dict, after: dict) -> dict:
    before_location = vector_from_request(before.get("location"))
    after_location = vector_from_request(after.get("location"))
    before_rotation = rotator_from_request(before.get("rotation"))
    after_rotation = rotator_from_request(after.get("rotation"))
    delta_location = after_location - before_location
    yaw_delta = normalize_degrees(after_rotation.yaw - before_rotation.yaw)
    pitch_delta = normalize_degrees(after_rotation.pitch - before_rotation.pitch)
    roll_delta = normalize_degrees(after_rotation.roll - before_rotation.roll)
    return {
        "location_delta": serialize_vector(delta_location),
        "distance_delta": float(delta_location.length()),
        "yaw_delta": float(yaw_delta),
        "pitch_delta": float(pitch_delta),
        "roll_delta": float(roll_delta),
    }


def filtered_visual_shots(actor, request: dict) -> list[dict]:
    requested_order = [str(item) for item in (request.get("shot_order") or ["front", "side"]) if str(item)]
    requested_set = set(requested_order)
    available = {item.get("shot_id"): item for item in build_visual_proof_shots(actor, request)}
    payload = []
    for shot_id in requested_order:
        shot = available.get(shot_id)
        if shot:
            payload.append(shot)
    return payload


def capture_visual_shot(
    target_actor,
    primary_mesh,
    weapon_mesh,
    shot_plan: dict,
    output_path: Path,
    request: dict,
    fallback_actor=None,
) -> dict:
    actor_subsystem = editor_actor_subsystem()
    width = int(request.get("width") or request.get("capture_width") or 1280)
    height = int(request.get("height") or request.get("capture_height") or 720)
    subject_min_screen_coverage = float(request.get("subject_min_screen_coverage") or 0.015)
    weapon_min_screen_coverage = float(request.get("weapon_min_screen_coverage") or 0.001)
    metric_camera = actor_subsystem.spawn_actor_from_class(
        unreal.CameraActor,
        vector_from_request(shot_plan["camera_location"]),
        rotator_from_request(shot_plan["camera_rotation"]),
        True,
    )
    line_of_sight = {"clear": False, "reason": "metric_camera_spawn_failed"}
    subject_coverage = {"coverage_ratio": 0.0, "reason": "metric_camera_spawn_failed"}
    weapon_coverage = {"coverage_ratio": 0.0, "reason": "metric_camera_spawn_failed"}
    if metric_camera:
        try:
            line_of_sight = line_of_sight_to_actor(metric_camera, target_actor)
            subject_coverage = screen_coverage_for_component(primary_mesh, metric_camera, width, height, fallback_actor=fallback_actor)
            weapon_coverage = screen_coverage_for_component(weapon_mesh, metric_camera, width, height)
        finally:
            try:
                actor_subsystem.destroy_actor(metric_camera)
            except Exception:
                pass

    capture_result = capture_frame_for_actor_object(
        target_actor,
        {
            "width": width,
            "height": height,
            "camera_mode": "explicit_pose",
            "camera_source": shot_plan["camera_source"],
            "camera_location": shot_plan["camera_location"],
            "camera_rotation": shot_plan["camera_rotation"],
            "capture_delay_seconds": float(request.get("capture_delay_seconds") or 0.2),
            "timeout_seconds": float(request.get("timeout_seconds") or 15.0),
            "file_stability_window_seconds": float(request.get("file_stability_window_seconds") or 0.75),
            "poll_interval_seconds": float(request.get("poll_interval_seconds") or 0.1),
        },
        output_path,
    )
    shot_errors = list(capture_result.get("errors") or [])
    shot_warnings = list(capture_result.get("warnings") or [])
    subject_visible = bool(subject_coverage.get("coverage_ratio", 0.0) >= subject_min_screen_coverage)
    weapon_visible = bool(weapon_coverage.get("coverage_ratio", 0.0) >= weapon_min_screen_coverage)
    line_clear = bool(line_of_sight.get("clear"))
    if not subject_visible:
        shot_errors.append("out_of_frame")
    if not line_clear:
        shot_errors.append("occluded")
    if not capture_result.get("output_exists"):
        shot_errors.append("capture_failed")
    shot_status = "pass" if not shot_errors else "fail"
    return {
        "shot_id": shot_plan["shot_id"],
        "camera_id": shot_plan["camera_id"],
        "camera_source": shot_plan["camera_source"],
        "camera_location": shot_plan["camera_location"],
        "camera_rotation": shot_plan["camera_rotation"],
        "image_path": str(output_path.resolve()),
        "subject_screen_coverage": float(subject_coverage.get("coverage_ratio") or 0.0),
        "weapon_screen_coverage": float(weapon_coverage.get("coverage_ratio") or 0.0),
        "line_of_sight_clear": line_clear,
        "line_of_sight": line_of_sight,
        "subject_coverage": subject_coverage,
        "weapon_coverage": weapon_coverage,
        "capture_backend": capture_result.get("capture_backend"),
        "status": shot_status,
        "warnings": sorted(set(shot_warnings)),
        "errors": sorted(set(shot_errors)),
    }


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


def animation_asset_payload(animation_asset) -> dict:
    payload = {
        "asset_path": "",
        "class_name": "",
        "skeleton_asset_path": "",
        "play_length_seconds": 0.0,
    }
    if not animation_asset:
        return payload
    try:
        payload["asset_path"] = animation_asset.get_path_name()
    except Exception:
        pass
    try:
        payload["class_name"] = animation_asset.get_class().get_name()
    except Exception:
        pass
    skeleton_asset = None
    for method_name in ("get_skeleton",):
        if hasattr(animation_asset, method_name):
            try:
                skeleton_asset = getattr(animation_asset, method_name)()
                if skeleton_asset:
                    break
            except Exception:
                continue
    if not skeleton_asset and hasattr(animation_asset, "get_editor_property"):
        try:
            skeleton_asset = animation_asset.get_editor_property("skeleton")
        except Exception:
            skeleton_asset = None
    if skeleton_asset:
        try:
            payload["skeleton_asset_path"] = skeleton_asset.get_path_name()
        except Exception:
            pass
    for method_name in ("get_play_length",):
        if hasattr(animation_asset, method_name):
            try:
                payload["play_length_seconds"] = float(getattr(animation_asset, method_name)())
                break
            except Exception:
                continue
    if not payload["play_length_seconds"] and hasattr(animation_asset, "get_editor_property"):
        for property_name in ("sequence_length", "target_frame_rate"):
            try:
                raw_value = animation_asset.get_editor_property(property_name)
                if property_name == "sequence_length":
                    payload["play_length_seconds"] = float(raw_value or 0.0)
                    if payload["play_length_seconds"] > 0.0:
                        break
            except Exception:
                continue
    return payload


def load_asset_from_any_path(asset_path: str):
    if not asset_path:
        return None
    candidates = [str(asset_path)]
    if "." not in str(asset_path) and str(asset_path).startswith("/Game/"):
        candidates.append(object_path_from_asset_path(str(asset_path)))
    for candidate in candidates:
        try:
            asset = unreal.EditorAssetLibrary.load_asset(candidate)
        except Exception:
            asset = None
        if asset:
            return asset
    return None


def canonical_asset_path(asset_path: str) -> str:
    text = str(asset_path or "").strip()
    if not text:
        return ""
    tail = text.rsplit("/", 1)[-1]
    if "." in tail:
        return text.split(".", 1)[0]
    return text


def package_path_and_asset_name(asset_path: str) -> tuple[str, str]:
    normalized = canonical_asset_path(asset_path)
    if "/" not in normalized:
        return "", normalized
    package_path, asset_name = normalized.rsplit("/", 1)
    return package_path, asset_name


def skeletal_mesh_asset_from_component(component):
    if not component:
        return None
    for method_name in ("get_skeletal_mesh_asset",):
        if hasattr(component, method_name):
            try:
                skeletal_mesh_asset = getattr(component, method_name)()
                if skeletal_mesh_asset:
                    return skeletal_mesh_asset
            except Exception:
                continue
    if hasattr(component, "get_editor_property"):
        for property_name in ("skeletal_mesh_asset", "skeletal_mesh"):
            try:
                skeletal_mesh_asset = component.get_editor_property(property_name)
                if skeletal_mesh_asset:
                    return skeletal_mesh_asset
            except Exception:
                continue
    return None


def skeleton_asset_from_skeletal_mesh_asset(skeletal_mesh_asset):
    if not skeletal_mesh_asset:
        return None
    for method_name in ("get_skeleton",):
        if hasattr(skeletal_mesh_asset, method_name):
            try:
                skeleton_asset = getattr(skeletal_mesh_asset, method_name)()
                if skeleton_asset:
                    return skeleton_asset
            except Exception:
                continue
    if hasattr(skeletal_mesh_asset, "get_editor_property"):
        try:
            skeleton_asset = skeletal_mesh_asset.get_editor_property("skeleton")
            if skeleton_asset:
                return skeleton_asset
        except Exception:
            pass
    return None


def component_skeletal_mesh_and_skeleton_paths(component) -> tuple[str, str]:
    skeletal_mesh_asset = skeletal_mesh_asset_from_component(component)
    skeleton_asset = skeleton_asset_from_skeletal_mesh_asset(skeletal_mesh_asset)
    skeletal_mesh_path = ""
    skeleton_path = ""
    if skeletal_mesh_asset:
        try:
            skeletal_mesh_path = skeletal_mesh_asset.get_path_name()
        except Exception:
            skeletal_mesh_path = ""
    if skeleton_asset:
        try:
            skeleton_path = skeleton_asset.get_path_name()
        except Exception:
            skeleton_path = ""
    return skeletal_mesh_path, skeleton_path


def mesh_skeleton_payload(component) -> dict:
    payload = {
        "mesh_asset_path": component_asset_path(component),
        "skeleton_asset_path": "",
    }
    if not component:
        return payload
    skeletal_mesh_asset = skeletal_mesh_asset_from_component(component)
    skeleton_asset = skeleton_asset_from_skeletal_mesh_asset(skeletal_mesh_asset)
    if skeleton_asset:
        try:
            payload["skeleton_asset_path"] = skeleton_asset.get_path_name()
        except Exception:
            pass
    return payload


def compatible_skeleton_paths(skeleton_asset) -> list[str]:
    if not skeleton_asset or not hasattr(skeleton_asset, "get_editor_property"):
        return []
    resolved = []
    try:
        items = list(skeleton_asset.get_editor_property("compatible_skeletons") or [])
    except Exception:
        items = []
    for item in items:
        try:
            path = item.get_path_name()
        except Exception:
            path = ""
        if path:
            resolved.append(path)
    return sorted(set(resolved))


def normalize_bone_name(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or "")).lower()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u4e00-\u9fff]+", "", normalized)


CANONICAL_HUMANOID_MARKERS = {
    "root": ["root"],
    "pelvis": ["pelvis", "hips", "hip", "center", "waist"],
    "spine_lower": ["spine", "spine1", "spine01", "spinelower"],
    "spine_upper": ["spine2", "spine02", "spine3", "spine03", "chest", "upperchest"],
    "neck": ["neck"],
    "head": ["head"],
    "arm_l": ["upperarml", "leftarm", "lupperarm", "arml", "leftupperarm"],
    "arm_r": ["upperarmr", "rightarm", "rupperarm", "armr", "rightupperarm"],
    "hand_l": ["handl", "lefthand", "lhand"],
    "hand_r": ["handr", "righthand", "rhand"],
    "leg_l": ["thighl", "uplegl", "leftleg", "lthigh", "leftupleg"],
    "leg_r": ["thighr", "uplegr", "rightleg", "rthigh", "rightupleg"],
    "foot_l": ["footl", "leftfoot", "lfoot"],
    "foot_r": ["footr", "rightfoot", "rfoot"],
}


def reference_skeleton_from_assets(skeleton_asset=None, skeletal_mesh_asset=None):
    for owner in (skeletal_mesh_asset, skeleton_asset):
        if not owner:
            continue
        for method_name in ("get_reference_skeleton", "get_ref_skeleton"):
            if hasattr(owner, method_name):
                try:
                    reference_skeleton = getattr(owner, method_name)()
                    if reference_skeleton:
                        return reference_skeleton
                except Exception:
                    continue
        if hasattr(owner, "get_editor_property"):
            for property_name in ("reference_skeleton", "ref_skeleton"):
                try:
                    reference_skeleton = owner.get_editor_property(property_name)
                    if reference_skeleton:
                        return reference_skeleton
                except Exception:
                    continue
    return None


def reference_skeleton_bone_names(reference_skeleton) -> tuple[list[str], str]:
    if not reference_skeleton:
        return [], "missing_reference_skeleton"
    for method_name in ("get_raw_bone_names", "get_bone_names"):
        if hasattr(reference_skeleton, method_name):
            try:
                names = [str(item) for item in list(getattr(reference_skeleton, method_name)() or []) if str(item)]
            except Exception:
                names = []
            if names:
                return names, f"reference_skeleton:{method_name}"
    if hasattr(reference_skeleton, "get_editor_property"):
        for property_name in ("raw_bone_names", "bone_names"):
            try:
                raw_names = list(reference_skeleton.get_editor_property(property_name) or [])
            except Exception:
                raw_names = []
            names = [str(item) for item in raw_names if str(item)]
            if names:
                return names, f"reference_skeleton_property:{property_name}"
    count = 0
    for method_name in ("get_num", "get_raw_bone_num", "get_bone_count"):
        if hasattr(reference_skeleton, method_name):
            try:
                count = int(getattr(reference_skeleton, method_name)() or 0)
            except Exception:
                count = 0
            if count:
                break
    if count and hasattr(reference_skeleton, "get_bone_name"):
        names = []
        for index in range(count):
            try:
                bone_name = str(reference_skeleton.get_bone_name(index))
            except Exception:
                bone_name = ""
            if bone_name:
                names.append(bone_name)
        if names:
            return names, "reference_skeleton:indexed"
    return [], "reference_skeleton_unresolved"


def skeleton_bone_names(skeleton_asset=None, skeletal_mesh_asset=None) -> tuple[list[str], str]:
    reference_skeleton = reference_skeleton_from_assets(skeleton_asset, skeletal_mesh_asset)
    names, source = reference_skeleton_bone_names(reference_skeleton)
    if names:
        return names, source
    skeleton_owner = skeleton_asset
    if not skeleton_owner and skeletal_mesh_asset:
        try:
            skeleton_owner = getattr(skeletal_mesh_asset, "skeleton")
        except Exception:
            skeleton_owner = None
        if not skeleton_owner and hasattr(skeletal_mesh_asset, "get_editor_property"):
            try:
                skeleton_owner = skeletal_mesh_asset.get_editor_property("skeleton")
            except Exception:
                skeleton_owner = None
    if skeleton_owner and hasattr(skeleton_owner, "get_reference_pose"):
        try:
            reference_pose = skeleton_owner.get_reference_pose()
        except Exception:
            reference_pose = None
        if reference_pose and hasattr(reference_pose, "get_bone_names"):
            try:
                pose_names = [str(item) for item in list(reference_pose.get_bone_names() or []) if str(item)]
            except Exception:
                pose_names = []
            if pose_names:
                return pose_names, "reference_pose:get_bone_names"
    if skeleton_asset and hasattr(skeleton_asset, "get_editor_property"):
        try:
            bone_tree = list(skeleton_asset.get_editor_property("bone_tree") or [])
        except Exception:
            bone_tree = []
        extracted = []
        for entry in bone_tree:
            bone_name = ""
            for attribute_name in ("name", "bone_name"):
                try:
                    value = getattr(entry, attribute_name)
                    bone_name = str(value) if value else ""
                except Exception:
                    bone_name = ""
                if bone_name:
                    break
            if bone_name:
                extracted.append(bone_name)
        if extracted:
            return extracted, "skeleton:bone_tree"
    return [], source


def skeleton_socket_names(skeleton_asset) -> list[str]:
    if not skeleton_asset or not hasattr(skeleton_asset, "get_editor_property"):
        return []
    try:
        sockets = list(skeleton_asset.get_editor_property("sockets") or [])
    except Exception:
        sockets = []
    names = []
    for socket in sockets:
        try:
            socket_name = str(socket.get_editor_property("socket_name"))
        except Exception:
            socket_name = ""
        if socket_name:
            names.append(socket_name)
    return sorted(set(names))


def humanoid_marker_summary(bone_names: list[str]) -> dict:
    normalized = {}
    for raw_name in bone_names:
        key = normalize_bone_name(raw_name)
        if key and key not in normalized:
            normalized[key] = str(raw_name)
    hits = {}
    for marker, aliases in CANONICAL_HUMANOID_MARKERS.items():
        matched_name = ""
        for alias in aliases:
            alias_key = normalize_bone_name(alias)
            if alias_key in normalized:
                matched_name = normalized[alias_key]
                break
        hits[marker] = matched_name
    matched = sorted([marker for marker, name in hits.items() if name])
    missing = sorted([marker for marker, name in hits.items() if not name])
    core_markers = ["pelvis", "head", "arm_l", "arm_r", "leg_l", "leg_r"]
    core_present = sorted([marker for marker in core_markers if hits.get(marker)])
    return {
        "matched_markers": matched,
        "missing_markers": missing,
        "marker_hits": hits,
        "canonical_marker_score": round(float(len(matched)) / float(len(CANONICAL_HUMANOID_MARKERS)), 4),
        "core_chain_markers_present": len(core_present),
        "core_chain_markers_total": len(core_markers),
        "core_ready": len(core_present) >= 4,
        "manual_chain_mapping_likely": len(core_present) < 6,
    }


def skeleton_profile_payload_from_assets(skeleton_asset=None, skeletal_mesh_asset=None) -> dict:
    bone_names, bone_source = skeleton_bone_names(skeleton_asset, skeletal_mesh_asset)
    socket_names = skeleton_socket_names(skeleton_asset)
    payload = {
        "skeleton_asset_path": "",
        "skeletal_mesh_asset_path": "",
        "preview_mesh_asset_path": "",
        "bone_count": len(bone_names),
        "root_bone_name": bone_names[0] if bone_names else "",
        "bone_name_source": bone_source,
        "bone_name_sample": bone_names[:24],
        "socket_count": len(socket_names),
        "socket_names": socket_names[:24],
        "humanoid_markers": humanoid_marker_summary(bone_names),
        "warnings": [],
    }
    if skeleton_asset:
        try:
            payload["skeleton_asset_path"] = skeleton_asset.get_path_name()
        except Exception:
            pass
        if hasattr(skeleton_asset, "get_preview_mesh"):
            try:
                preview_mesh = skeleton_asset.get_preview_mesh()
            except Exception:
                preview_mesh = None
            if preview_mesh:
                try:
                    payload["preview_mesh_asset_path"] = preview_mesh.get_path_name()
                except Exception:
                    pass
    if skeletal_mesh_asset:
        try:
            payload["skeletal_mesh_asset_path"] = skeletal_mesh_asset.get_path_name()
        except Exception:
            pass
    if not bone_names:
        payload["warnings"].append("bone_names_unresolved")
    return payload


def skeleton_profile_payload_from_component(component) -> dict:
    skeletal_mesh_asset = skeletal_mesh_asset_from_component(component)
    skeleton_asset = skeleton_asset_from_skeletal_mesh_asset(skeletal_mesh_asset)
    payload = skeleton_profile_payload_from_assets(skeleton_asset, skeletal_mesh_asset)
    payload["component_mesh_asset_path"] = component_asset_path(component)
    return payload


def animation_skeleton_profile_payload(animation_asset) -> dict:
    animation_payload = animation_asset_payload(animation_asset)
    skeleton_asset = load_asset_from_any_path(animation_payload.get("skeleton_asset_path") or "")
    payload = skeleton_profile_payload_from_assets(skeleton_asset)
    payload["animation_asset_path"] = animation_payload.get("asset_path") or ""
    payload["animation_class_name"] = animation_payload.get("class_name") or ""
    payload["animation_play_length_seconds"] = float(animation_payload.get("play_length_seconds") or 0.0)
    return payload


def asset_entries_by_class_names(asset_root: str, class_names: set[str], limit: int = 500) -> list[dict]:
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    assets = list(registry.get_assets_by_path(to_name(asset_root), recursive=True))
    entries = []
    for asset_data in assets:
        class_name = asset_class_name(asset_data)
        if class_name not in class_names:
            continue
        entries.append(
            {
                "object_path": asset_object_path(asset_data),
                "package_name": str(asset_data.package_name),
                "asset_name": str(asset_data.asset_name),
                "asset_class": class_name,
            }
        )
    entries = sorted(entries, key=lambda item: item["object_path"])
    return entries[:limit]


def struct_field_value(struct_value, field_names: list[str]):
    for field_name in field_names:
        try:
            value = getattr(struct_value, field_name)
        except Exception:
            value = None
        if value not in (None, ""):
            return value
        if hasattr(struct_value, "get_editor_property"):
            try:
                value = struct_value.get_editor_property(field_name)
            except Exception:
                value = None
            if value not in (None, ""):
                return value
    return None


def ik_rig_chain_records(controller) -> list[dict]:
    try:
        raw_chains = list(controller.get_retarget_chains() or [])
    except Exception:
        raw_chains = []
    records = []
    for chain in raw_chains:
        chain_name = str(struct_field_value(chain, ["chain_name", "chain"]) or "")
        start_bone = ""
        end_bone = ""
        goal_name = ""
        if chain_name:
            try:
                start_bone = str(controller.get_retarget_chain_start_bone(to_name(chain_name)) or "")
            except Exception:
                start_bone = ""
            try:
                end_bone = str(controller.get_retarget_chain_end_bone(to_name(chain_name)) or "")
            except Exception:
                end_bone = ""
            try:
                goal_name = str(controller.get_retarget_chain_goal(to_name(chain_name)) or "")
            except Exception:
                goal_name = ""
        if not start_bone:
            start_bone = str(struct_field_value(chain, ["start_bone_name"]) or "")
        if not end_bone:
            end_bone = str(struct_field_value(chain, ["end_bone_name"]) or "")
        if not goal_name:
            goal_name = str(struct_field_value(chain, ["ik_goal_name", "goal_name"]) or "")
        records.append(
            {
                "chain_name": chain_name,
                "start_bone": start_bone,
                "end_bone": end_bone,
                "goal_name": goal_name,
            }
        )
    return records


def ik_rig_profile_payload(ik_rig_asset) -> dict:
    if not ik_rig_asset:
        return {
            "asset_path": "",
            "skeletal_mesh_asset_path": "",
            "skeleton_asset_path": "",
            "retarget_root": "",
            "chain_count": 0,
            "chains": [],
        }
    controller = unreal.IKRigController.get_controller(ik_rig_asset)
    skeletal_mesh_asset = controller.get_skeletal_mesh() if controller else None
    skeletal_mesh_path = ""
    skeleton_path = ""
    if skeletal_mesh_asset:
        try:
            skeletal_mesh_path = skeletal_mesh_asset.get_path_name()
        except Exception:
            skeletal_mesh_path = ""
        skeleton_asset = skeleton_asset_from_skeletal_mesh_asset(skeletal_mesh_asset)
        if skeleton_asset:
            try:
                skeleton_path = skeleton_asset.get_path_name()
            except Exception:
                skeleton_path = ""
    retarget_root = ""
    if controller:
        try:
            retarget_root = str(controller.get_retarget_root() or "")
        except Exception:
            retarget_root = ""
    chains = ik_rig_chain_records(controller) if controller else []
    asset_path = ""
    try:
        asset_path = canonical_asset_path(ik_rig_asset.get_path_name())
    except Exception:
        asset_path = ""
    return {
        "asset_path": asset_path,
        "skeletal_mesh_asset_path": skeletal_mesh_path,
        "skeleton_asset_path": skeleton_path,
        "retarget_root": retarget_root,
        "chain_count": len(chains),
        "chains": chains,
    }


def base_name_from_asset_path(asset_path: str) -> str:
    text = str(asset_path or "")
    if not text:
        return ""
    package_name = text.split(".", 1)[0]
    return package_name.rsplit("/", 1)[-1]


def matching_asset_entries(entries: list[dict], keywords: list[str], class_name: str | None = None) -> list[dict]:
    lowered_keywords = [str(item).strip().lower() for item in keywords if str(item).strip()]
    matched = []
    for entry in entries:
        if class_name and entry.get("asset_class") != class_name:
            continue
        haystack = " ".join([entry.get("object_path") or "", entry.get("package_name") or "", entry.get("asset_name") or ""]).lower()
        if not lowered_keywords or any(keyword in haystack for keyword in lowered_keywords):
            matched.append(entry)
    return matched


def retarget_tooling_inventory(sample_id: str, package_id: str, source_profile: dict, target_profile: dict) -> dict:
    entries = asset_entries_by_class_names("/Game", {"IKRigDefinition", "IKRetargeter"}, limit=500)
    source_keywords = [
        sample_id,
        package_id,
        base_name_from_asset_path(source_profile.get("skeleton_asset_path") or ""),
        "pmxpipeline",
    ]
    target_keywords = [
        "mannequin",
        base_name_from_asset_path(target_profile.get("skeleton_asset_path") or ""),
        base_name_from_asset_path(target_profile.get("preview_mesh_asset_path") or ""),
    ]
    retargeter_keywords = source_keywords + target_keywords + ["retarget"]
    return {
        "ik_rig_definition_available": hasattr(unreal, "IKRigDefinition"),
        "ik_retargeter_available": hasattr(unreal, "IKRetargeter"),
        "can_author_new_retarget_assets": bool(hasattr(unreal, "IKRigDefinition") and hasattr(unreal, "IKRetargeter")),
        "project_asset_counts": {
            "ik_rigs": sum(1 for entry in entries if entry.get("asset_class") == "IKRigDefinition"),
            "ik_retargeters": sum(1 for entry in entries if entry.get("asset_class") == "IKRetargeter"),
        },
        "matching_source_ik_rigs": matching_asset_entries(entries, source_keywords, class_name="IKRigDefinition")[:16],
        "matching_target_ik_rigs": matching_asset_entries(entries, target_keywords, class_name="IKRigDefinition")[:16],
        "matching_retargeters": matching_asset_entries(entries, retargeter_keywords, class_name="IKRetargeter")[:16],
        "asset_sample": entries[:24],
    }


def retarget_recommendations(compatibility: dict, source_profile: dict, target_profile: dict, tooling: dict) -> list[str]:
    recommendations = []
    if compatibility.get("compatible"):
        recommendations.append("Direct skeleton compatibility already exists; you can skip retarget setup and move straight to a real animation preview.")
        return recommendations
    if not tooling.get("can_author_new_retarget_assets"):
        recommendations.append("Enable the IKRig plugin in AiUEdemo so Unreal exposes IKRigDefinition and IKRetargeter authoring APIs.")
    if source_profile.get("skeleton_asset_path"):
        recommendations.append(f"Create a source IKRig for the imported PMX skeleton: {source_profile.get('skeleton_asset_path')}.")
    if target_profile.get("skeleton_asset_path"):
        recommendations.append(f"Create or reuse a target mannequin IKRig for: {target_profile.get('skeleton_asset_path')}.")
    if not tooling.get("matching_retargeters"):
        recommendations.append("Create an IKRetargeter that maps the imported PMX rig to the mannequin rig before retrying animation-preview.")
    if (source_profile.get("humanoid_markers") or {}).get("manual_chain_mapping_likely"):
        recommendations.append("Expect manual retarget chain setup because the imported skeleton does not expose the full set of canonical humanoid bone names.")
    if not recommendations:
        recommendations.append("Inspect existing IKRig and IKRetargeter assets in the project and bind the imported skeleton to the closest mannequin retarget path.")
    return recommendations


def resolve_enum_member(enum_type_names: tuple[str, ...], member_names: tuple[str, ...]):
    for enum_name in enum_type_names:
        enum_type = getattr(unreal, enum_name, None)
        if not enum_type:
            continue
        for member_name in member_names:
            if hasattr(enum_type, member_name):
                return getattr(enum_type, member_name)
    return None


def retarget_source_enum_value():
    return resolve_enum_member(("RetargetSourceOrTarget", "ERetargetSourceOrTarget"), ("Source", "SOURCE"))


def retarget_target_enum_value():
    return resolve_enum_member(("RetargetSourceOrTarget", "ERetargetSourceOrTarget"), ("Target", "TARGET"))


def auto_map_chain_type_value():
    return resolve_enum_member(("AutoMapChainType", "EAutoMapChainType"), ("Exact", "EXACT", "Fuzzy", "FUZZY"))


SOURCE_CHAIN_SPECS = [
    {
        "chain_name": "root",
        "start_aliases": [["root"], ["全ての親"], ["センター"], ["center"], ["groove"]],
        "end_aliases": [["hips"], ["pelvis"], ["下半身"], ["腰"], ["center"]],
        "allow_same_bone": True,
    },
    {
        "chain_name": "Spine",
        "start_aliases": [["spine", "1"], ["上半身"], ["spine"]],
        "end_aliases": [["spine", "2"], ["上半身2"], ["chest"], ["spine", "3"], ["upper", "chest"]],
        "allow_same_bone": False,
    },
    {
        "chain_name": "Neck",
        "start_aliases": [["neck"], ["首"]],
        "end_aliases": [["neck"], ["首"]],
        "allow_same_bone": True,
    },
    {
        "chain_name": "head",
        "start_aliases": [["head"], ["頭"]],
        "end_aliases": [["head"], ["頭"]],
        "allow_same_bone": True,
    },
    {
        "chain_name": "LeftClavicle",
        "start_aliases": [["left", "clavicle"], ["clavicle", "l"], ["left", "shoulder"], ["左肩"]],
        "end_aliases": [["left", "clavicle"], ["clavicle", "l"], ["left", "shoulder"], ["左肩"]],
        "allow_same_bone": True,
    },
    {
        "chain_name": "RightClavicle",
        "start_aliases": [["right", "clavicle"], ["clavicle", "r"], ["right", "shoulder"], ["右肩"]],
        "end_aliases": [["right", "clavicle"], ["clavicle", "r"], ["right", "shoulder"], ["右肩"]],
        "allow_same_bone": True,
    },
    {
        "chain_name": "LeftArm",
        "start_aliases": [["left", "upper", "arm"], ["upperarm", "l"], ["arm", "l"], ["左腕"]],
        "end_aliases": [["left", "hand"], ["hand", "l"], ["左手首"], ["左手"]],
        "allow_same_bone": False,
    },
    {
        "chain_name": "RightArm",
        "start_aliases": [["right", "upper", "arm"], ["upperarm", "r"], ["arm", "r"], ["右腕"]],
        "end_aliases": [["right", "hand"], ["hand", "r"], ["右手首"], ["右手"]],
        "allow_same_bone": False,
    },
    {
        "chain_name": "LeftLeg",
        "start_aliases": [["left", "thigh"], ["thigh", "l"], ["left", "leg"], ["左足"], ["左足上"]],
        "end_aliases": [["left", "foot"], ["foot", "l"], ["左足首"], ["左足"]],
        "allow_same_bone": False,
    },
    {
        "chain_name": "RightLeg",
        "start_aliases": [["right", "thigh"], ["thigh", "r"], ["right", "leg"], ["右足"], ["右足上"]],
        "end_aliases": [["right", "foot"], ["foot", "r"], ["右足首"], ["右足"]],
        "allow_same_bone": False,
    },
    {
        "chain_name": "LeftToe",
        "start_aliases": [["left", "toe"], ["toe", "l"], ["左つま先"]],
        "end_aliases": [["left", "toe"], ["toe", "l"], ["左つま先"]],
        "allow_same_bone": True,
    },
    {
        "chain_name": "RightToe",
        "start_aliases": [["right", "toe"], ["toe", "r"], ["右つま先"]],
        "end_aliases": [["right", "toe"], ["toe", "r"], ["右つま先"]],
        "allow_same_bone": True,
    },
]


def numeric_suffix(text: str) -> int:
    match = re.search(r"(\d+)$", str(text or ""))
    return int(match.group(1)) if match else -1


def pmx_plain_side_bones(bone_names: list[str], side_token: str) -> list[str]:
    pattern = re.compile(rf"^Bone_{re.escape(side_token)}_(\d+)$", re.IGNORECASE)
    matched = []
    for bone_name in bone_names:
        if pattern.match(str(bone_name or "")):
            matched.append(str(bone_name))
    matched.sort(key=numeric_suffix)
    return matched


def pmx_neutral_numbered_bones(bone_names: list[str]) -> list[str]:
    pattern = re.compile(r"^Bone_(\d+)$", re.IGNORECASE)
    matched = []
    for bone_name in bone_names:
        if pattern.match(str(bone_name or "")):
            matched.append(str(bone_name))
    matched.sort(key=numeric_suffix)
    return matched


def pmx_numbered_prefix_groups(bone_names: list[str], limit: int = 12) -> list[dict]:
    grouped = {}
    for bone_name in bone_names:
        text = str(bone_name or "")
        match = re.match(r"^(.*?)(\d+)$", text)
        if not match:
            continue
        prefix = match.group(1)
        grouped.setdefault(prefix, []).append(text)
    records = []
    for prefix, names in grouped.items():
        ordered = sorted(names, key=numeric_suffix)
        records.append(
            {
                "prefix": prefix,
                "count": len(ordered),
                "sample": ordered[: min(8, len(ordered))],
            }
        )
    records.sort(key=lambda item: (-int(item["count"]), item["prefix"]))
    return records[:limit]


def pmx_upper_body_fallback_chains(bone_names: list[str]) -> tuple[list[dict], list[str], dict]:
    planned = []
    warnings = []
    diagnostics = {
        "strategy": "pmx_numeric_upper_body",
        "plain_right_bones": pmx_plain_side_bones(bone_names, "R"),
        "plain_left_bones": pmx_plain_side_bones(bone_names, "L"),
        "neutral_numbered_bones": pmx_neutral_numbered_bones(bone_names),
    }

    def add_chain(chain_name: str, start_bone: str, end_bone: str, reason: str) -> None:
        if not start_bone or not end_bone:
            return
        planned.append(
            {
                "chain_name": chain_name,
                "start_bone": start_bone,
                "end_bone": end_bone,
                "goal_name": "",
                "planning_reason": reason,
            }
        )

    groove_bone = pick_best_bone_name(bone_names, [["groove"], ["center"], ["鍏ㄣ仸銇Κ"], ["銈汇兂銈裤兗"]])
    waist_bone = pick_best_bone_name(bone_names, [["waist"], ["鑵"], ["涓嬪崐韜"]])
    neutral_numbered = diagnostics["neutral_numbered_bones"]
    first_neutral = neutral_numbered[0] if neutral_numbered else ""
    second_neutral = neutral_numbered[1] if len(neutral_numbered) > 1 else ""
    if groove_bone:
        add_chain("root", groove_bone, groove_bone, "pmx_generic_root")
    if waist_bone and first_neutral and waist_bone != first_neutral:
        add_chain("Spine", waist_bone, first_neutral, "pmx_generic_waist_to_first_neutral")
    elif waist_bone and second_neutral and waist_bone != second_neutral:
        add_chain("Spine", waist_bone, second_neutral, "pmx_generic_waist_to_second_neutral")

    right_plain = diagnostics["plain_right_bones"]
    left_plain = diagnostics["plain_left_bones"]
    if len(right_plain) >= 1:
        add_chain("RightClavicle", right_plain[0], right_plain[0], "pmx_plain_r_first")
    if len(right_plain) >= 4:
        add_chain("RightArm", right_plain[1], right_plain[4] if len(right_plain) >= 5 else right_plain[-1], "pmx_plain_r_arm_span")
    elif len(right_plain) >= 3:
        add_chain("RightArm", right_plain[1], right_plain[-1], "pmx_plain_r_arm_short")
    if len(left_plain) >= 1:
        add_chain("LeftClavicle", left_plain[0], left_plain[0], "pmx_plain_l_first")
    if len(left_plain) >= 4:
        add_chain("LeftArm", left_plain[1], left_plain[4] if len(left_plain) >= 5 else left_plain[-1], "pmx_plain_l_arm_span")
    elif len(left_plain) >= 3:
        add_chain("LeftArm", left_plain[1], left_plain[-1], "pmx_plain_l_arm_short")

    if not any(item["chain_name"] == "RightArm" for item in planned):
        warnings.append("pmx_upper_body_fallback_right_arm_unresolved")
    if not any(item["chain_name"] == "LeftArm" for item in planned):
        warnings.append("pmx_upper_body_fallback_left_arm_unresolved")
    return planned, warnings, diagnostics


def bone_names_from_ik_rig_controller(controller) -> tuple[list[str], str]:
    if not controller:
        return [], "controller_missing"
    try:
        skeletal_mesh_asset = controller.get_skeletal_mesh()
    except Exception:
        skeletal_mesh_asset = None
    if not skeletal_mesh_asset:
        return [], "ik_rig_skeletal_mesh_missing"
    skeleton_asset = skeleton_asset_from_skeletal_mesh_asset(skeletal_mesh_asset)
    try:
        direct_skeleton = skeletal_mesh_asset.skeleton
        if direct_skeleton:
            skeleton_asset = direct_skeleton
    except Exception:
        pass
    if skeleton_asset and hasattr(skeleton_asset, "get_reference_pose"):
        try:
            reference_pose = skeleton_asset.get_reference_pose()
        except Exception:
            reference_pose = None
        if reference_pose and hasattr(reference_pose, "get_bone_names"):
            try:
                names = [str(item) for item in list(reference_pose.get_bone_names() or []) if str(item)]
            except Exception:
                names = []
            if names:
                return names, "ik_rig_skeletal_mesh.skeleton.reference_pose"
    return skeleton_bone_names(skeleton_asset, skeletal_mesh_asset)


def pick_best_bone_name(bone_names: list[str], alias_groups: list[list[str]]) -> str:
    normalized_pairs = [(str(name), normalize_bone_name(name)) for name in bone_names if str(name)]
    best_name = ""
    best_score = -1
    for original_name, normalized_name in normalized_pairs:
        for alias_group in alias_groups:
            if not alias_group:
                continue
            score = 0
            for alias in alias_group:
                alias_key = normalize_bone_name(alias)
                if alias_key and alias_key in normalized_name:
                    score += len(alias_key)
                else:
                    score = -1
                    break
            if score > best_score:
                best_score = score
                best_name = original_name
    return best_name if best_score > 0 else ""


def planned_source_chain_records(bone_names: list[str]) -> tuple[list[dict], list[str], dict]:
    planned = []
    warnings = []
    alias_match_records = []
    for spec in SOURCE_CHAIN_SPECS:
        start_bone = pick_best_bone_name(bone_names, spec["start_aliases"])
        end_bone = pick_best_bone_name(bone_names, spec["end_aliases"])
        if not start_bone and end_bone:
            start_bone = end_bone
        if not end_bone and start_bone and spec.get("allow_same_bone"):
            end_bone = start_bone
        if not start_bone or not end_bone:
            warnings.append(f"source_chain_unresolved:{spec['chain_name']}")
            continue
        if start_bone == end_bone and not spec.get("allow_same_bone"):
            warnings.append(f"source_chain_same_bone_skipped:{spec['chain_name']}:{start_bone}")
            continue
        planned.append(
            {
                "chain_name": spec["chain_name"],
                "start_bone": start_bone,
                "end_bone": end_bone,
                "goal_name": "",
                "planning_reason": "alias_match",
            }
        )
        alias_match_records.append(
            {
                "chain_name": spec["chain_name"],
                "start_bone": start_bone,
                "end_bone": end_bone,
            }
        )

    planned_by_name = {entry["chain_name"]: dict(entry) for entry in planned}
    pmx_fallback_plans, pmx_warnings, pmx_diagnostics = pmx_upper_body_fallback_chains(bone_names)
    warnings.extend(pmx_warnings)
    for fallback in pmx_fallback_plans:
        chain_name = str(fallback.get("chain_name") or "")
        if chain_name and chain_name not in planned_by_name:
            planned_by_name[chain_name] = dict(fallback)

    preferred_order = [str(spec.get("chain_name") or "") for spec in SOURCE_CHAIN_SPECS]
    planned = []
    for chain_name in preferred_order:
        if chain_name and chain_name in planned_by_name:
            planned.append(planned_by_name[chain_name])
    for chain_name, payload in planned_by_name.items():
        if chain_name not in preferred_order:
            planned.append(payload)

    diagnostics = {
        "alias_match_records": alias_match_records,
        "pmx_fallback": pmx_diagnostics,
        "numbered_prefix_groups": pmx_numbered_prefix_groups(bone_names),
        "planned_chain_names": [item.get("chain_name") for item in planned if item.get("chain_name")],
    }
    return planned, warnings, diagnostics


def create_or_load_ik_rig_asset(asset_path: str):
    normalized = canonical_asset_path(asset_path)
    existing = load_asset_from_any_path(normalized)
    if existing:
        return existing, False
    package_path, asset_name = package_path_and_asset_name(normalized)
    ensure_directory(package_path)
    created = unreal.IKRigDefinitionFactory.create_new_ik_rig_asset(package_path, asset_name)
    return created, True


def create_or_load_retargeter_asset(asset_path: str):
    normalized = canonical_asset_path(asset_path)
    existing = load_asset_from_any_path(normalized)
    if existing:
        return existing, False
    package_path, asset_name = package_path_and_asset_name(normalized)
    ensure_directory(package_path)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    created = asset_tools.create_asset(asset_name, package_path, unreal.IKRetargeter, unreal.IKRetargetFactory())
    return created, True


def choose_target_ik_rig_asset(animation_asset, preferred_asset_path: str = "") -> tuple[object | None, dict]:
    if preferred_asset_path:
        preferred_asset = load_asset_from_any_path(preferred_asset_path)
        if preferred_asset:
            return preferred_asset, {
                "selection_mode": "preferred_asset_path",
                "requested_asset_path": preferred_asset_path,
                "resolved_asset_path": canonical_asset_path(preferred_asset.get_path_name()),
                "candidate_count": 1,
            }
    animation_payload = animation_asset_payload(animation_asset)
    animation_skeleton_path = str(animation_payload.get("skeleton_asset_path") or "")
    entries = asset_entries_by_class_names("/Game", {"IKRigDefinition"}, limit=500)
    best_asset = None
    best_metadata = None
    best_score = -1
    for entry in entries:
        asset = load_asset_from_any_path(entry["object_path"])
        if not asset:
            continue
        controller = unreal.IKRigController.get_controller(asset)
        if not controller:
            continue
        try:
            skeletal_mesh_asset = controller.get_skeletal_mesh()
        except Exception:
            skeletal_mesh_asset = None
        skeletal_mesh_path = ""
        skeleton_path = ""
        if skeletal_mesh_asset:
            try:
                skeletal_mesh_path = skeletal_mesh_asset.get_path_name()
            except Exception:
                skeletal_mesh_path = ""
            skeleton_asset = skeleton_asset_from_skeletal_mesh_asset(skeletal_mesh_asset)
            if skeleton_asset:
                try:
                    skeleton_path = skeleton_asset.get_path_name()
                except Exception:
                    skeleton_path = ""
        score = 0
        reasons = []
        if animation_skeleton_path and skeleton_path and animation_skeleton_path == skeleton_path:
            score += 100
            reasons.append("exact_animation_skeleton_match")
        lowered = " ".join([entry.get("object_path") or "", skeletal_mesh_path, skeleton_path]).lower()
        if "mannequin" in lowered:
            score += 20
            reasons.append("mannequin_keyword")
        if "ue5" in lowered:
            score += 5
            reasons.append("ue5_keyword")
        if skeletal_mesh_asset:
            score += 3
            reasons.append("has_skeletal_mesh")
        if score > best_score:
            best_score = score
            best_asset = asset
            best_metadata = {
                "selection_mode": "auto_search",
                "requested_asset_path": preferred_asset_path,
                "resolved_asset_path": canonical_asset_path(entry["object_path"]),
                "candidate_count": len(entries),
                "score": score,
                "reasons": reasons,
                "skeletal_mesh_asset_path": skeletal_mesh_path,
                "skeleton_asset_path": skeleton_path,
            }
    return best_asset, (best_metadata or {
        "selection_mode": "auto_search",
        "requested_asset_path": preferred_asset_path,
        "resolved_asset_path": "",
        "candidate_count": len(entries),
        "score": best_score,
        "reasons": [],
    })


def animation_compatibility_payload(component, animation_asset) -> dict:
    mesh_payload = mesh_skeleton_payload(component)
    animation_payload = animation_asset_payload(animation_asset)
    compatible_paths = []
    mesh_skeleton_asset = None
    if component:
        skeletal_mesh_asset = skeletal_mesh_asset_from_component(component)
        mesh_skeleton_asset = skeleton_asset_from_skeletal_mesh_asset(skeletal_mesh_asset)
    compatible_paths = compatible_skeleton_paths(mesh_skeleton_asset)
    mesh_skeleton_path = mesh_payload.get("skeleton_asset_path") or ""
    animation_skeleton_path = animation_payload.get("skeleton_asset_path") or ""
    exact_match = bool(mesh_skeleton_path and animation_skeleton_path and mesh_skeleton_path == animation_skeleton_path)
    listed_compatible = bool(animation_skeleton_path and animation_skeleton_path in compatible_paths)
    return {
        "mesh_asset_path": mesh_payload.get("mesh_asset_path") or "",
        "mesh_skeleton_asset_path": mesh_skeleton_path,
        "animation_asset_path": animation_payload.get("asset_path") or "",
        "animation_class_name": animation_payload.get("class_name") or "",
        "animation_skeleton_asset_path": animation_skeleton_path,
        "animation_play_length_seconds": float(animation_payload.get("play_length_seconds") or 0.0),
        "compatible_skeleton_paths": compatible_paths,
        "exact_skeleton_match": exact_match,
        "listed_compatible_skeleton": listed_compatible,
        "compatible": bool(exact_match or listed_compatible),
    }


def retarget_preflight(request: dict) -> dict:
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
    animation_asset = load_asset_from_any_path(animation_asset_path)
    if not animation_asset:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"animation_asset_load_failed:{animation_asset_path or 'missing'}"],
        }

    spawn_location = vector_from_request(request.get("location"), unreal.Vector(0.0, 0.0, 120.0))
    spawn_rotation = rotator_from_request(request.get("rotation"), make_rotator(0.0, 180.0, 0.0))
    actor_label = str(request.get("actor_label") or f"AIUE_RetargetPreflight_{sanitize_segment(host_record.get('character_package_id') if host_record else host_asset_path)}")
    spawned_host = actor_subsystem.spawn_actor_from_object(blueprint_asset, spawn_location, spawn_rotation, True)
    if not spawned_host:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"failed_to_spawn_host:{host_asset_path}"],
        }

    spawned_host.set_actor_label(actor_label)
    blocking_reasons = []
    try:
        try:
            spawned_host.apply_configured_loadout()
        except Exception as exc:
            warnings.append(f"apply_configured_loadout_failed:{exc}")

        time.sleep(max(float(request.get("settle_delay_seconds") or 0.2), 0.05))
        primary_mesh = actor_primary_mesh_component(spawned_host)
        compatibility = animation_compatibility_payload(primary_mesh, animation_asset)
        source_profile = skeleton_profile_payload_from_component(primary_mesh)
        target_profile = animation_skeleton_profile_payload(animation_asset)
        tooling = retarget_tooling_inventory(
            str(host_record.get("sample_id") if host_record else request.get("sample_id") or ""),
            str(host_record.get("character_package_id") if host_record else request.get("package_id") or ""),
            source_profile,
            target_profile,
        )

        if not compatibility.get("mesh_skeleton_asset_path"):
            blocking_reasons.append("source_skeleton_missing")
        if not compatibility.get("animation_skeleton_asset_path"):
            blocking_reasons.append("animation_skeleton_missing")

        requires_retarget = not compatibility.get("compatible")
        viable = bool(
            compatibility.get("compatible")
            or (
                tooling.get("can_author_new_retarget_assets")
                and source_profile.get("skeleton_asset_path")
                and target_profile.get("skeleton_asset_path")
            )
        )
        if requires_retarget and not tooling.get("can_author_new_retarget_assets"):
            blocking_reasons.append("ik_retarget_tooling_unavailable")
        if requires_retarget and (source_profile.get("humanoid_markers") or {}).get("manual_chain_mapping_likely"):
            warnings.append("source_skeleton_will_need_manual_chain_mapping")

        next_steps = retarget_recommendations(compatibility, source_profile, target_profile, tooling)
        return {
            "status": "pass" if viable and not blocking_reasons else "fail",
            "package_id": host_record.get("character_package_id") if host_record else request.get("package_id"),
            "sample_id": host_record.get("sample_id") if host_record else request.get("sample_id"),
            "host_id": spawned_host.get_path_name(),
            "host_blueprint_asset": host_asset_path,
            "level_path": level_path or get_current_level_path(),
            "animation_asset_path": animation_asset_path,
            "animation_compatibility": compatibility,
            "source_skeleton_profile": source_profile,
            "target_skeleton_profile": target_profile,
            "retarget_tooling": tooling,
            "retarget_readiness": {
                "direct_animation_compatible": bool(compatibility.get("compatible")),
                "requires_retarget": requires_retarget,
                "viable": viable and not blocking_reasons,
                "blocking_reasons": sorted(set(blocking_reasons)),
                "recommended_next_steps": next_steps,
            },
            "warnings": warnings,
            "errors": [] if viable and not blocking_reasons else sorted(set(blocking_reasons)),
        }
    finally:
        try:
            actor_subsystem.destroy_actor(spawned_host)
        except Exception:
            pass


def retarget_bootstrap(request: dict) -> dict:
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
    animation_asset = load_asset_from_any_path(animation_asset_path)
    if not animation_asset:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"animation_asset_load_failed:{animation_asset_path or 'missing'}"],
        }

    spawn_location = vector_from_request(request.get("location"), unreal.Vector(0.0, 0.0, 120.0))
    spawn_rotation = rotator_from_request(request.get("rotation"), make_rotator(0.0, 180.0, 0.0))
    actor_label = str(request.get("actor_label") or f"AIUE_RetargetBootstrap_{sanitize_segment(host_record.get('character_package_id') if host_record else host_asset_path)}")
    spawned_host = actor_subsystem.spawn_actor_from_object(blueprint_asset, spawn_location, spawn_rotation, True)
    if not spawned_host:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"failed_to_spawn_host:{host_asset_path}"],
        }

    spawned_host.set_actor_label(actor_label)
    errors = []
    try:
        try:
            spawned_host.apply_configured_loadout()
        except Exception as exc:
            warnings.append(f"apply_configured_loadout_failed:{exc}")

        time.sleep(max(float(request.get("settle_delay_seconds") or 0.2), 0.05))
        primary_mesh = actor_primary_mesh_component(spawned_host)
        source_mesh_asset = skeletal_mesh_asset_from_component(primary_mesh)
        source_mesh_path = ""
        source_skeleton_path = ""
        if source_mesh_asset:
            try:
                source_mesh_path = source_mesh_asset.get_path_name()
            except Exception:
                source_mesh_path = ""
            source_skeleton_asset = skeleton_asset_from_skeletal_mesh_asset(source_mesh_asset)
            if source_skeleton_asset:
                try:
                    source_skeleton_path = source_skeleton_asset.get_path_name()
                except Exception:
                    source_skeleton_path = ""
        if not source_mesh_asset:
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": ["source_skeletal_mesh_missing"],
            }

        target_ik_rig_asset, target_selection = choose_target_ik_rig_asset(animation_asset, str(request.get("target_ik_rig_asset_path") or ""))
        if not target_ik_rig_asset:
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": ["target_ik_rig_missing"],
            }

        source_ik_rig_request_path = str(request.get("source_ik_rig_asset_path") or "")
        if not source_ik_rig_request_path:
            asset_root = str(request.get("asset_root") or "/Game/PMXPipeline").rstrip("/")
            source_ik_rig_request_path = f"{asset_root}/Retarget/Source/IK_{sanitize_segment(host_record.get('character_package_id') if host_record else 'pmx_source')}"
        source_ik_rig_asset, source_ik_rig_created = create_or_load_ik_rig_asset(source_ik_rig_request_path)
        if not source_ik_rig_asset:
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": [f"source_ik_rig_create_failed:{source_ik_rig_request_path}"],
            }

        source_controller = unreal.IKRigController.get_controller(source_ik_rig_asset)
        source_mesh_applied = False
        auto_retarget_definition_applied = False
        if source_controller:
            try:
                source_mesh_applied = bool(source_controller.set_skeletal_mesh(source_mesh_asset))
            except Exception as exc:
                warnings.append(f"source_ik_rig_set_skeletal_mesh_failed:{exc}")
            try:
                auto_retarget_definition_applied = bool(source_controller.apply_auto_generated_retarget_definition())
            except Exception as exc:
                warnings.append(f"source_ik_rig_auto_retarget_definition_failed:{exc}")
        else:
            errors.append("source_ik_rig_controller_missing")

        target_controller = unreal.IKRigController.get_controller(target_ik_rig_asset)
        target_mesh_asset = target_controller.get_skeletal_mesh() if target_controller else None
        target_mesh_path = ""
        if target_mesh_asset:
            try:
                target_mesh_path = target_mesh_asset.get_path_name()
            except Exception:
                target_mesh_path = ""

        retargeter_request_path = str(request.get("retargeter_asset_path") or "")
        if not retargeter_request_path:
            asset_root = str(request.get("asset_root") or "/Game/PMXPipeline").rstrip("/")
            target_slug = sanitize_segment(base_name_from_asset_path(target_selection.get("resolved_asset_path") or target_mesh_path or "target"))
            retargeter_request_path = f"{asset_root}/Retarget/Demo/RTG_{sanitize_segment(host_record.get('character_package_id') if host_record else 'pmx_source')}_to_{target_slug}"
        retargeter_asset, retargeter_created = create_or_load_retargeter_asset(retargeter_request_path)
        if not retargeter_asset:
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": [f"retargeter_create_failed:{retargeter_request_path}"],
            }

        retargeter_controller = unreal.IKRetargeterController.get_controller(retargeter_asset)
        if not retargeter_controller:
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": ["retargeter_controller_missing"],
            }

        source_enum = retarget_source_enum_value()
        target_enum = retarget_target_enum_value()
        auto_map_enum = auto_map_chain_type_value()
        if source_enum is None or target_enum is None:
            errors.append("retarget_source_or_target_enum_missing")

        source_assignment_ok = False
        target_assignment_ok = False
        if source_enum is not None and target_enum is not None:
            try:
                retargeter_controller.set_ik_rig(source_enum, source_ik_rig_asset)
                source_assignment_ok = True
            except Exception as exc:
                warnings.append(f"retargeter_set_source_ik_rig_failed:{exc}")
            try:
                retargeter_controller.set_ik_rig(target_enum, target_ik_rig_asset)
                target_assignment_ok = True
            except Exception as exc:
                warnings.append(f"retargeter_set_target_ik_rig_failed:{exc}")
            if source_mesh_asset:
                try:
                    retargeter_controller.set_preview_mesh(source_enum, source_mesh_asset)
                except Exception as exc:
                    warnings.append(f"retargeter_set_source_preview_mesh_failed:{exc}")
            if target_mesh_asset:
                try:
                    retargeter_controller.set_preview_mesh(target_enum, target_mesh_asset)
                except Exception as exc:
                    warnings.append(f"retargeter_set_target_preview_mesh_failed:{exc}")

        try:
            retargeter_controller.add_default_ops()
        except Exception as exc:
            warnings.append(f"retargeter_add_default_ops_failed:{exc}")
        if source_enum is not None:
            try:
                retargeter_controller.assign_ik_rig_to_all_ops(source_enum, source_ik_rig_asset)
            except Exception as exc:
                warnings.append(f"retargeter_assign_source_ik_rig_failed:{exc}")
        if target_enum is not None:
            try:
                retargeter_controller.assign_ik_rig_to_all_ops(target_enum, target_ik_rig_asset)
            except Exception as exc:
                warnings.append(f"retargeter_assign_target_ik_rig_failed:{exc}")

        op_count = 0
        try:
            op_count = int(retargeter_controller.get_num_retarget_ops() or 0)
        except Exception:
            op_count = 0
        for index in range(op_count):
            try:
                retargeter_controller.run_op_initial_setup(index)
            except Exception as exc:
                warnings.append(f"retargeter_run_op_initial_setup_failed:{index}:{exc}")
        auto_map_invoked = False
        if auto_map_enum is not None:
            try:
                retargeter_controller.auto_map_chains(auto_map_enum, True)
                auto_map_invoked = True
            except Exception as exc:
                warnings.append(f"retargeter_auto_map_failed:{exc}")

        source_ik_rig_profile = ik_rig_profile_payload(source_ik_rig_asset)
        target_ik_rig_profile = ik_rig_profile_payload(target_ik_rig_asset)
        target_chain_names = [item.get("chain_name") or "" for item in target_ik_rig_profile.get("chains") or [] if item.get("chain_name")]
        mapped_chain_records = []
        mapped_chain_count = 0
        for target_chain_name in target_chain_names:
            source_chain_name = ""
            try:
                source_chain_name = str(retargeter_controller.get_source_chain(to_name(target_chain_name)) or "")
            except Exception:
                source_chain_name = ""
            if source_chain_name in {"None", "NAME_None"}:
                source_chain_name = ""
            if source_chain_name:
                mapped_chain_count += 1
            mapped_chain_records.append(
                {
                    "target_chain_name": target_chain_name,
                    "source_chain_name": source_chain_name,
                    "mapped": bool(source_chain_name),
                }
            )

        save_loaded_asset(source_ik_rig_asset)
        save_loaded_asset(retargeter_asset)
        status = "pass" if source_assignment_ok and target_assignment_ok and not errors else "fail"
        if source_ik_rig_profile.get("chain_count", 0) == 0:
            warnings.append("source_ik_rig_has_no_retarget_chains")
        if mapped_chain_count == 0:
            warnings.append("retargeter_has_no_mapped_target_chains")
        recommended_next_step_id = "retry_animation_preview_with_retargeter" if mapped_chain_count > 0 else "author_source_retarget_chains"
        recommended_next_step_reason = (
            "The retargeter has at least one mapped chain, so the next step is retrying a real animation preview through the new retarget assets."
            if mapped_chain_count > 0
            else "The bootstrap assets exist, but the imported PMX source rig still has no mapped retarget chains."
        )
        return {
            "status": status,
            "package_id": host_record.get("character_package_id") if host_record else request.get("package_id"),
            "sample_id": host_record.get("sample_id") if host_record else request.get("sample_id"),
            "host_id": spawned_host.get_path_name(),
            "host_blueprint_asset": host_asset_path,
            "level_path": level_path or get_current_level_path(),
            "animation_asset_path": animation_asset_path,
            "source_mesh_asset_path": source_mesh_path,
            "source_skeleton_asset_path": source_skeleton_path,
            "source_ik_rig_asset_path": canonical_asset_path(source_ik_rig_asset.get_path_name()),
            "source_ik_rig_created": source_ik_rig_created,
            "source_mesh_applied_to_ik_rig": source_mesh_applied,
            "source_auto_generated_retarget_definition_applied": auto_retarget_definition_applied,
            "target_ik_rig_asset_path": canonical_asset_path(target_ik_rig_asset.get_path_name()),
            "target_ik_rig_selection": target_selection,
            "retargeter_asset_path": canonical_asset_path(retargeter_asset.get_path_name()),
            "retargeter_created": retargeter_created,
            "source_ik_rig_assigned": source_assignment_ok,
            "target_ik_rig_assigned": target_assignment_ok,
            "auto_map_invoked": auto_map_invoked,
            "operation_count": op_count,
            "source_ik_rig_profile": source_ik_rig_profile,
            "target_ik_rig_profile": target_ik_rig_profile,
            "mapped_chain_count": mapped_chain_count,
            "mapped_chain_records": mapped_chain_records,
            "recommended_next_step_id": recommended_next_step_id,
            "recommended_next_step_reason": recommended_next_step_reason,
            "warnings": warnings,
            "errors": errors,
        }
    finally:
        try:
            actor_subsystem.destroy_actor(spawned_host)
        except Exception:
            pass


def retarget_author_chains(request: dict) -> dict:
    warnings = []
    source_ik_rig_asset_path = str(request.get("source_ik_rig_asset_path") or "")
    retargeter_asset_path = str(request.get("retargeter_asset_path") or "")
    target_ik_rig_asset_path = str(request.get("target_ik_rig_asset_path") or "")

    source_ik_rig_asset = load_asset_from_any_path(source_ik_rig_asset_path)
    if not source_ik_rig_asset:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"source_ik_rig_load_failed:{source_ik_rig_asset_path or 'missing'}"],
        }
    retargeter_asset = load_asset_from_any_path(retargeter_asset_path)
    if not retargeter_asset:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"retargeter_load_failed:{retargeter_asset_path or 'missing'}"],
        }
    target_ik_rig_asset = load_asset_from_any_path(target_ik_rig_asset_path) if target_ik_rig_asset_path else None

    source_controller = unreal.IKRigController.get_controller(source_ik_rig_asset)
    retargeter_controller = unreal.IKRetargeterController.get_controller(retargeter_asset)
    if not source_controller:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": ["source_ik_rig_controller_missing"],
        }
    if not retargeter_controller:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": ["retargeter_controller_missing"],
        }

    bone_names, bone_name_source = bone_names_from_ik_rig_controller(source_controller)
    if not bone_names:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": ["source_bone_names_unresolved"],
        }

    existing_chains = ik_rig_chain_records(source_controller)
    clear_existing = bool(request.get("clear_existing_chains", True))
    removed_chain_names = []
    if clear_existing:
        for chain_record in existing_chains:
            chain_name = str(chain_record.get("chain_name") or "")
            if not chain_name:
                continue
            try:
                if source_controller.remove_retarget_chain(to_name(chain_name)):
                    removed_chain_names.append(chain_name)
            except Exception as exc:
                warnings.append(f"remove_source_chain_failed:{chain_name}:{exc}")

    planned_chains, planning_warnings, planning_diagnostics = planned_source_chain_records(bone_names)
    warnings.extend(planning_warnings)

    authored_chain_records = []
    for chain in planned_chains:
        chain_name = chain["chain_name"]
        start_bone = chain["start_bone"]
        end_bone = chain["end_bone"]
        goal_name = chain.get("goal_name") or ""
        try:
            created_name = source_controller.add_retarget_chain(
                to_name(chain_name),
                to_name(start_bone),
                to_name(end_bone),
                to_name(goal_name) if goal_name else unreal.Name("None"),
            )
            authored_chain_records.append(
                {
                    "requested_chain_name": chain_name,
                    "created_chain_name": str(created_name or chain_name),
                    "start_bone": start_bone,
                    "end_bone": end_bone,
                    "goal_name": goal_name,
                    "planning_reason": chain.get("planning_reason") or "",
                }
            )
        except Exception as exc:
            warnings.append(f"add_source_chain_failed:{chain_name}:{exc}")

    pelvis_bone = pick_best_bone_name(bone_names, [["pelvis"], ["hips"], ["下半身"], ["腰"], ["center"]])
    if not pelvis_bone:
        spine_chain = next((item for item in planned_chains if str(item.get("chain_name") or "") == "Spine"), None)
        root_chain = next((item for item in planned_chains if str(item.get("chain_name") or "") == "root"), None)
        pelvis_bone = str((spine_chain or {}).get("start_bone") or (root_chain or {}).get("end_bone") or "")
    retarget_root_set = False
    if pelvis_bone:
        try:
            retarget_root_set = bool(source_controller.set_retarget_root(to_name(pelvis_bone)))
        except Exception as exc:
            warnings.append(f"set_source_retarget_root_failed:{pelvis_bone}:{exc}")
    else:
        warnings.append("source_retarget_root_unresolved")

    source_enum = retarget_source_enum_value()
    target_enum = retarget_target_enum_value()
    auto_map_enum = auto_map_chain_type_value()
    if source_enum is not None:
        try:
            retargeter_controller.assign_ik_rig_to_all_ops(source_enum, source_ik_rig_asset)
        except Exception as exc:
            warnings.append(f"retargeter_reassign_source_ik_rig_failed:{exc}")
    if target_enum is not None and target_ik_rig_asset:
        try:
            retargeter_controller.assign_ik_rig_to_all_ops(target_enum, target_ik_rig_asset)
        except Exception as exc:
            warnings.append(f"retargeter_reassign_target_ik_rig_failed:{exc}")
    auto_map_invoked = False
    if auto_map_enum is not None:
        try:
            retargeter_controller.auto_map_chains(auto_map_enum, True)
            auto_map_invoked = True
        except Exception as exc:
            warnings.append(f"retargeter_auto_map_failed:{exc}")

    source_profile = ik_rig_profile_payload(source_ik_rig_asset)
    target_profile = ik_rig_profile_payload(target_ik_rig_asset) if target_ik_rig_asset else {
        "asset_path": canonical_asset_path(target_ik_rig_asset_path),
        "skeletal_mesh_asset_path": "",
        "skeleton_asset_path": "",
        "retarget_root": "",
        "chain_count": 0,
        "chains": [],
    }
    target_chain_names = [item.get("chain_name") or "" for item in target_profile.get("chains") or [] if item.get("chain_name")]
    mapped_chain_records = []
    mapped_chain_count = 0
    exact_named_mapped_chain_count = 0
    exact_named_mapped_chain_names = []
    for target_chain_name in target_chain_names:
        source_chain_name = ""
        try:
            source_chain_name = str(retargeter_controller.get_source_chain(to_name(target_chain_name)) or "")
        except Exception:
            source_chain_name = ""
        if source_chain_name in {"None", "NAME_None"}:
            source_chain_name = ""
        if source_chain_name:
            mapped_chain_count += 1
        exact_named_match = bool(source_chain_name and source_chain_name == target_chain_name)
        if exact_named_match:
            exact_named_mapped_chain_count += 1
            exact_named_mapped_chain_names.append(target_chain_name)
        mapped_chain_records.append(
            {
                "target_chain_name": target_chain_name,
                "source_chain_name": source_chain_name,
                "mapped": bool(source_chain_name),
                "exact_named_match": exact_named_match,
            }
        )

    save_loaded_asset(source_ik_rig_asset)
    save_loaded_asset(retargeter_asset)
    errors = []
    if source_profile.get("chain_count", 0) == 0:
        errors.append("source_chain_authoring_failed")
    if mapped_chain_count == 0:
        warnings.append("retargeter_still_has_no_mapped_target_chains")
    meaningful_required_chain_names = ["root", "Spine", "LeftClavicle", "RightClavicle", "LeftArm", "RightArm"]
    authored_chain_name_set = {str(item.get("created_chain_name") or item.get("requested_chain_name") or "") for item in authored_chain_records}
    missing_meaningful_source_chain_names = [name for name in meaningful_required_chain_names if name not in authored_chain_name_set]
    missing_meaningful_mapped_chain_names = [name for name in meaningful_required_chain_names if name not in exact_named_mapped_chain_names]
    if missing_meaningful_source_chain_names:
        warnings.append(f"meaningful_source_chains_missing:{','.join(missing_meaningful_source_chain_names)}")
    if exact_named_mapped_chain_count == 0:
        warnings.append("retargeter_has_no_exact_named_chain_mappings")
    if exact_named_mapped_chain_count < 4:
        warnings.append("retargeter_exact_named_chain_mapping_insufficient_for_upper_body_preview")

    ready_for_animation_retry = bool(exact_named_mapped_chain_count >= 4 and not missing_meaningful_mapped_chain_names[:4])
    recommended_next_step_id = "retry_animation_preview_with_retargeter" if ready_for_animation_retry else "refine_source_chain_mapping"
    recommended_next_step_reason = (
        "The PMX source rig now has enough exact-named upper-body chain mappings to justify retrying animation preview through the retargeter."
        if ready_for_animation_retry
        else "The PMX source rig is no longer blank, but its exact-named upper-body chain mappings are still incomplete."
    )

    return {
        "status": "pass" if not errors else "fail",
        "source_ik_rig_asset_path": canonical_asset_path(source_ik_rig_asset.get_path_name()),
        "retargeter_asset_path": canonical_asset_path(retargeter_asset.get_path_name()),
        "target_ik_rig_asset_path": canonical_asset_path(target_ik_rig_asset.get_path_name()) if target_ik_rig_asset else canonical_asset_path(target_ik_rig_asset_path),
        "source_bone_name_source": bone_name_source,
        "source_bone_count": len(bone_names),
        "source_bone_name_sample": bone_names[:40],
        "removed_chain_names": removed_chain_names,
        "planned_chains": planned_chains,
        "planning_diagnostics": planning_diagnostics,
        "authored_chain_records": authored_chain_records,
        "retarget_root_bone": pelvis_bone,
        "retarget_root_set": retarget_root_set,
        "auto_map_invoked": auto_map_invoked,
        "source_ik_rig_profile": source_profile,
        "target_ik_rig_profile": target_profile,
        "mapped_chain_count": mapped_chain_count,
        "exact_named_mapped_chain_count": exact_named_mapped_chain_count,
        "exact_named_mapped_chain_names": exact_named_mapped_chain_names,
        "meaningful_required_chain_names": meaningful_required_chain_names,
        "missing_meaningful_source_chain_names": missing_meaningful_source_chain_names,
        "missing_meaningful_mapped_chain_names": missing_meaningful_mapped_chain_names,
        "mapped_chain_records": mapped_chain_records,
        "ready_for_animation_retry": ready_for_animation_retry,
        "recommended_next_step_id": recommended_next_step_id,
        "recommended_next_step_reason": recommended_next_step_reason,
        "warnings": warnings,
        "errors": errors,
    }


def asset_data_from_asset_path(asset_path: str):
    normalized = canonical_asset_path(asset_path)
    if not normalized:
        return None
    object_path = object_path_from_asset_path(normalized)
    if hasattr(unreal.EditorAssetLibrary, "find_asset_data"):
        try:
            asset_data = unreal.EditorAssetLibrary.find_asset_data(object_path)
        except Exception:
            asset_data = None
        if asset_data and asset_object_path(asset_data):
            return asset_data
    loaded_asset = load_asset_from_any_path(normalized)
    if loaded_asset and hasattr(unreal.AssetRegistryHelpers, "create_asset_data"):
        try:
            asset_data = unreal.AssetRegistryHelpers.create_asset_data(loaded_asset)
        except Exception:
            asset_data = None
        if asset_data and asset_object_path(asset_data):
            return asset_data
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    try:
        asset_data = registry.get_asset_by_object_path(object_path)
    except Exception:
        asset_data = None
    if asset_data and asset_object_path(asset_data):
        return asset_data
    package_path, asset_name = package_path_and_asset_name(normalized)
    if package_path:
        try:
            candidates = list(registry.get_assets_by_path(to_name(package_path), recursive=False) or [])
        except Exception:
            candidates = []
        for candidate in candidates:
            if str(candidate.asset_name) == asset_name or asset_object_path(candidate) == object_path:
                return candidate
    return None


def skeletal_mesh_from_ik_rig_asset(ik_rig_asset):
    if not ik_rig_asset:
        return None
    controller = unreal.IKRigController.get_controller(ik_rig_asset)
    if not controller:
        return None
    try:
        mesh = controller.get_skeletal_mesh()
    except Exception:
        mesh = None
    return mesh


def reverse_preview_retargeter_asset_path(source_ik_rig_asset_path: str, target_ik_rig_asset_path: str, package_id: str | None = None) -> str:
    source_slug = sanitize_segment(base_name_from_asset_path(source_ik_rig_asset_path) or "source")
    target_slug = sanitize_segment(package_id or base_name_from_asset_path(target_ik_rig_asset_path) or "target")
    return f"/Game/PMXPipeline/Retarget/Demo/RTG_{source_slug}_to_{target_slug}_Preview"


def exact_chain_names_for_ik_rig(ik_rig_asset) -> list[str]:
    profile = ik_rig_profile_payload(ik_rig_asset)
    return sorted({str(item.get("chain_name") or "") for item in (profile.get("chains") or []) if str(item.get("chain_name") or "")})


def configure_retargeter_for_preview_export(retargeter_asset, source_ik_rig_asset, target_ik_rig_asset, source_mesh_asset, target_mesh_asset) -> dict:
    warnings = []
    controller = unreal.IKRetargeterController.get_controller(retargeter_asset) if retargeter_asset else None
    if not controller:
        return {
            "success": False,
            "warnings": ["preview_retargeter_controller_missing"],
            "errors": ["preview_retargeter_controller_missing"],
            "exact_chain_names": [],
            "mapped_chain_records": [],
        }

    source_enum = retarget_source_enum_value()
    target_enum = retarget_target_enum_value()
    auto_map_enum = auto_map_chain_type_value()
    if source_enum is not None and source_ik_rig_asset:
        try:
            controller.set_ik_rig(source_enum, source_ik_rig_asset)
        except Exception as exc:
            warnings.append(f"preview_retargeter_set_source_ik_rig_failed:{exc}")
    if target_enum is not None and target_ik_rig_asset:
        try:
            controller.set_ik_rig(target_enum, target_ik_rig_asset)
        except Exception as exc:
            warnings.append(f"preview_retargeter_set_target_ik_rig_failed:{exc}")
    if source_enum is not None and source_mesh_asset:
        try:
            controller.set_preview_mesh(source_enum, source_mesh_asset)
        except Exception as exc:
            warnings.append(f"preview_retargeter_set_source_preview_mesh_failed:{exc}")
    if target_enum is not None and target_mesh_asset:
        try:
            controller.set_preview_mesh(target_enum, target_mesh_asset)
        except Exception as exc:
            warnings.append(f"preview_retargeter_set_target_preview_mesh_failed:{exc}")

    try:
        controller.remove_all_ops()
    except Exception as exc:
        warnings.append(f"preview_retargeter_remove_all_ops_failed:{exc}")
    try:
        controller.add_default_ops()
    except Exception as exc:
        warnings.append(f"preview_retargeter_add_default_ops_failed:{exc}")

    op_count = 0
    try:
        op_count = int(controller.get_num_retarget_ops() or 0)
    except Exception:
        op_count = 0
    for index in range(op_count):
        try:
            controller.run_op_initial_setup(index)
        except Exception as exc:
            warnings.append(f"preview_retargeter_run_op_initial_setup_failed:{index}:{exc}")
    if source_enum is not None and source_ik_rig_asset:
        try:
            controller.assign_ik_rig_to_all_ops(source_enum, source_ik_rig_asset)
        except Exception as exc:
            warnings.append(f"preview_retargeter_assign_source_ik_rig_failed:{exc}")
    if target_enum is not None and target_ik_rig_asset:
        try:
            controller.assign_ik_rig_to_all_ops(target_enum, target_ik_rig_asset)
        except Exception as exc:
            warnings.append(f"preview_retargeter_assign_target_ik_rig_failed:{exc}")
    if auto_map_enum is not None:
        try:
            controller.auto_map_chains(auto_map_enum, True)
        except Exception as exc:
            warnings.append(f"preview_retargeter_auto_map_failed:{exc}")

    source_chain_names = set(exact_chain_names_for_ik_rig(source_ik_rig_asset))
    target_chain_names = set(exact_chain_names_for_ik_rig(target_ik_rig_asset))
    exact_chain_names = sorted(source_chain_names.intersection(target_chain_names))
    exact_mapping_errors = []
    for chain_name in exact_chain_names:
        try:
            if not controller.set_source_chain(to_name(chain_name), to_name(chain_name)):
                exact_mapping_errors.append(chain_name)
        except Exception:
            exact_mapping_errors.append(chain_name)
    if exact_mapping_errors:
        warnings.append(f"preview_retargeter_set_exact_source_chain_failed:{','.join(sorted(exact_mapping_errors))}")

    mapped_chain_records = []
    for chain_name in sorted(target_chain_names):
        source_chain_name = ""
        try:
            source_chain_name = str(controller.get_source_chain(to_name(chain_name)) or "")
        except Exception:
            source_chain_name = ""
        if source_chain_name in {"None", "NAME_None"}:
            source_chain_name = ""
        mapped_chain_records.append(
            {
                "target_chain_name": chain_name,
                "source_chain_name": source_chain_name,
                "exact_named_match": bool(source_chain_name and source_chain_name == chain_name),
            }
        )

    save_loaded_asset(retargeter_asset)
    exact_named_mapped_chain_names = sorted(
        [item["target_chain_name"] for item in mapped_chain_records if item.get("exact_named_match")]
    )
    return {
        "success": True,
        "warnings": warnings,
        "errors": [],
        "op_count": op_count,
        "exact_chain_names": exact_chain_names,
        "mapped_chain_records": mapped_chain_records,
        "exact_named_mapped_chain_names": exact_named_mapped_chain_names,
    }


def resolve_retargeted_animation_asset(results) -> tuple[object | None, str]:
    asset_data_list = list(results or [])
    if not asset_data_list:
        return None, ""
    chosen_asset_path = ""
    chosen_asset = None
    for asset_data in asset_data_list:
        class_name = asset_class_name(asset_data)
        object_path = asset_object_path(asset_data)
        canonical_path = canonical_asset_path(object_path)
        if class_name == "AnimSequence":
            chosen_asset_path = canonical_path
            chosen_asset = load_asset_from_any_path(canonical_path)
            if chosen_asset:
                return chosen_asset, chosen_asset_path
    first_object_path = asset_object_path(asset_data_list[0])
    chosen_asset_path = canonical_asset_path(first_object_path)
    return load_asset_from_any_path(chosen_asset_path), chosen_asset_path


def generate_retargeted_animation_for_preview(primary_mesh, animation_asset, request: dict) -> dict:
    warnings = []
    errors = []
    if not primary_mesh or not animation_asset:
        return {
            "success": False,
            "warnings": warnings,
            "errors": ["preview_mesh_or_animation_missing"],
        }

    source_ik_rig_asset_path = str(request.get("retarget_source_ik_rig_asset_path") or "")
    target_ik_rig_asset_path = str(request.get("retarget_target_ik_rig_asset_path") or "")
    source_ik_rig_asset = load_asset_from_any_path(source_ik_rig_asset_path)
    target_ik_rig_asset = load_asset_from_any_path(target_ik_rig_asset_path)
    if not source_ik_rig_asset or not target_ik_rig_asset:
        return {
            "success": False,
            "warnings": warnings,
            "errors": [
                f"retarget_preview_ik_rig_missing:source={bool(source_ik_rig_asset)}:target={bool(target_ik_rig_asset)}"
            ],
        }

    source_mesh_asset = load_asset_from_any_path(str(request.get("retarget_source_mesh_asset_path") or "")) or skeletal_mesh_from_ik_rig_asset(source_ik_rig_asset)
    target_mesh_asset = load_asset_from_any_path(str(request.get("retarget_target_mesh_asset_path") or "")) or skeletal_mesh_asset_from_component(primary_mesh)
    if not source_mesh_asset or not target_mesh_asset:
        return {
            "success": False,
            "warnings": warnings,
            "errors": [
                f"retarget_preview_mesh_missing:source={bool(source_mesh_asset)}:target={bool(target_mesh_asset)}"
            ],
        }

    preview_retargeter_asset_path = str(
        request.get("retargeter_asset_path")
        or reverse_preview_retargeter_asset_path(source_ik_rig_asset_path, target_ik_rig_asset_path, request.get("package_id"))
    )
    preview_retargeter_asset, preview_retargeter_created = create_or_load_retargeter_asset(preview_retargeter_asset_path)
    if not preview_retargeter_asset:
        return {
            "success": False,
            "warnings": warnings,
            "errors": [f"preview_retargeter_create_failed:{preview_retargeter_asset_path}"],
        }

    configuration = configure_retargeter_for_preview_export(
        preview_retargeter_asset,
        source_ik_rig_asset,
        target_ik_rig_asset,
        source_mesh_asset,
        target_mesh_asset,
    )
    warnings.extend(configuration.get("warnings") or [])
    errors.extend(configuration.get("errors") or [])

    asset_data = asset_data_from_asset_path(animation_asset.get_path_name())
    if not asset_data:
        return {
            "success": False,
            "warnings": warnings,
            "errors": errors + [f"animation_asset_data_unresolved:{animation_asset.get_path_name()}"],
        }

    batch_class = getattr(unreal, "IKRetargetBatchOperation", None)
    batch_function = None
    for attribute_name in ("duplicate_and_retarget", "DuplicateAndRetarget"):
        if batch_class and hasattr(batch_class, attribute_name):
            batch_function = getattr(batch_class, attribute_name)
            break
    if not batch_function:
        return {
            "success": False,
            "warnings": warnings,
            "errors": errors + ["ik_retarget_batch_operation_unavailable"],
        }

    suffix = str(request.get("retarget_output_suffix") or "_PMXPreview")
    prefix = str(request.get("retarget_output_prefix") or "RTG_")
    try:
        retargeted_assets = batch_function(
            [asset_data],
            source_mesh_asset,
            target_mesh_asset,
            preview_retargeter_asset,
            "",
            "",
            prefix,
            suffix,
            False,
            True,
        )
    except Exception as exc:
        return {
            "success": False,
            "warnings": warnings,
            "errors": errors + [f"duplicate_and_retarget_failed:{exc}"],
        }

    retargeted_animation_asset, retargeted_animation_asset_path = resolve_retargeted_animation_asset(retargeted_assets)
    if not retargeted_animation_asset:
        return {
            "success": False,
            "warnings": warnings,
            "errors": errors + ["retargeted_animation_asset_unresolved"],
            "retargeter_asset_path": canonical_asset_path(preview_retargeter_asset.get_path_name()),
        }
    retargeted_compatibility = animation_compatibility_payload(primary_mesh, retargeted_animation_asset)
    save_loaded_asset(retargeted_animation_asset)
    return {
        "success": bool(retargeted_compatibility.get("compatible")),
        "warnings": warnings,
        "errors": errors if retargeted_compatibility.get("compatible") else errors + ["retargeted_animation_still_incompatible"],
        "retargeter_asset_path": canonical_asset_path(preview_retargeter_asset.get_path_name()),
        "retargeter_created": preview_retargeter_created,
        "source_ik_rig_asset_path": canonical_asset_path(source_ik_rig_asset.get_path_name()),
        "target_ik_rig_asset_path": canonical_asset_path(target_ik_rig_asset.get_path_name()),
        "source_mesh_asset_path": canonical_asset_path(source_mesh_asset.get_path_name()),
        "target_mesh_asset_path": canonical_asset_path(target_mesh_asset.get_path_name()),
        "source_animation_asset_path": canonical_asset_path(animation_asset.get_path_name()),
        "retargeted_animation_asset_path": canonical_asset_path(retargeted_animation_asset_path or retargeted_animation_asset.get_path_name()),
        "retargeted_animation_class_name": retargeted_animation_asset.get_class().get_name() if retargeted_animation_asset else "",
        "retargeted_compatibility": retargeted_compatibility,
        "exact_named_mapped_chain_names": list(configuration.get("exact_named_mapped_chain_names") or []),
        "mapped_chain_records": list(configuration.get("mapped_chain_records") or []),
    }


def interesting_member_names(obj, interesting_names: list[str]) -> list[str]:
    if not obj:
        return []
    try:
        available = set(dir(obj))
    except Exception:
        return []
    return sorted([name for name in interesting_names if name in available])


def call_method_variants(target, label: str, candidate_names: list[str], arg_variants: list[tuple], call_trace: list[dict], warnings: list[str], applied_methods: list[str]):
    for method_name in candidate_names:
        if not hasattr(target, method_name):
            continue
        method = getattr(target, method_name)
        for args in arg_variants:
            trace_record = {
                "label": label,
                "method_name": method_name,
                "args": [repr(arg) for arg in args],
                "success": False,
            }
            try:
                result = method(*args)
                trace_record["success"] = True
                if result is not None:
                    trace_record["result_repr"] = repr(result)
                call_trace.append(trace_record)
                applied_methods.append(f"{label}:{method_name}")
                return True, result
            except Exception as exc:
                trace_record["error"] = str(exc)
                call_trace.append(trace_record)
        warnings.append(f"{label}_failed:{method_name}")
    return False, None


def set_editor_property_variants(target, label: str, property_updates: list[tuple[str, object]], call_trace: list[dict], warnings: list[str], applied_methods: list[str]) -> bool:
    if not target or not hasattr(target, "set_editor_property"):
        return False
    any_success = False
    for property_name, property_value in property_updates:
        trace_record = {
            "label": label,
            "property_name": property_name,
            "value_repr": repr(property_value),
            "success": False,
        }
        try:
            target.set_editor_property(property_name, property_value)
            trace_record["success"] = True
            call_trace.append(trace_record)
            applied_methods.append(f"{label}:{property_name}")
            any_success = True
        except Exception as exc:
            trace_record["error"] = str(exc)
            call_trace.append(trace_record)
    if not any_success:
        warnings.append(f"{label}_property_update_failed")
    return any_success


def bone_space_world_value():
    bone_spaces = getattr(unreal, "BoneSpaces", None)
    if bone_spaces:
        for candidate in ("WORLD_SPACE", "WorldSpace"):
            if hasattr(bone_spaces, candidate):
                return getattr(bone_spaces, candidate)
    return None


def probe_component_pose(component, probe_bone_names: list[str] | None = None) -> dict:
    requested_bone_names = [str(name) for name in list(probe_bone_names or []) if str(name)]
    pose = {
        "component_world_location": {},
        "component_world_rotation": {},
        "component_asset_path": component_asset_path(component),
        "sampled_bones": {},
        "requested_bone_names": requested_bone_names,
        "available_probe_methods": [],
    }
    if not component:
        pose["warnings"] = ["component_missing"]
        return pose

    try:
        pose["component_world_location"] = serialize_vector(component.get_component_location())
    except Exception:
        pose["component_world_location"] = {}
    try:
        pose["component_world_rotation"] = serialize_rotator(component.get_component_rotation())
    except Exception:
        pose["component_world_rotation"] = {}

    available_methods = interesting_member_names(
        component,
        [
            "get_bone_location",
            "GetBoneLocation",
            "get_socket_location",
            "GetSocketLocation",
            "get_socket_transform",
            "GetSocketTransform",
            "does_socket_exist",
            "DoesSocketExist",
        ],
    )
    pose["available_probe_methods"] = available_methods
    if not requested_bone_names:
        return pose

    world_space = bone_space_world_value()
    sampled = {}
    for bone_name in requested_bone_names:
        location = None
        source = ""
        if hasattr(component, "get_socket_location"):
            try:
                location = component.get_socket_location(to_name(bone_name))
                source = "get_socket_location"
            except Exception:
                location = None
        if location is None and hasattr(component, "GetSocketLocation"):
            try:
                location = component.GetSocketLocation(to_name(bone_name))
                source = "GetSocketLocation"
            except Exception:
                location = None
        if location is None and hasattr(component, "get_bone_location") and world_space is not None:
            try:
                location = component.get_bone_location(to_name(bone_name), world_space)
                source = "get_bone_location"
            except Exception:
                location = None
        if location is None and hasattr(component, "GetBoneLocation") and world_space is not None:
            try:
                location = component.GetBoneLocation(to_name(bone_name), world_space)
                source = "GetBoneLocation"
            except Exception:
                location = None
        if location is not None:
            sampled[bone_name] = {
                "location": serialize_vector(location),
                "source": source,
            }
    pose["sampled_bones"] = sampled
    return pose


def pose_delta_payload(before_pose: dict, after_pose: dict) -> dict:
    before_bones = dict((before_pose or {}).get("sampled_bones") or {})
    after_bones = dict((after_pose or {}).get("sampled_bones") or {})
    delta_by_bone = {}
    moving_bone_count = 0
    max_location_delta = 0.0
    for bone_name in sorted(set(before_bones.keys()).intersection(after_bones.keys())):
        before_location = vector_from_request(before_bones[bone_name].get("location"))
        after_location = vector_from_request(after_bones[bone_name].get("location"))
        delta_vector = after_location - before_location
        location_delta = math.sqrt((delta_vector.x * delta_vector.x) + (delta_vector.y * delta_vector.y) + (delta_vector.z * delta_vector.z))
        moving = location_delta >= 0.5
        moving_bone_count += int(moving)
        max_location_delta = max(max_location_delta, float(location_delta))
        delta_by_bone[bone_name] = {
            "location_delta": float(location_delta),
            "moving": moving,
            "before_location": serialize_vector(before_location),
            "after_location": serialize_vector(after_location),
        }
    return {
        "moving_bone_count": moving_bone_count,
        "max_location_delta": float(max_location_delta),
        "delta_by_bone": delta_by_bone,
    }


def serialize_quat(quat) -> dict:
    if quat is None:
        return {}
    payload = {}
    for attribute_name in ("x", "y", "z", "w"):
        try:
            payload[attribute_name] = float(getattr(quat, attribute_name))
        except Exception:
            continue
    return payload


def transform_translation_value(transform):
    if transform is None:
        return None
    for method_name in ("get_translation",):
        if hasattr(transform, method_name):
            try:
                return getattr(transform, method_name)()
            except Exception:
                continue
    for attribute_name in ("translation", "location"):
        try:
            value = getattr(transform, attribute_name)
            if value is not None:
                return value
        except Exception:
            continue
    return None


def transform_rotation_value(transform):
    if transform is None:
        return None
    for method_name in ("get_rotation",):
        if hasattr(transform, method_name):
            try:
                return getattr(transform, method_name)()
            except Exception:
                continue
    for attribute_name in ("rotation",):
        try:
            value = getattr(transform, attribute_name)
            if value is not None:
                return value
        except Exception:
            continue
    return None


def transform_scale_value(transform):
    if transform is None:
        return None
    for method_name in ("get_scale3d",):
        if hasattr(transform, method_name):
            try:
                return getattr(transform, method_name)()
            except Exception:
                continue
    for attribute_name in ("scale3d", "scale"):
        try:
            value = getattr(transform, attribute_name)
            if value is not None:
                return value
        except Exception:
            continue
    return None


def serialize_transform_payload(transform) -> dict:
    translation = transform_translation_value(transform)
    rotation = transform_rotation_value(transform)
    scale = transform_scale_value(transform)
    rotator = None
    if rotation is not None and hasattr(rotation, "rotator"):
        try:
            rotator = rotation.rotator()
        except Exception:
            rotator = None
    return {
        "translation": serialize_vector(translation) if translation is not None else {},
        "rotation_quat": serialize_quat(rotation) if rotation is not None else {},
        "rotation_rotator": serialize_rotator(rotator) if rotator is not None else {},
        "scale": serialize_vector(scale) if scale is not None else {},
        "repr": repr(transform),
    }


def reference_skeleton_pose_records(reference_skeleton) -> dict[str, dict]:
    names, _ = reference_skeleton_bone_names(reference_skeleton)
    if not names:
        return {}
    pose_values = None
    for method_name in ("get_raw_ref_bone_pose", "get_ref_bone_pose"):
        if hasattr(reference_skeleton, method_name):
            try:
                pose_values = list(getattr(reference_skeleton, method_name)() or [])
            except Exception:
                pose_values = None
            if pose_values:
                break
    records = {}
    for index, bone_name in enumerate(names):
        local_transform = pose_values[index] if pose_values and index < len(pose_values) else None
        parent_index = -1
        for method_name in ("get_parent_index",):
            if hasattr(reference_skeleton, method_name):
                try:
                    parent_index = int(getattr(reference_skeleton, method_name)(index))
                    break
                except Exception:
                    parent_index = -1
        records[bone_name] = {
            "index": index,
            "parent_index": parent_index,
            "local_transform": local_transform,
            "local_transform_payload": serialize_transform_payload(local_transform) if local_transform is not None else {},
        }
    return records


def sample_animation_local_pose(animation_asset, bone_names: list[str], sample_time_seconds: float, preview_mesh_asset=None) -> dict:
    payload = {
        "success": False,
        "warnings": [],
        "errors": [],
        "sample_time_seconds": float(sample_time_seconds),
        "bone_count": len(bone_names),
        "bone_poses": {},
        "api_trace": [],
    }
    animation_library = getattr(unreal, "AnimationBlueprintLibrary", None)
    if not animation_library:
        for loader_name in ("load_module", "load_editor_module"):
            if hasattr(unreal, loader_name):
                try:
                    getattr(unreal, loader_name)("AnimationBlueprintLibrary")
                    payload["api_trace"].append(f"{loader_name}:AnimationBlueprintLibrary")
                except Exception as exc:
                    payload["api_trace"].append(f"{loader_name}:AnimationBlueprintLibrary_failed:{exc}")
        modules_class = getattr(unreal, "Modules", None)
        if modules_class and hasattr(modules_class, "load_module"):
            try:
                modules_class.load_module("AnimationBlueprintLibrary")
                payload["api_trace"].append("Modules.load_module:AnimationBlueprintLibrary")
            except Exception as exc:
                payload["api_trace"].append(f"Modules.load_module:AnimationBlueprintLibrary_failed:{exc}")
        animation_library = getattr(unreal, "AnimationBlueprintLibrary", None)
    if not animation_library:
        payload["errors"].append("animation_blueprint_library_unavailable")
        return payload
    if not animation_asset:
        payload["errors"].append("animation_asset_missing")
        return payload
    if not bone_names:
        payload["errors"].append("animation_pose_bone_list_empty")
        return payload

    result = None
    bone_name_values = [to_name(name) for name in bone_names]
    try:
        result = animation_library.get_bone_poses_for_time(animation_asset, bone_name_values, float(sample_time_seconds), False, preview_mesh_asset)
        payload["api_trace"].append("get_bone_poses_for_time:with_preview_mesh")
    except Exception as exc:
        payload["api_trace"].append(f"get_bone_poses_for_time:with_preview_mesh_failed:{exc}")
    if result is None:
        try:
            result = animation_library.get_bone_poses_for_time(animation_asset, bone_name_values, float(sample_time_seconds), False)
            payload["api_trace"].append("get_bone_poses_for_time:no_preview_mesh")
        except Exception as exc:
            payload["api_trace"].append(f"get_bone_poses_for_time:no_preview_mesh_failed:{exc}")

    transforms = []
    if isinstance(result, (list, tuple)):
        transforms = list(result)
    elif result is not None:
        transforms = [result]

    if not transforms or len(transforms) != len(bone_names):
        transforms = []
        for bone_name in bone_names:
            transform = None
            try:
                transform = animation_library.get_bone_pose_for_time(animation_asset, to_name(bone_name), float(sample_time_seconds), False)
                payload["api_trace"].append(f"get_bone_pose_for_time:{bone_name}")
            except Exception as exc:
                payload["api_trace"].append(f"get_bone_pose_for_time_failed:{bone_name}:{exc}")
            transforms.append(transform)

    if not transforms:
        payload["errors"].append("animation_pose_sampling_failed")
        return payload

    for bone_name, transform in zip(bone_names, transforms):
        if transform is None:
            continue
        payload["bone_poses"][bone_name] = {
            "transform": serialize_transform_payload(transform),
        }
    payload["success"] = bool(payload["bone_poses"])
    if not payload["success"]:
        payload["errors"].append("animation_pose_sampling_empty")
    return payload


def animation_pose_delta_against_reference(sampled_pose: dict, reference_pose_records: dict[str, dict]) -> dict:
    delta_by_bone = {}
    changed_bone_count = 0
    rotation_changed_bone_count = 0
    translation_changed_bone_count = 0
    for bone_name, sampled_record in dict(sampled_pose.get("bone_poses") or {}).items():
        sampled_transform = dict(sampled_record.get("transform") or {})
        reference_transform = dict((reference_pose_records.get(bone_name) or {}).get("local_transform_payload") or {})
        sampled_translation = vector_from_request(sampled_transform.get("translation"))
        reference_translation = vector_from_request(reference_transform.get("translation"))
        delta_vector = sampled_translation - reference_translation
        translation_delta = math.sqrt((delta_vector.x * delta_vector.x) + (delta_vector.y * delta_vector.y) + (delta_vector.z * delta_vector.z))
        sampled_rotator = dict(sampled_transform.get("rotation_rotator") or {})
        reference_rotator = dict(reference_transform.get("rotation_rotator") or {})
        rotation_delta = max(
            abs(float(sampled_rotator.get("pitch", 0.0)) - float(reference_rotator.get("pitch", 0.0))),
            abs(float(sampled_rotator.get("yaw", 0.0)) - float(reference_rotator.get("yaw", 0.0))),
            abs(float(sampled_rotator.get("roll", 0.0)) - float(reference_rotator.get("roll", 0.0))),
        )
        repr_changed = str(sampled_transform.get("repr") or "") != str(reference_transform.get("repr") or "")
        translation_changed = translation_delta >= 0.25
        rotation_changed = rotation_delta >= 1.0
        changed = bool(translation_changed or rotation_changed or repr_changed)
        changed_bone_count += int(changed)
        translation_changed_bone_count += int(translation_changed)
        rotation_changed_bone_count += int(rotation_changed)
        delta_by_bone[bone_name] = {
            "translation_delta": float(translation_delta),
            "rotation_delta_max_degrees": float(rotation_delta),
            "translation_changed": translation_changed,
            "rotation_changed": rotation_changed,
            "repr_changed": repr_changed,
            "changed": changed,
            "sampled_transform": sampled_transform,
            "reference_transform": reference_transform,
        }
    return {
        "changed_bone_count": changed_bone_count,
        "translation_changed_bone_count": translation_changed_bone_count,
        "rotation_changed_bone_count": rotation_changed_bone_count,
        "delta_by_bone": delta_by_bone,
    }


def struct_property_value(struct_value, property_name: str, default=None):
    if struct_value is None:
        return default
    try:
        return struct_value.get_editor_property(property_name)
    except Exception:
        pass
    try:
        value = getattr(struct_value, property_name)
        if callable(value):
            return value()
        return value
    except Exception:
        return default


def serialize_native_animation_pose_probe_result(probe_result) -> dict:
    return {
        "bone_name": str(struct_property_value(probe_result, "bone_name", "") or ""),
        "found": bool(struct_property_value(probe_result, "found", False)),
        "changed": bool(struct_property_value(probe_result, "changed", False)),
        "location_delta": float(struct_property_value(probe_result, "location_delta", 0.0) or 0.0),
        "rotation_angle_delta_degrees": float(struct_property_value(probe_result, "rotation_angle_delta_degrees", 0.0) or 0.0),
        "scale_delta": float(struct_property_value(probe_result, "scale_delta", 0.0) or 0.0),
    }


def serialize_native_animation_pose_evaluation(result) -> dict:
    probe_results = [serialize_native_animation_pose_probe_result(item) for item in list(struct_property_value(result, "probe_results", []) or [])]
    return {
        "available": True,
        "success": bool(struct_property_value(result, "success", False)),
        "pose_changed": bool(struct_property_value(result, "pose_changed", False)),
        "sample_time_seconds": float(struct_property_value(result, "sample_time_seconds", 0.0) or 0.0),
        "bone_count": int(struct_property_value(result, "bone_count", 0) or 0),
        "changed_bone_count": int(struct_property_value(result, "changed_bone_count", 0) or 0),
        "max_location_delta": float(struct_property_value(result, "max_location_delta", 0.0) or 0.0),
        "max_rotation_angle_delta_degrees": float(struct_property_value(result, "max_rotation_angle_delta_degrees", 0.0) or 0.0),
        "max_scale_delta": float(struct_property_value(result, "max_scale_delta", 0.0) or 0.0),
        "applied_methods": [str(item) for item in list(struct_property_value(result, "applied_methods", []) or [])],
        "warnings": [str(item) for item in list(struct_property_value(result, "warnings", []) or [])],
        "errors": [str(item) for item in list(struct_property_value(result, "errors", []) or [])],
        "probe_results": probe_results,
    }


def evaluate_animation_pose_on_component_native(component, animation_asset, sample_time_seconds: float, probe_bone_names: list[str]) -> dict:
    if not hasattr(unreal, "PMXEquipmentBlueprintLibrary"):
        return {
            "available": False,
            "success": False,
            "pose_changed": False,
            "errors": ["pmx_runtime_blueprint_library_unavailable"],
            "warnings": [],
            "applied_methods": [],
            "probe_results": [],
            "sample_time_seconds": float(sample_time_seconds),
            "bone_count": 0,
            "changed_bone_count": 0,
            "max_location_delta": 0.0,
            "max_rotation_angle_delta_degrees": 0.0,
            "max_scale_delta": 0.0,
        }
    try:
        result = unreal.PMXEquipmentBlueprintLibrary.evaluate_animation_pose_on_component(
            component,
            animation_asset,
            float(sample_time_seconds),
            [to_name(name) for name in probe_bone_names if str(name)],
        )
        return serialize_native_animation_pose_evaluation(result)
    except Exception as exc:
        return {
            "available": True,
            "success": False,
            "pose_changed": False,
            "errors": [f"native_animation_pose_evaluation_failed:{exc}"],
            "warnings": [],
            "applied_methods": [],
            "probe_results": [],
            "sample_time_seconds": float(sample_time_seconds),
            "bone_count": 0,
            "changed_bone_count": 0,
            "max_location_delta": 0.0,
            "max_rotation_angle_delta_degrees": 0.0,
            "max_scale_delta": 0.0,
        }


def apply_animation_pose_to_component(component, animation_asset, sample_time_seconds: float) -> dict:
    warnings = []
    applied_methods = []
    success = False
    call_trace = []
    if not component or not animation_asset:
        return {
            "success": False,
            "warnings": ["component_or_animation_missing"],
            "applied_methods": [],
            "call_trace": [],
            "available_component_methods": [],
            "available_single_node_methods": [],
        }

    set_editor_property_variants(
        component,
        "pre_animation_flags",
        [
            ("pause_anims", False),
            ("no_skeleton_update", False),
            ("force_ref_pose", False),
            ("force_refpose", False),
            ("use_ref_pose_on_init_anim", False),
            ("enable_animation", True),
            ("update_animation_in_editor", True),
            ("global_anim_rate_scale", 1.0),
        ],
        call_trace,
        warnings,
        applied_methods,
    )

    visibility_enum = getattr(unreal, "VisibilityBasedAnimTickOption", None) or getattr(unreal, "EVisibilityBasedAnimTickOption", None)
    visibility_value = None
    if visibility_enum:
        for enum_name in ("ALWAYS_TICK_POSE_AND_REFRESH_BONES", "AlwaysTickPoseAndRefreshBones"):
            if hasattr(visibility_enum, enum_name):
                visibility_value = getattr(visibility_enum, enum_name)
                break
    if visibility_value is not None:
        set_editor_property_variants(
            component,
            "visibility_based_anim_tick_option",
            [("visibility_based_anim_tick_option", visibility_value)],
            call_trace,
            warnings,
            applied_methods,
        )

    call_method_variants(
        component,
        "set_update_animation_in_editor",
        ["set_update_animation_in_editor", "SetUpdateAnimationInEditor"],
        [(True,)],
        call_trace,
        warnings,
        applied_methods,
    )
    call_method_variants(
        component,
        "set_enable_animation",
        ["set_enable_animation", "SetEnableAnimation"],
        [(True,)],
        call_trace,
        warnings,
        applied_methods,
    )
    call_method_variants(
        component,
        "set_component_tick_enabled",
        ["set_component_tick_enabled", "SetComponentTickEnabled"],
        [(True,)],
        call_trace,
        warnings,
        applied_methods,
    )
    call_method_variants(
        component,
        "activate",
        ["activate", "Activate"],
        [(True,)],
        call_trace,
        warnings,
        applied_methods,
    )

    if hasattr(unreal, "AnimationMode"):
        mode_set, _ = call_method_variants(
            component,
            "set_animation_mode",
            ["set_animation_mode", "SetAnimationMode"],
            [
                (unreal.AnimationMode.ANIMATION_SINGLE_NODE, True),
                (unreal.AnimationMode.ANIMATION_SINGLE_NODE,),
            ],
            call_trace,
            warnings,
            applied_methods,
        )
        success = mode_set or success

    override_applied, _ = call_method_variants(
        component,
        "override_animation_data",
        ["override_animation_data", "OverrideAnimationData"],
        [
            (animation_asset, False, False, float(sample_time_seconds), 0.0),
            (animation_asset, False, False, float(sample_time_seconds), 1.0),
        ],
        call_trace,
        warnings,
        applied_methods,
    )
    success = override_applied or success

    set_animation_applied, _ = call_method_variants(
        component,
        "set_animation",
        ["set_animation", "SetAnimation"],
        [(animation_asset,)],
        call_trace,
        warnings,
        applied_methods,
    )
    success = set_animation_applied or success

    call_method_variants(
        component,
        "stop",
        ["stop", "Stop"],
        [tuple()],
        call_trace,
        warnings,
        applied_methods,
    )
    call_method_variants(
        component,
        "set_play_rate",
        ["set_play_rate", "SetPlayRate"],
        [(0.0,)],
        call_trace,
        warnings,
        applied_methods,
    )
    call_method_variants(
        component,
        "set_position",
        ["set_position", "SetPosition"],
        [
            (float(sample_time_seconds), False),
            (float(sample_time_seconds),),
        ],
        call_trace,
        warnings,
        applied_methods,
    )

    single_node_instance = None
    _, single_node_instance = call_method_variants(
        component,
        "get_single_node_instance",
        ["get_single_node_instance", "GetSingleNodeInstance"],
        [tuple()],
        call_trace,
        warnings,
        applied_methods,
    )
    if single_node_instance:
        call_method_variants(
            single_node_instance,
            "single_node_set_animation_asset",
            ["set_animation_asset", "SetAnimationAsset"],
            [(animation_asset, False, 0.0), (animation_asset, False)],
            call_trace,
            warnings,
            applied_methods,
        )
        call_method_variants(
            single_node_instance,
            "single_node_set_looping",
            ["set_looping", "SetLooping"],
            [(False,)],
            call_trace,
            warnings,
            applied_methods,
        )
        call_method_variants(
            single_node_instance,
            "single_node_set_play_rate",
            ["set_play_rate", "SetPlayRate"],
            [(0.0,)],
            call_trace,
            warnings,
            applied_methods,
        )
        call_method_variants(
            single_node_instance,
            "single_node_set_playing",
            ["set_playing", "SetPlaying"],
            [(False,)],
            call_trace,
            warnings,
            applied_methods,
        )
        call_method_variants(
            single_node_instance,
            "single_node_set_position_with_previous_time",
            ["set_position_with_previous_time", "SetPositionWithPreviousTime"],
            [(float(sample_time_seconds), 0.0, False), (float(sample_time_seconds), 0.0)],
            call_trace,
            warnings,
            applied_methods,
        )
        pose_set, _ = call_method_variants(
            single_node_instance,
            "single_node_set_position",
            ["set_position", "SetPosition"],
            [(float(sample_time_seconds), False), (float(sample_time_seconds),)],
            call_trace,
            warnings,
            applied_methods,
        )
        success = pose_set or success

    call_method_variants(
        component,
        "tick_animation",
        ["tick_animation", "TickAnimation"],
        [(float(sample_time_seconds), False), (0.0, False)],
        call_trace,
        warnings,
        applied_methods,
    )
    call_method_variants(
        component,
        "tick_pose",
        ["tick_pose", "TickPose"],
        [(float(sample_time_seconds), False), (0.0, False)],
        call_trace,
        warnings,
        applied_methods,
    )
    call_method_variants(
        component,
        "refresh_bone_transforms",
        ["refresh_bone_transforms", "RefreshBoneTransforms"],
        [(None,), tuple()],
        call_trace,
        warnings,
        applied_methods,
    )
    call_method_variants(
        component,
        "update_bounds",
        ["update_bounds", "UpdateBounds"],
        [tuple()],
        call_trace,
        warnings,
        applied_methods,
    )
    for method_name in ("mark_render_transform_dirty", "mark_render_dynamic_data_dirty", "mark_render_state_dirty"):
        if hasattr(component, method_name):
            try:
                getattr(component, method_name)()
                applied_methods.append(method_name)
            except Exception:
                continue

    return {
        "success": bool(success),
        "warnings": warnings,
        "applied_methods": applied_methods,
        "call_trace": call_trace,
        "available_component_methods": interesting_member_names(
            component,
            [
                "set_animation_mode",
                "SetAnimationMode",
                "override_animation_data",
                "OverrideAnimationData",
                "set_animation",
                "SetAnimation",
                "play_animation",
                "PlayAnimation",
                "stop",
                "Stop",
                "set_position",
                "SetPosition",
                "set_play_rate",
                "SetPlayRate",
                "get_single_node_instance",
                "GetSingleNodeInstance",
                "tick_animation",
                "TickAnimation",
                "tick_pose",
                "TickPose",
                "refresh_bone_transforms",
                "RefreshBoneTransforms",
                "update_bounds",
                "UpdateBounds",
                "set_update_animation_in_editor",
                "SetUpdateAnimationInEditor",
                "set_enable_animation",
                "SetEnableAnimation",
            ],
        ),
        "available_single_node_methods": interesting_member_names(
            single_node_instance,
            [
                "set_animation_asset",
                "SetAnimationAsset",
                "set_looping",
                "SetLooping",
                "set_play_rate",
                "SetPlayRate",
                "set_playing",
                "SetPlaying",
                "set_position",
                "SetPosition",
                "set_position_with_previous_time",
                "SetPositionWithPreviousTime",
                "get_current_time",
                "GetCurrentTime",
                "get_length",
                "GetLength",
            ],
        ),
    }


def animation_preview(request: dict) -> dict:
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
    animation_asset = unreal.EditorAssetLibrary.load_asset(object_path_from_asset_path(animation_asset_path)) if animation_asset_path else None
    if not animation_asset:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"animation_asset_load_failed:{animation_asset_path or 'missing'}"],
        }

    spawn_location = vector_from_request(request.get("location"), unreal.Vector(0.0, 0.0, 120.0))
    spawn_rotation = rotator_from_request(request.get("rotation"), make_rotator(0.0, 180.0, 0.0))
    actor_label = str(request.get("actor_label") or f"AIUE_AnimationPreview_{sanitize_segment(host_record.get('character_package_id') if host_record else host_asset_path)}")
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

        time.sleep(max(float(request.get("settle_delay_seconds") or 0.2), 0.05))
        primary_mesh = actor_primary_mesh_component(spawned_host)
        weapon_mesh = actor_weapon_mesh_component(spawned_host, primary_mesh)
        primary_mesh_asset = skeletal_mesh_asset_from_component(primary_mesh)
        primary_reference_skeleton = reference_skeleton_from_assets(
            skeleton_asset_from_skeletal_mesh_asset(primary_mesh_asset),
            primary_mesh_asset,
        )
        direct_compatibility = animation_compatibility_payload(primary_mesh, animation_asset)
        compatibility = dict(direct_compatibility)
        resolved_animation_asset = animation_asset
        resolved_animation_asset_path = animation_asset_path
        retarget_generation = {
            "attempted": False,
            "success": False,
            "warnings": [],
            "errors": [],
        }
        if not compatibility.get("compatible") and bool(request.get("retarget_if_needed")):
            retarget_generation = generate_retargeted_animation_for_preview(primary_mesh, animation_asset, request)
            retarget_generation["attempted"] = True
            warnings.extend(retarget_generation.get("warnings") or [])
            if retarget_generation.get("retargeted_animation_asset_path"):
                resolved_animation_asset_path = str(retarget_generation.get("retargeted_animation_asset_path") or animation_asset_path)
                resolved_animation_asset = load_asset_from_any_path(resolved_animation_asset_path) or resolved_animation_asset
            compatibility = dict(retarget_generation.get("retargeted_compatibility") or compatibility)
        if not compatibility.get("compatible"):
            failed_requirements.append("animation_skeleton_incompatible")
        if retarget_generation.get("attempted") and not retarget_generation.get("success"):
            failed_requirements.append("retarget_generate_failed")

        main_mesh_component = component_visibility_record(primary_mesh)
        weapon_mesh_component = component_visibility_record(weapon_mesh)
        output_root = Path(request.get("output_root") or (Path(unreal.Paths.project_saved_dir()) / "pmx_pipeline" / "animation_preview")).expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        before_root = output_root / "before"
        after_root = output_root / "after"
        before_root.mkdir(parents=True, exist_ok=True)
        after_root.mkdir(parents=True, exist_ok=True)
        shot_plans = filtered_visual_shots(spawned_host, request)
        if not shot_plans:
            failed_requirements.append("shot_plan_missing")

        before_capture_by_shot = {}
        probe_bone_names = [str(name) for name in list(request.get("pose_probe_bone_names") or []) if str(name)]
        sampled_animation_pose = {
            "success": False,
            "warnings": [],
            "errors": ["animation_pose_sampling_skipped"],
            "sample_time_seconds": float(request.get("animation_sample_time_seconds") or 0.0),
            "bone_count": len(probe_bone_names),
            "bone_poses": {},
            "api_trace": [],
        }
        sampled_animation_pose_delta = {
            "changed_bone_count": 0,
            "translation_changed_bone_count": 0,
            "rotation_changed_bone_count": 0,
            "delta_by_bone": {},
        }
        native_animation_pose_evaluation = {
            "available": hasattr(unreal, "PMXEquipmentBlueprintLibrary"),
            "success": False,
            "pose_changed": False,
            "warnings": [],
            "errors": ["native_animation_pose_evaluation_skipped"],
            "applied_methods": [],
            "probe_results": [],
            "sample_time_seconds": 0.0,
            "bone_count": 0,
            "changed_bone_count": 0,
            "max_location_delta": 0.0,
            "max_rotation_angle_delta_degrees": 0.0,
            "max_scale_delta": 0.0,
        }
        pose_probe_before = probe_component_pose(primary_mesh, probe_bone_names)
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

        animation_application = {
            "success": False,
            "warnings": [],
            "applied_methods": [],
        }
        sample_time_seconds = float(request.get("animation_sample_time_seconds") or max(0.1, float(compatibility.get("animation_play_length_seconds") or 0.5) * 0.5))
        if compatibility.get("compatible"):
            native_animation_pose_evaluation = evaluate_animation_pose_on_component_native(
                primary_mesh,
                resolved_animation_asset,
                sample_time_seconds,
                probe_bone_names,
            )
            warnings.extend(native_animation_pose_evaluation.get("warnings") or [])
            sampled_animation_pose = sample_animation_local_pose(
                resolved_animation_asset,
                probe_bone_names,
                sample_time_seconds,
                preview_mesh_asset=primary_mesh_asset,
            )
            if sampled_animation_pose.get("success"):
                sampled_animation_pose_delta = animation_pose_delta_against_reference(
                    sampled_animation_pose,
                    reference_skeleton_pose_records(primary_reference_skeleton),
                )
            else:
                warnings.extend(list(sampled_animation_pose.get("errors") or []))
            native_driver_success = bool(native_animation_pose_evaluation.get("success")) and bool(native_animation_pose_evaluation.get("pose_changed"))
            animation_application = {
                "success": native_driver_success,
                "warnings": list(native_animation_pose_evaluation.get("warnings") or []),
                "errors": list(native_animation_pose_evaluation.get("errors") or []),
                "applied_methods": list(native_animation_pose_evaluation.get("applied_methods") or []),
                "driver": "native_runtime",
            }
            if not native_driver_success:
                fallback_application = apply_animation_pose_to_component(primary_mesh, resolved_animation_asset, sample_time_seconds)
                warnings.extend(fallback_application.get("warnings") or [])
                animation_application = {
                    "success": bool(fallback_application.get("success")),
                    "warnings": sorted(set(list(native_animation_pose_evaluation.get("warnings") or []) + list(fallback_application.get("warnings") or []))),
                    "errors": sorted(set(list(native_animation_pose_evaluation.get("errors") or []) + list(fallback_application.get("errors") or []))),
                    "applied_methods": list(native_animation_pose_evaluation.get("applied_methods") or []) + list(fallback_application.get("applied_methods") or []),
                    "driver": "native_runtime_with_python_fallback",
                }
            if not animation_application.get("success"):
                failed_requirements.append("animation_apply_failed")
        else:
            warnings.append("animation_preview_skipped_due_to_skeleton_incompatibility")

        time.sleep(max(float(request.get("animation_settle_seconds") or 0.1), 0.05))
        pose_probe_after = probe_component_pose(primary_mesh, probe_bone_names)
        pose_probe_delta = pose_delta_payload(pose_probe_before, pose_probe_after)
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
            if not compatibility.get("compatible"):
                shot_errors.append("animation_skeleton_incompatible")
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

        return {
            "status": "pass" if not failed_requirements else "fail",
            "package_id": host_record.get("character_package_id") if host_record else request.get("package_id"),
            "sample_id": host_record.get("sample_id") if host_record else request.get("sample_id"),
            "host_id": spawned_host.get_path_name(),
            "host_blueprint_asset": host_asset_path,
            "level_path": level_path or get_current_level_path(),
            "animation_asset_path": animation_asset_path,
            "resolved_animation_asset_path": resolved_animation_asset_path,
            "direct_animation_compatibility": direct_compatibility,
            "animation_compatibility": compatibility,
            "retarget_generation": retarget_generation,
            "animation_application": animation_application,
            "native_animation_pose_evaluation": native_animation_pose_evaluation,
            "sampled_animation_pose": sampled_animation_pose,
            "sampled_animation_pose_delta": sampled_animation_pose_delta,
            "pose_probe_before": pose_probe_before,
            "pose_probe_after": pose_probe_after,
            "pose_probe_delta": pose_probe_delta,
            "main_mesh_component": {
                "component_name": main_mesh_component.get("component_name"),
                "class_name": main_mesh_component.get("class_name"),
            },
            "weapon_mesh_component": {
                "component_name": weapon_mesh_component.get("component_name"),
                "class_name": weapon_mesh_component.get("class_name"),
            },
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


def inspect_host_visual(request: dict) -> dict:
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

    cell_origin = vector_from_request(request.get("cell_origin"), unreal.Vector(0.0, 0.0, 30000.0))
    cell_rotation = rotator_from_request(request.get("cell_rotation"), make_rotator(0.0, 180.0, 0.0))
    actor_label = str(request.get("actor_label") or f"AIUE_VisualProof_{sanitize_segment(host_record.get('character_package_id') if host_record else host_asset_path)}")

    spawned_host = actor_subsystem.spawn_actor_from_object(blueprint_asset, cell_origin, cell_rotation, True)
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
        component_visibility = {
            "main_mesh": main_mesh_component,
            "weapon_mesh": weapon_mesh_component,
        }
        character_mesh_asset = main_mesh_component.get("asset_path") or ""
        weapon_mesh_asset = weapon_mesh_component.get("asset_path") or ""

        if not main_mesh_component.get("component_name"):
            failed_requirements.append("mesh_missing")
        if not character_mesh_asset:
            failed_requirements.append("mesh_missing")
        if not main_mesh_bounds.get("non_zero"):
            failed_requirements.append("bounds_invalid")
        if not weapon_mesh_component.get("component_name"):
            failed_requirements.append("weapon_missing")
        if not weapon_mesh_asset:
            failed_requirements.append("weapon_missing")
        if equipment_diagnostics.get("resolved_attach_socket_exists") is False:
            failed_requirements.append("socket_resolution_failed")

        output_root = Path(request.get("output_root") or (Path(unreal.Paths.project_saved_dir()) / "pmx_pipeline" / "visual_proof")).expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        width = int(request.get("width") or request.get("capture_width") or 1280)
        height = int(request.get("height") or request.get("capture_height") or 720)
        subject_min_screen_coverage = float(request.get("subject_min_screen_coverage") or 0.015)
        weapon_min_screen_coverage = float(request.get("weapon_min_screen_coverage") or 0.001)
        shot_plans = build_visual_proof_shots(spawned_host, request)

        subject_pass_count = 0
        weapon_pass_count = 0
        for shot_plan in shot_plans:
            metric_camera = actor_subsystem.spawn_actor_from_class(
                unreal.CameraActor,
                vector_from_request(shot_plan["camera_location"]),
                rotator_from_request(shot_plan["camera_rotation"]),
                True,
            )
            line_of_sight = {"clear": False, "reason": "metric_camera_spawn_failed"}
            subject_coverage = {"coverage_ratio": 0.0, "reason": "metric_camera_spawn_failed"}
            weapon_coverage = {"coverage_ratio": 0.0, "reason": "metric_camera_spawn_failed"}
            if metric_camera:
                try:
                    line_of_sight = line_of_sight_to_actor(metric_camera, spawned_host)
                    subject_coverage = screen_coverage_for_component(primary_mesh, metric_camera, width, height, fallback_actor=spawned_host)
                    weapon_coverage = screen_coverage_for_component(weapon_mesh, metric_camera, width, height)
                finally:
                    try:
                        actor_subsystem.destroy_actor(metric_camera)
                    except Exception:
                        pass
            image_path = output_root / f"{shot_plan['shot_id']}.png"
            capture_result = capture_frame(
                {
                    "actor_path": spawned_host.get_path_name(),
                    "actor_label": spawned_host.get_actor_label(),
                    "output_path": str(image_path),
                    "width": width,
                    "height": height,
                    "camera_mode": "explicit_pose",
                    "camera_source": shot_plan["camera_source"],
                    "camera_location": shot_plan["camera_location"],
                    "camera_rotation": shot_plan["camera_rotation"],
                    "capture_delay_seconds": float(request.get("capture_delay_seconds") or 0.2),
                    "timeout_seconds": float(request.get("timeout_seconds") or 15.0),
                    "file_stability_window_seconds": float(request.get("file_stability_window_seconds") or 0.75),
                    "poll_interval_seconds": float(request.get("poll_interval_seconds") or 0.1),
                }
            )
            shot_errors = list(capture_result.get("errors") or [])
            shot_warnings = list(capture_result.get("warnings") or [])
            subject_visible = bool(subject_coverage.get("coverage_ratio", 0.0) >= subject_min_screen_coverage)
            weapon_visible = bool(weapon_coverage.get("coverage_ratio", 0.0) >= weapon_min_screen_coverage)
            line_clear = bool(line_of_sight.get("clear"))
            if not subject_visible:
                shot_errors.append("out_of_frame")
            if not line_clear:
                shot_errors.append("occluded")
            if not capture_result.get("output_exists"):
                shot_errors.append("capture_failed")
            shot_status = "pass" if not shot_errors else "fail"
            subject_pass_count += int(subject_visible and line_clear and bool(capture_result.get("output_exists")))
            weapon_pass_count += int(weapon_visible)
            shots.append(
                {
                    "shot_id": shot_plan["shot_id"],
                    "camera_id": shot_plan["camera_id"],
                    "image_path": str(image_path.resolve()),
                    "camera_source": shot_plan["camera_source"],
                    "camera_location": shot_plan["camera_location"],
                    "camera_rotation": shot_plan["camera_rotation"],
                    "subject_screen_coverage": float(subject_coverage.get("coverage_ratio") or 0.0),
                    "weapon_screen_coverage": float(weapon_coverage.get("coverage_ratio") or 0.0),
                    "line_of_sight_clear": line_clear,
                    "line_of_sight": line_of_sight,
                    "subject_coverage": subject_coverage,
                    "weapon_coverage": weapon_coverage,
                    "status": shot_status,
                    "warnings": sorted(set(shot_warnings)),
                    "errors": sorted(set(shot_errors)),
                }
            )

        if subject_pass_count < 2:
            failed_requirements.append("out_of_frame")
        if weapon_pass_count < 1:
            failed_requirements.append("weapon_invisible")
        if any(shot.get("status") != "pass" for shot in shots) and "capture_failed" not in failed_requirements:
            if any("capture_failed" in (shot.get("errors") or []) for shot in shots):
                failed_requirements.append("capture_failed")
            if any("occluded" in (shot.get("errors") or []) for shot in shots):
                failed_requirements.append("occluded")

        return {
            "status": "pass" if not failed_requirements else "fail",
            "package_id": host_record.get("character_package_id") if host_record else request.get("package_id"),
            "host_id": spawned_host.get_path_name(),
            "host_blueprint_asset": host_asset_path,
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
            "component_visibility": component_visibility,
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


def run_scene_sweep(request: dict) -> dict:
    summary_path = request.get("summary")
    suite_output_path = Path(request.get("suite_output") or "").expanduser() if request.get("suite_output") else None
    capture_manifest_path = Path(request.get("capture_manifest_output") or "").expanduser() if request.get("capture_manifest_output") else None
    capture_root = Path(request.get("capture_root") or (Path(unreal.Paths.project_saved_dir()) / "pmx_pipeline" / "captures")).expanduser().resolve()
    capture_root.mkdir(parents=True, exist_ok=True)
    suite_output_path = suite_output_path.resolve() if suite_output_path else capture_root / "ue_animation_suite_summary.json"
    capture_manifest_path = capture_manifest_path.resolve() if capture_manifest_path else capture_root / "ue_capture_manifest.json"

    scenario_names = list(request.get("scenario_names") or ["idle_2s", "walk_forward_2s", "run_forward_2s", "jump_land_1cycle"])
    camera_mode = str(request.get("camera_mode") or "auto_framing")
    package_ids = [request.get("package_id")] if request.get("package_id") else []
    if not package_ids:
        report_path = resolve_equipment_report_path(request)
        if report_path and report_path.exists():
            report_payload = read_json(report_path)
            package_ids = [
                entry.get("character_package_id")
                for entry in (report_payload.get("host_blueprints") or [])
                if entry.get("has_runtime_weapon_mesh_component")
            ]

    package_results = []
    capture_entries = []
    current_level_path = None
    if request.get("level_lifecycle") == "reuse_level" or len(package_ids) <= 1:
        requested_level = request.get("level_path") or request.get("scene_level_path")
        if requested_level:
            load_result = load_level({"level_path": requested_level})
            current_level_path = load_result.get("current_level_path")
            if load_result.get("errors"):
                return {
                    "summary_path": summary_path,
                    "suite_output": str(suite_output_path),
                    "capture_manifest_output": str(capture_manifest_path),
                    "capture_root": str(capture_root),
                    "counts": {
                        "requested_packages": len(package_ids),
                        "completed_packages": 0,
                        "failed_packages": len(package_ids),
                        "capture_entries": 0,
                        "valid_images": 0,
                        "captured_before_report": 0,
                        "captured_after_report_before_exit": 0,
                        "captured_after_exit": 0,
                    },
                    "warnings": list(load_result.get("warnings") or []),
                    "errors": list(load_result.get("errors") or []),
                }

    for package_index, package_id in enumerate(package_ids, start=1):
        suite_record = load_suite_summary_record(summary_path, package_id)
        host_request = {
            "package_id": package_id,
            "sample_id": suite_record.get("sample_id"),
            "summary": summary_path,
            "report_path": str(resolve_equipment_report_path(request)) if resolve_equipment_report_path(request) else None,
            "runtime_ready_only": True,
        }
        try:
            host_asset_path, host_record, host_warnings = resolve_host_blueprint_asset_path(host_request)
        except Exception as exc:
            package_result = {
                "package_id": package_id,
                "sample_id": suite_record.get("sample_id"),
                "host_blueprint_asset_path": None,
                "status": "fail",
                "warnings": [],
                "errors": [str(exc)],
                "scenario_results": [],
            }
            package_results.append(package_result)
            continue

        scenario_results = []
        package_warnings = list(host_warnings)
        for scenario_index, scenario_name in enumerate(scenario_names, start=1):
            if request.get("level_lifecycle") == "reload_level_per_run":
                requested_level = request.get("level_path") or request.get("scene_level_path")
                if requested_level:
                    level_result = load_level({"level_path": requested_level})
                    current_level_path = level_result.get("current_level_path")
                    package_warnings.extend(level_result.get("warnings") or [])
                    if level_result.get("errors"):
                        scenario_result = {
                            "scenario": scenario_name,
                            "status": "fail",
                            "capture_status": "capture_failed",
                            "image_path": None,
                            "warnings": list(level_result.get("warnings") or []),
                            "errors": list(level_result.get("errors") or []),
                        }
                        scenario_results.append(scenario_result)
                        capture_entries.append(
                            {
                                "sample_id": suite_record.get("sample_id") or host_record.get("sample_id") if host_record else None,
                                "package_id": package_id,
                                "scenario": scenario_name,
                                "image_path": None,
                                "capture_status": "capture_failed",
                                "reference_dir": str(Path(summary_path).expanduser().resolve().parent) if summary_path else None,
                                "warnings": list(level_result.get("warnings") or []),
                                "errors": list(level_result.get("errors") or []),
                            }
                        )
                        continue

            overrides = scenario_capture_overrides(scenario_index, scenario_name, request)
            scenario_camera_mode = str(overrides.get("camera_mode") or camera_mode)
            package_capture_root = capture_root / sanitize_segment(package_id or f"package_{package_index:03d}")
            package_capture_root.mkdir(parents=True, exist_ok=True)
            image_path = package_capture_root / f"{scenario_index:02d}_{sanitize_segment(scenario_name)}.png"
            capture_request = {
                "summary": summary_path,
                "report_path": str(resolve_equipment_report_path(request)) if resolve_equipment_report_path(request) else None,
                "package_id": package_id,
                "sample_id": (suite_record.get("sample_id") or (host_record or {}).get("sample_id")),
                "host_blueprint_asset_path": host_asset_path,
                "runtime_ready_only": True,
                "level_path": None if request.get("level_lifecycle") == "reuse_level" else (request.get("level_path") or request.get("scene_level_path")),
                "actor_label": f"AIUE_{sanitize_segment(package_id)}_{sanitize_segment(scenario_name)}",
                "output_path": str(image_path),
                "width": int(request.get("capture_width") or request.get("width") or 1280),
                "height": int(request.get("capture_height") or request.get("height") or 720),
                "capture_delay_seconds": float(request.get("capture_delay_seconds") or 0.2),
                "timeout_seconds": float(request.get("settle_timeout_seconds") or request.get("timeout_seconds") or 20.0),
                "file_stability_window_seconds": float(request.get("file_stability_window_seconds") or 0.75),
                "poll_interval_seconds": float(request.get("viewport_pump_interval_seconds") or request.get("poll_interval_seconds") or 0.2),
                "camera_mode": scenario_camera_mode,
            }
            if scenario_camera_mode == "anchor_actor":
                capture_request["spawn_anchor_actor_label"] = str(overrides.get("spawn_anchor_actor_label") or request.get("spawn_anchor_actor_label") or "")
                capture_request["camera_anchor_actor_label"] = str(overrides.get("camera_anchor_actor_label") or request.get("camera_anchor_actor_label") or "")
                if overrides.get("expected_spawn_location") is not None:
                    capture_request["expected_spawn_location"] = overrides.get("expected_spawn_location")
                if overrides.get("expected_spawn_rotation") is not None:
                    capture_request["expected_spawn_rotation"] = overrides.get("expected_spawn_rotation")
                if overrides.get("expected_camera_location") is not None:
                    capture_request["expected_camera_location"] = overrides.get("expected_camera_location")
                if overrides.get("expected_camera_rotation") is not None:
                    capture_request["expected_camera_rotation"] = overrides.get("expected_camera_rotation")
            else:
                capture_request["location"] = overrides["location"]
                capture_request["rotation"] = overrides["rotation"]
                capture_request["camera_distance"] = overrides["camera_distance"]
                capture_request["camera_lateral_offset"] = overrides["camera_lateral_offset"]
                capture_request["camera_height"] = overrides["camera_height"]
                capture_request["target_height_offset"] = overrides["target_height_offset"] or float(request.get("target_height_offset") or 0.0)
            capture_result = capture_frame(capture_request)
            if not capture_result.get("output_exists") and capture_result.get("output_path"):
                finalized_output_path, _ = wait_for_screenshot(
                    None,
                    Path(capture_result["output_path"]),
                    float(request.get("quit_barrier_seconds") or 2.0) + float(request.get("file_stability_window_seconds") or 0.75) + 1.0,
                    float(request.get("file_stability_window_seconds") or 0.75),
                    float(request.get("viewport_pump_interval_seconds") or 0.2),
                )
                if finalized_output_path and finalized_output_path.exists():
                    capture_result["output_path"] = str(finalized_output_path)
                    capture_result["output_exists"] = True
                    capture_result["file_size_bytes"] = finalized_output_path.stat().st_size
                    capture_result["task_done"] = True
                    capture_result["warnings"] = [
                        warning
                        for warning in (capture_result.get("warnings") or [])
                        if warning != "screenshot_output_missing_after_task_completion"
                    ]
                    capture_result["errors"] = []
            capture_success = not capture_result.get("errors") and bool(capture_result.get("output_exists"))
            capture_status = "captured_before_report" if capture_success else "capture_failed"
            scenario_result = {
                "scenario": scenario_name,
                "status": "pass" if capture_success else "fail",
                "capture_status": capture_status,
                "image_path": capture_result.get("output_path"),
                "camera_source": capture_result.get("camera_source") or scenario_camera_mode,
                "capture_backend": capture_result.get("capture_backend"),
                "spawn_anchor_actor_label": capture_result.get("spawn_anchor_actor_label") or capture_request.get("spawn_anchor_actor_label") or "",
                "camera_anchor_actor_label": capture_result.get("camera_anchor_actor_label") or capture_request.get("camera_anchor_actor_label") or "",
                "subject_visible": bool(capture_result.get("subject_visible")),
                "subject_visibility": dict(capture_result.get("subject_visibility") or {}),
                "target_render_components": list(capture_result.get("target_render_components") or []),
                "warnings": list(capture_result.get("warnings") or []),
                "errors": list(capture_result.get("errors") or []),
                "camera_plan": capture_result.get("camera_plan"),
            }
            scenario_results.append(scenario_result)
            capture_entries.append(
                {
                    "sample_id": suite_record.get("sample_id") or (host_record or {}).get("sample_id"),
                    "package_id": package_id,
                    "scenario": scenario_name,
                    "image_path": capture_result.get("output_path"),
                    "capture_status": capture_status,
                    "camera_source": scenario_result["camera_source"],
                    "spawn_anchor_actor_label": scenario_result["spawn_anchor_actor_label"],
                    "camera_anchor_actor_label": scenario_result["camera_anchor_actor_label"],
                    "subject_visible": scenario_result["subject_visible"],
                    "reference_dir": str(package_capture_root),
                    "warnings": list(capture_result.get("warnings") or []),
                    "errors": list(capture_result.get("errors") or []),
                    "host_blueprint_asset_path": host_asset_path,
                }
            )

        package_failed = any(result.get("status") != "pass" for result in scenario_results)
        package_results.append(
            {
                "package_id": package_id,
                "sample_id": suite_record.get("sample_id") or (host_record or {}).get("sample_id"),
                "host_blueprint_asset_path": host_asset_path,
                "status": "fail" if package_failed else "pass",
                "warnings": package_warnings,
                "errors": [] if not package_failed else ["one_or_more_scenarios_failed"],
                "scenario_results": scenario_results,
            }
        )

    manifest_payload = {
        "generated_at_utc": now_utc(),
        "suite_name": "ue_scene_sweep",
        "suite_summary_path": str(suite_output_path),
        "capture_enabled": True,
        "capture_root": str(capture_root),
        "entries": capture_entries,
    }
    summary_payload = {
        "generated_at_utc": now_utc(),
        "summary_source_path": summary_path,
        "capture_root": str(capture_root),
        "suite_output_path": str(suite_output_path),
        "capture_manifest_output": str(capture_manifest_path),
        "package_results": package_results,
        "scenario_names": scenario_names,
        "config": {
            "validation_mode": request.get("validation_mode"),
            "camera_lifecycle": request.get("camera_lifecycle"),
            "camera_mode": camera_mode,
            "level_lifecycle": request.get("level_lifecycle"),
            "scenario_scheduling": request.get("scenario_scheduling"),
            "completion_strategy": request.get("completion_strategy"),
        },
    }
    write_json(capture_manifest_path, manifest_payload)
    write_json(suite_output_path, summary_payload)

    valid_images = sum(1 for entry in capture_entries if entry.get("capture_status") == "captured_before_report" and entry.get("image_path"))
    failed_packages = sum(1 for item in package_results if item.get("status") != "pass")
    result = {
        "summary_path": summary_path,
        "suite_output": str(suite_output_path),
        "capture_manifest_output": str(capture_manifest_path),
        "capture_root": str(capture_root),
        "level_path": request.get("level_path") or request.get("scene_level_path"),
        "current_level_path": current_level_path or get_current_level_path(),
        "scenario_names": scenario_names,
        "package_results": package_results,
        "counts": {
            "requested_packages": len(package_ids),
            "completed_packages": len(package_results) - failed_packages,
            "failed_packages": failed_packages,
            "capture_entries": len(capture_entries),
            "valid_images": valid_images,
            "captured_before_report": valid_images,
            "captured_after_report_before_exit": 0,
            "captured_after_exit": 0,
            "late_captures": 0,
        },
        "warnings": [],
        "errors": [],
    }
    if not package_ids:
        result["warnings"].append("no_package_ids_resolved_for_scene_sweep")
    if failed_packages:
        result["errors"].append("scene_sweep_failed_packages_present")
    return result


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


def dispatch(request: dict) -> dict:
    command = request["command"]
    if command == "inspect-host":
        return inspect_host(request)
    if command == "inspect-host-visual":
        return inspect_host_visual(request)
    if command == "action-preview":
        return action_preview(request)
    if command == "animation-preview":
        return animation_preview(request)
    if command == "retarget-preflight":
        return retarget_preflight(request)
    if command == "retarget-bootstrap":
        return retarget_bootstrap(request)
    if command == "retarget-author-chains":
        return retarget_author_chains(request)
    if command == "debug-physics-api":
        return debug_physics_api(request)
    if command == "load-level":
        return load_level(request)
    if command == "spawn-host":
        return spawn_host(request)
    if command == "inspect-stage-anchors":
        return inspect_stage_anchors(request)
    if command == "ensure-stage-anchors":
        return ensure_stage_anchors(request)
    if command == "capture-frame":
        return capture_frame(request)
    if command == "stage-capture":
        stage_request = dict(request)
        stage_request["command"] = "capture-frame"
        return capture_frame(stage_request)
    if command == "run-scene-sweep":
        return run_scene_sweep(request)
    if command == "list-assets":
        return list_assets(request)
    if command == "build-equipment-registry":
        return build_equipment_registry(request)
    if command == "import-package" and request.get("dry_run"):
        return import_package_dry_run(request)
    if command == "import-package":
        return import_package(request)
    return {
        "warnings": [],
        "errors": [f"unsupported_command:{command}"],
    }


def main() -> int:
    if len(sys.argv) >= 3:
        request_path = Path(sys.argv[1]).expanduser().resolve()
        response_path = Path(sys.argv[2]).expanduser().resolve()
    else:
        request_env = os.environ.get("AIUE_REQUEST_PATH")
        response_env = os.environ.get("AIUE_RESPONSE_PATH")
        if not request_env or not response_env:
            raise RuntimeError("AIUE_REQUEST_PATH and AIUE_RESPONSE_PATH must be provided")
        request_path = Path(request_env).expanduser().resolve()
        response_path = Path(response_env).expanduser().resolve()
    request = json.loads(request_path.read_text(encoding="utf-8-sig"))
    try:
        result = dispatch(request)
        payload = {
            "success": not result.get("errors"),
            "result": result,
            "warnings": result.get("warnings", []),
            "errors": result.get("errors", []),
        }
    except Exception as exc:
        payload = {
            "success": False,
            "result": {},
            "warnings": [],
            "errors": [str(exc), traceback.format_exc()],
        }
    response_path.parent.mkdir(parents=True, exist_ok=True)
    response_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if payload["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
