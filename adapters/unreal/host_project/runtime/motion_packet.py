from __future__ import annotations

from pathlib import Path

from .common import *
from .composition_registry_assets import blueprint_cdo


SUPPORTED_FORMAT_PROFILE = "route_a_kimodo_somaskel77"
SUPPORTED_RUNTIME_SEMANTICS = "runtime"
SUPPORTED_SKELETON_ID = "somaskel77"


def _asset_path_from_object_path(object_path: str | None) -> str:
    if not object_path:
        return ""
    return str(object_path).split(".", 1)[0]


def _search_skeleton_asset(explicit_asset_path: str) -> tuple[object | None, str, list[str]]:
    warnings: list[str] = []
    package_path = str(explicit_asset_path or "").strip()
    if not package_path.startswith("/Game/") or "/" not in package_path:
        return None, "", warnings
    folder_path = package_path.rsplit("/", 1)[0]
    try:
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        assets = list(registry.get_assets_by_path(to_name(folder_path), recursive=False))
    except Exception as exc:
        warnings.append(f"target_skeleton_folder_scan_failed:{exc}")
        return None, "", warnings

    matching_assets = [asset_data for asset_data in assets if asset_class_name(asset_data) == "Skeleton"]
    if not matching_assets:
        warnings.append(f"target_skeleton_folder_scan_empty:{folder_path}")
        return None, "", warnings

    matching_assets.sort(key=lambda item: str(getattr(item, "asset_name", "") or ""))
    selected_asset_data = matching_assets[0]
    object_path = asset_object_path(selected_asset_data)
    loaded_asset = unreal.EditorAssetLibrary.load_asset(object_path)
    if not loaded_asset:
        warnings.append(f"target_skeleton_folder_scan_load_failed:{object_path}")
        return None, "", warnings
    resolved_asset_path = _asset_path_from_object_path(object_path)
    warnings.append(f"explicit_target_skeleton_resolved_by_folder_scan:{folder_path}")
    return loaded_asset, resolved_asset_path, warnings


def _load_packet_manifest(request: dict) -> tuple[Path, dict]:
    manifest_value = str(request.get("manifest") or request.get("manifest_path") or "").strip()
    if not manifest_value:
        raise ValueError("manifest_missing")
    manifest_path = Path(manifest_value).expanduser().resolve()
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest_missing:{manifest_path}")
    return manifest_path, read_json(manifest_path)


def _supported_packet_errors(manifest: dict) -> list[str]:
    errors = []
    if str(manifest.get("format_profile") or "") != SUPPORTED_FORMAT_PROFILE:
        errors.append(f"unsupported_format_profile:{manifest.get('format_profile') or 'missing'}")
    if str(manifest.get("runtime_semantics") or "") != SUPPORTED_RUNTIME_SEMANTICS:
        errors.append(f"unsupported_runtime_semantics:{manifest.get('runtime_semantics') or 'missing'}")
    if bool(manifest.get("placeholder_motion")):
        errors.append("placeholder_motion_not_supported")
    skeleton = manifest.get("skeleton") or {}
    if str(skeleton.get("skeleton_id") or "") != SUPPORTED_SKELETON_ID:
        errors.append(f"unsupported_skeleton_id:{skeleton.get('skeleton_id') or 'missing'}")
    validation = manifest.get("validation") or {}
    if str(validation.get("status") or "").strip().lower() != "pass":
        errors.append(f"motion_validation_not_pass:{validation.get('status') or 'missing'}")
    return errors


def _resolve_target_skeleton(request: dict) -> tuple[object | None, str, str, list[str]]:
    warnings: list[str] = []
    explicit_asset_path = str(request.get("target_skeleton_asset_path") or "").strip()
    if explicit_asset_path:
        skeleton_asset = unreal.EditorAssetLibrary.load_asset(object_path_from_asset_path(explicit_asset_path))
        if skeleton_asset:
            return skeleton_asset, explicit_asset_path, "", warnings
        scanned_asset, scanned_asset_path, scan_warnings = _search_skeleton_asset(explicit_asset_path)
        warnings.extend(scan_warnings)
        if scanned_asset:
            return scanned_asset, scanned_asset_path, "", warnings
        warnings.append(f"explicit_target_skeleton_missing:{explicit_asset_path}")

    try:
        host_asset_path, _, host_warnings = resolve_host_blueprint_asset_path(
            {
                **request,
                "runtime_ready_only": request.get("runtime_ready_only", True),
            }
        )
    except Exception as exc:
        warnings.append(f"target_host_resolution_failed:{exc}")
        return None, "", "", warnings

    warnings.extend(host_warnings)
    blueprint_asset = unreal.EditorAssetLibrary.load_asset(object_path_from_asset_path(str(host_asset_path)))
    if not blueprint_asset:
        warnings.append(f"target_host_blueprint_missing:{host_asset_path}")
        return None, "", str(host_asset_path), warnings

    cdo = blueprint_cdo(blueprint_asset)
    primary_mesh = actor_primary_mesh_component(cdo)
    skeletal_mesh_asset = None
    if primary_mesh is not None:
        try:
            skeletal_mesh_asset = primary_mesh.get_editor_property("skeletal_mesh")
        except Exception:
            skeletal_mesh_asset = None
    if skeletal_mesh_asset is None:
        warnings.append("target_host_primary_mesh_missing")
        return None, "", str(host_asset_path), warnings

    skeleton_asset = None
    try:
        skeleton_asset = skeletal_mesh_asset.get_editor_property("skeleton")
    except Exception:
        skeleton_asset = None
    if not skeleton_asset:
        warnings.append("target_host_skeleton_missing")
        return None, "", str(host_asset_path), warnings
    return skeleton_asset, path_for_loaded_asset(skeleton_asset) or "", str(host_asset_path), warnings


def _build_animation_import_options(target_skeleton) -> object:
    options = unreal.FbxImportUI()
    set_if_present(options, "automated_import_should_detect_type", False)
    set_if_present(options, "import_mesh", False)
    set_if_present(options, "import_as_skeletal", True)
    set_if_present(options, "import_animations", True)
    set_if_present(options, "import_materials", False)
    set_if_present(options, "import_textures", False)
    if target_skeleton is not None:
        set_if_present(options, "skeleton", target_skeleton)
    if hasattr(unreal, "FBXImportType"):
        set_if_present(options, "original_import_type", unreal.FBXImportType.FBXIT_ANIMATION)
        set_if_present(options, "mesh_type_to_import", unreal.FBXImportType.FBXIT_ANIMATION)
    try:
        anim_data = options.get_editor_property("anim_sequence_import_data")
    except Exception:
        anim_data = None
    if anim_data is not None:
        set_if_present(anim_data, "convert_scene", True)
        set_if_present(anim_data, "convert_scene_unit", False)
        set_if_present(anim_data, "import_uniform_scale", 1.0)
    return options


def _build_source_bundle_import_options() -> object:
    options = unreal.FbxImportUI()
    set_if_present(options, "automated_import_should_detect_type", False)
    set_if_present(options, "import_mesh", True)
    set_if_present(options, "import_as_skeletal", True)
    set_if_present(options, "import_animations", False)
    set_if_present(options, "import_materials", False)
    set_if_present(options, "import_textures", False)
    set_if_present(options, "create_physics_asset", False)
    if hasattr(unreal, "FBXImportType"):
        set_if_present(options, "original_import_type", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
        set_if_present(options, "mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    try:
        skeletal_data = options.get_editor_property("skeletal_mesh_import_data")
    except Exception:
        skeletal_data = None
    if skeletal_data is not None:
        set_if_present(skeletal_data, "convert_scene", True)
        set_if_present(skeletal_data, "convert_scene_unit", False)
        set_if_present(skeletal_data, "import_uniform_scale", 1.0)
        set_if_present(skeletal_data, "update_skeleton_reference_pose", False)
        set_if_present(skeletal_data, "use_t0_as_ref_pose", True)
        set_if_present(skeletal_data, "preserve_smoothing_groups", True)
        set_if_present(skeletal_data, "import_meshes_in_bone_hierarchy", True)
    try:
        anim_data = options.get_editor_property("anim_sequence_import_data")
    except Exception:
        anim_data = None
    if anim_data is not None:
        set_if_present(anim_data, "convert_scene", True)
        set_if_present(anim_data, "convert_scene_unit", False)
        set_if_present(anim_data, "import_uniform_scale", 1.0)
    return options


def _disable_interchange_fbx_import() -> list[str]:
    warnings: list[str] = []
    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
        unreal.SystemLibrary.execute_console_command(world, "Interchange.FeatureFlags.Import.FBX False")
        warnings.append("interchange_fbx_import_disabled_for_motion_import")
    except Exception as exc:
        warnings.append(f"interchange_fbx_import_toggle_failed:{exc}")
    return warnings


def _resolve_import_destination(manifest: dict, request: dict) -> tuple[str, str]:
    destination_root = str(request.get("motion_asset_root") or request.get("asset_root") or "/Game/AiUE/MotionPackets").rstrip("/")
    sample_id = sanitize_segment(str(manifest.get("sample_id") or request.get("sample_id") or "sample"))
    package_id = sanitize_segment(str(manifest.get("package_id") or request.get("package_id") or "package"))
    destination_path = f"{destination_root}/{sample_id}"
    asset_name = f"AN_{package_id}"
    return destination_path, asset_name


def _scan_imported_motion_assets(destination_path: str) -> dict[str, str]:
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    result = {
        "animation_asset_path": "",
        "skeletal_mesh_asset_path": "",
        "skeleton_asset_path": "",
    }
    try:
        assets = list(registry.get_assets_by_path(to_name(destination_path), recursive=False) or [])
    except Exception:
        assets = []
    for asset_data in assets:
        class_name = asset_class_name(asset_data)
        object_path = asset_object_path(asset_data)
        canonical_path = _asset_path_from_object_path(object_path)
        if class_name in {"AnimSequence", "AnimationAsset"} and not result["animation_asset_path"]:
            result["animation_asset_path"] = canonical_path
        elif class_name == "SkeletalMesh" and not result["skeletal_mesh_asset_path"]:
            result["skeletal_mesh_asset_path"] = canonical_path
        elif class_name == "Skeleton" and not result["skeleton_asset_path"]:
            result["skeleton_asset_path"] = canonical_path
    return result


def _resolve_existing_source_bundle_assets(source_bundle_path: str, asset_name: str) -> dict[str, str]:
    candidates = {
        "animation_asset_path": f"{source_bundle_path}/{asset_name}_Anim",
        "skeletal_mesh_asset_path": f"{source_bundle_path}/{asset_name}",
        "skeleton_asset_path": f"{source_bundle_path}/{asset_name}_Skeleton",
    }
    resolved = {
        "animation_asset_path": "",
        "skeletal_mesh_asset_path": "",
        "skeleton_asset_path": "",
    }
    for key, asset_path in candidates.items():
        if unreal.EditorAssetLibrary.does_asset_exist(object_path_from_asset_path(asset_path)):
            resolved[key] = asset_path
    return resolved


def _load_source_bundle_skeleton(source_bundle_path: str, asset_name: str) -> tuple[object | None, dict[str, str]]:
    resolved = _resolve_existing_source_bundle_assets(source_bundle_path, asset_name)
    skeleton_asset_path = resolved["skeleton_asset_path"]
    if skeleton_asset_path:
        skeleton_asset = unreal.EditorAssetLibrary.load_asset(object_path_from_asset_path(skeleton_asset_path))
        if skeleton_asset:
            save_loaded_asset(skeleton_asset)
            return skeleton_asset, resolved

    skeletal_mesh_asset_path = resolved["skeletal_mesh_asset_path"]
    if skeletal_mesh_asset_path:
        skeletal_mesh_asset = unreal.EditorAssetLibrary.load_asset(object_path_from_asset_path(skeletal_mesh_asset_path))
        if skeletal_mesh_asset:
            save_loaded_asset(skeletal_mesh_asset)
            try:
                skeleton_asset = skeletal_mesh_asset.get_editor_property("skeleton")
            except Exception:
                skeleton_asset = None
            if skeleton_asset:
                save_loaded_asset(skeleton_asset)
                resolved["skeleton_asset_path"] = path_for_loaded_asset(skeleton_asset) or ""
                return skeleton_asset, resolved
    return None, resolved


def _import_source_bundle_animation(
    motion_source_path: Path,
    source_bundle_path: str,
    asset_name: str,
    source_skeleton,
) -> str:
    animation_asset_name = f"{asset_name}_Anim"
    animation_task = unreal.AssetImportTask()
    animation_task.set_editor_property("filename", str(motion_source_path))
    animation_task.set_editor_property("destination_path", source_bundle_path)
    set_if_present(animation_task, "destination_name", animation_asset_name)
    animation_task.set_editor_property("replace_existing", True)
    animation_task.set_editor_property("replace_existing_settings", True)
    animation_task.set_editor_property("automated", True)
    animation_task.set_editor_property("save", True)
    animation_task.set_editor_property("options", _build_animation_import_options(source_skeleton))
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([animation_task])

    imported_paths = list(animation_task.get_editor_property("imported_object_paths") or [])
    for object_path in imported_paths:
        class_name = load_asset_class_name(object_path)
        if class_name in {"AnimSequence", "AnimationAsset"}:
            return _asset_path_from_object_path(object_path)

    expected_animation_asset_path = f"{source_bundle_path}/{animation_asset_name}"
    if unreal.EditorAssetLibrary.does_asset_exist(object_path_from_asset_path(expected_animation_asset_path)):
        return expected_animation_asset_path
    return ""


def _import_motion_asset(motion_source_path: Path, destination_path: str, asset_name: str, target_skeleton) -> tuple[dict[str, str], list[str]]:
    ensure_directory(destination_path)
    warnings: list[str] = []
    warnings.extend(_disable_interchange_fbx_import())
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(motion_source_path))
    task.set_editor_property("destination_path", destination_path)
    set_if_present(task, "destination_name", asset_name)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("replace_existing_settings", True)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("options", _build_animation_import_options(target_skeleton))
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    imported_paths = list(task.get_editor_property("imported_object_paths") or [])
    for object_path in imported_paths:
        class_name = load_asset_class_name(object_path)
        if class_name in {"AnimSequence", "AnimationAsset"}:
            return {
                "animation_asset_path": _asset_path_from_object_path(object_path),
                "skeletal_mesh_asset_path": "",
                "skeleton_asset_path": path_for_loaded_asset(target_skeleton) or "",
                "import_mode": "target_skeleton_animation",
            }, warnings
    expected_asset_path = f"{destination_path}/{asset_name}"
    if unreal.EditorAssetLibrary.does_asset_exist(object_path_from_asset_path(expected_asset_path)):
        return {
            "animation_asset_path": expected_asset_path,
            "skeletal_mesh_asset_path": "",
            "skeleton_asset_path": path_for_loaded_asset(target_skeleton) or "",
            "import_mode": "target_skeleton_animation",
        }, warnings
    warnings.append("import_completed_without_animsequence_object_path")

    source_bundle_path = f"{destination_path}/Source"
    ensure_directory(source_bundle_path)
    fallback_task = unreal.AssetImportTask()
    fallback_task.set_editor_property("filename", str(motion_source_path))
    fallback_task.set_editor_property("destination_path", source_bundle_path)
    set_if_present(fallback_task, "destination_name", asset_name)
    fallback_task.set_editor_property("replace_existing", True)
    fallback_task.set_editor_property("replace_existing_settings", True)
    fallback_task.set_editor_property("automated", True)
    fallback_task.set_editor_property("save", True)
    fallback_task.set_editor_property("options", _build_source_bundle_import_options())
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([fallback_task])

    fallback_imported_paths = list(fallback_task.get_editor_property("imported_object_paths") or [])
    fallback_assets = {
        "animation_asset_path": "",
        "skeletal_mesh_asset_path": "",
        "skeleton_asset_path": "",
        "import_mode": "source_bundle_fallback",
    }
    for object_path in fallback_imported_paths:
        class_name = load_asset_class_name(object_path)
        canonical_path = _asset_path_from_object_path(object_path)
        if class_name in {"AnimSequence", "AnimationAsset"} and not fallback_assets["animation_asset_path"]:
            fallback_assets["animation_asset_path"] = canonical_path
        elif class_name == "SkeletalMesh" and not fallback_assets["skeletal_mesh_asset_path"]:
            fallback_assets["skeletal_mesh_asset_path"] = canonical_path
        elif class_name == "Skeleton" and not fallback_assets["skeleton_asset_path"]:
            fallback_assets["skeleton_asset_path"] = canonical_path
    if not fallback_assets["animation_asset_path"]:
        scanned_assets = _scan_imported_motion_assets(source_bundle_path)
        fallback_assets["animation_asset_path"] = scanned_assets["animation_asset_path"]
        fallback_assets["skeletal_mesh_asset_path"] = scanned_assets["skeletal_mesh_asset_path"]
        fallback_assets["skeleton_asset_path"] = scanned_assets["skeleton_asset_path"]
    if not fallback_assets["animation_asset_path"]:
        existing_assets = _resolve_existing_source_bundle_assets(source_bundle_path, asset_name)
        fallback_assets["animation_asset_path"] = existing_assets["animation_asset_path"]
        fallback_assets["skeletal_mesh_asset_path"] = (
            fallback_assets["skeletal_mesh_asset_path"] or existing_assets["skeletal_mesh_asset_path"]
        )
        fallback_assets["skeleton_asset_path"] = (
            fallback_assets["skeleton_asset_path"] or existing_assets["skeleton_asset_path"]
        )
    source_skeleton, resolved_assets = _load_source_bundle_skeleton(source_bundle_path, asset_name)
    fallback_assets["skeletal_mesh_asset_path"] = (
        fallback_assets["skeletal_mesh_asset_path"] or resolved_assets["skeletal_mesh_asset_path"]
    )
    fallback_assets["skeleton_asset_path"] = (
        fallback_assets["skeleton_asset_path"] or resolved_assets["skeleton_asset_path"]
    )
    if not fallback_assets["animation_asset_path"] and source_skeleton is not None:
        fallback_assets["animation_asset_path"] = _import_source_bundle_animation(
            motion_source_path,
            source_bundle_path,
            asset_name,
            source_skeleton,
        )
    if fallback_assets["animation_asset_path"]:
        warnings.append("target_skeleton_import_failed_falling_back_to_source_bundle")
        return fallback_assets, warnings
    return {
        "animation_asset_path": "",
        "skeletal_mesh_asset_path": "",
        "skeleton_asset_path": "",
        "import_mode": "failed",
    }, warnings


def import_motion_packet(request: dict) -> dict:
    warnings: list[str] = []
    manifest_path, manifest = _load_packet_manifest(request)
    errors = _supported_packet_errors(manifest)
    explicit_motion_source = str(request.get("motion_import_source_path") or "").strip()
    if explicit_motion_source:
        motion_source_path = Path(explicit_motion_source).expanduser().resolve()
    else:
        export_artifacts = manifest.get("export_artifacts") or {}
        motion_source_path = resolve_manifest_artifact(
            manifest_path,
            (export_artifacts.get("motion_fbx") or export_artifacts.get("motion_bvh") or "motion.bvh"),
        )
    if motion_source_path is None or not motion_source_path.exists():
        errors.append(f"motion_import_source_missing:{motion_source_path or 'missing'}")
    if errors:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": errors,
            "package_id": str(manifest.get("package_id") or ""),
            "sample_id": str(manifest.get("sample_id") or ""),
        }

    target_skeleton, target_skeleton_asset_path, target_host_asset_path, skeleton_warnings = _resolve_target_skeleton(request)
    warnings.extend(skeleton_warnings)
    if target_skeleton is None:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": ["target_skeleton_resolution_failed"],
            "package_id": str(manifest.get("package_id") or ""),
            "sample_id": str(manifest.get("sample_id") or ""),
            "packet_manifest_path": str(manifest_path),
            "motion_import_source_path": str(motion_source_path),
        }

    destination_path, asset_name = _resolve_import_destination(manifest, request)
    imported_assets, import_warnings = _import_motion_asset(
        motion_source_path,
        destination_path,
        asset_name,
        target_skeleton,
    )
    warnings.extend(import_warnings)
    imported_animation_asset_path = str(imported_assets.get("animation_asset_path") or "")
    if not imported_animation_asset_path:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": ["animation_import_failed"],
            "package_id": str(manifest.get("package_id") or ""),
            "sample_id": str(manifest.get("sample_id") or ""),
            "packet_manifest_path": str(manifest_path),
            "motion_import_source_path": str(motion_source_path),
            "target_skeleton_asset_path": target_skeleton_asset_path,
            "target_host_asset_path": target_host_asset_path,
        }

    return {
        "status": "pass",
        "warnings": warnings,
        "errors": [],
        "package_id": str(manifest.get("package_id") or ""),
        "sample_id": str(manifest.get("sample_id") or ""),
        "packet_manifest_path": str(manifest_path),
        "motion_import_source_path": str(motion_source_path),
        "imported_animation_asset_path": imported_animation_asset_path,
        "imported_assets": dict(imported_assets),
        "target_skeleton_asset_path": target_skeleton_asset_path,
        "target_host_asset_path": target_host_asset_path,
        "retarget_refs": {
            "target_skeleton_asset_path": target_skeleton_asset_path,
            "target_host_asset_path": target_host_asset_path,
        },
        "source_packet_refs": {
            "sample_id": str(manifest.get("sample_id") or ""),
            "package_id": str(manifest.get("package_id") or ""),
            "clip_id": str(manifest.get("clip_id") or ""),
            "pack_version": str(manifest.get("pack_version") or ""),
        },
    }
