from __future__ import annotations

from .common import *
from .retarget_profile import *

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





