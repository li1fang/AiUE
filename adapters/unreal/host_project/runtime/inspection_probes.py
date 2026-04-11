from __future__ import annotations

from .common import *


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


__all__ = [
    "debug_physics_api",
    "inspect_host",
    "list_assets",
]
