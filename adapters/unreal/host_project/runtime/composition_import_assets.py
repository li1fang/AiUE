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


__all__ = [
    "load_existing_import_blueprint",
    "resolve_texture_files",
    "classify_imported_assets",
    "path_for_loaded_asset",
    "enrich_related_assets",
    "import_skeletal_mesh",
    "material_slot_names",
    "create_physics_asset_for_mesh",
]
