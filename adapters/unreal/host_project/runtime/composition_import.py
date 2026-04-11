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



