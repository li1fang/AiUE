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
    if candidate.is_absolute():
        if candidate.exists():
            return candidate.resolve()
        local_candidate = candidate
    else:
        local_candidate = (manifest_path.parent / candidate)
        if local_candidate.exists():
            return local_candidate.resolve()
    local_sibling = manifest_path.parent / candidate.name
    if local_sibling.exists():
        return local_sibling.resolve()
    return local_candidate.resolve(strict=False)


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

def load_asset(object_path: str | None):
    if not object_path:
        return None
    return unreal.EditorAssetLibrary.load_asset(object_path)

def pair_id_for(character_package_id: str | None, weapon_package_id: str | None) -> str:
    return f"{character_package_id or 'character'}_{weapon_package_id or 'weapon'}"

def asset_name_from_path(asset_path: str) -> str:
    return asset_path.rstrip("/").split("/")[-1]


def path_for_loaded_asset(asset) -> str | None:
    if not asset:
        return None
    try:
        return unreal.EditorAssetLibrary.get_path_name_for_loaded_asset(asset)
    except Exception:
        return None


def object_path_from_asset_path(asset_path: str) -> str:
    asset_name = asset_name_from_path(asset_path)
    return f"{asset_path}.{asset_name}"


def asset_path_from_object_path(object_path: str | None) -> str:
    if not object_path:
        return ""
    return str(object_path).split(".", 1)[0]

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
            "NiagaraComponent",
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
        if class_name == "NiagaraComponent":
            for property_name in ("asset", "niagara_system_asset", "niagara_system"):
                try:
                    niagara_asset = component.get_editor_property(property_name)
                except Exception:
                    niagara_asset = None
                if niagara_asset:
                    record["asset_path"] = niagara_asset.get_path_name()
                    break
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


def reconcile_camera_plan_warning(subject_visibility: dict, warnings: list[str], actual_subject_visible: bool, line_clear: bool, capture_succeeded: bool) -> tuple[list[str], dict]:
    normalized_warnings = list(warnings or [])
    plan_visible = bool((subject_visibility or {}).get("visible"))
    warning_code = "subject_not_visible_in_camera_plan"
    warning_present = warning_code in normalized_warnings
    warning_reconciled = False
    if warning_present and capture_succeeded and actual_subject_visible and line_clear:
        normalized_warnings = [item for item in normalized_warnings if item != warning_code]
        warning_reconciled = True
    return normalized_warnings, {
        "plan_visible": plan_visible,
        "plan_reason": str((subject_visibility or {}).get("reason") or ""),
        "warning_code": warning_code,
        "warning_present": warning_present,
        "warning_reconciled": warning_reconciled,
        "warning_retained": warning_present and not warning_reconciled,
        "matches_post_capture": None if not capture_succeeded else bool(plan_visible == actual_subject_visible),
        "actual_subject_visible": bool(actual_subject_visible),
        "line_of_sight_clear": bool(line_clear),
        "capture_succeeded": bool(capture_succeeded),
    }


def build_shot_quality_payload(
    capture_result: dict,
    subject_coverage: dict,
    weapon_coverage: dict,
    line_of_sight: dict,
    subject_min_screen_coverage: float,
    weapon_min_screen_coverage: float,
) -> dict:
    shot_errors = list(capture_result.get("errors") or [])
    shot_warnings = list(capture_result.get("warnings") or [])
    subject_visible = bool(subject_coverage.get("coverage_ratio", 0.0) >= subject_min_screen_coverage)
    weapon_visible = bool(weapon_coverage.get("coverage_ratio", 0.0) >= weapon_min_screen_coverage)
    line_clear = bool(line_of_sight.get("clear"))
    capture_succeeded = bool(capture_result.get("output_exists"))
    shot_warnings, camera_plan_assessment = reconcile_camera_plan_warning(
        dict(capture_result.get("subject_visibility") or {}),
        shot_warnings,
        subject_visible,
        line_clear,
        capture_succeeded,
    )
    if not subject_visible:
        shot_errors.append("out_of_frame")
    if not line_clear:
        shot_errors.append("occluded")
    if not capture_succeeded:
        shot_errors.append("capture_failed")
    shot_status = "pass" if not shot_errors else "fail"
    return {
        "status": shot_status,
        "warnings": sorted(set(shot_warnings)),
        "errors": sorted(set(shot_errors)),
        "quality_gate": {
            "status": shot_status,
            "capture_succeeded": capture_succeeded,
            "subject_visible": subject_visible,
            "weapon_visible": weapon_visible,
            "line_of_sight_clear": line_clear,
            "subject_min_screen_coverage": float(subject_min_screen_coverage),
            "weapon_min_screen_coverage": float(weapon_min_screen_coverage),
        },
        "camera_plan_assessment": camera_plan_assessment,
    }


def component_asset_path(component) -> str:
    if not component:
        return ""
    for property_name in ("skeletal_mesh_asset", "skeletal_mesh", "static_mesh", "asset", "niagara_system_asset", "niagara_system"):
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
        "render_in_main_pass": None,
        "render_in_depth_pass": None,
        "component_name": str(getattr(component, "get_name", lambda: "")() or "") if component else "",
        "class_name": component_class_name(component) if component else "",
        "asset_path": component_asset_path(component),
    }
    if not component:
        return payload
    for property_name in ("visible", "hidden_in_game", "cast_shadow", "render_in_main_pass", "render_in_depth_pass"):
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


def bounds_payload_from_box(box, component_location, source: str) -> dict | None:
    if not box:
        return None
    min_vector = getattr(box, "min", None)
    max_vector = getattr(box, "max", None)
    if min_vector is None or max_vector is None:
        return None
    try:
        local_origin = unreal.Vector(
            (float(min_vector.x) + float(max_vector.x)) * 0.5,
            (float(min_vector.y) + float(max_vector.y)) * 0.5,
            (float(min_vector.z) + float(max_vector.z)) * 0.5,
        )
        local_extent = unreal.Vector(
            abs(float(max_vector.x) - float(min_vector.x)) * 0.5,
            abs(float(max_vector.y) - float(min_vector.y)) * 0.5,
            abs(float(max_vector.z) - float(min_vector.z)) * 0.5,
        )
        world_origin = unreal.Vector(
            float(component_location.x) + float(local_origin.x),
            float(component_location.y) + float(local_origin.y),
            float(component_location.z) + float(local_origin.z),
        )
        return bounds_payload_from_origin_extent(world_origin, local_extent, source)
    except Exception:
        return None


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
    for property_name in ("skeletal_mesh_asset", "skeletal_mesh", "static_mesh", "asset", "niagara_system_asset", "niagara_system"):
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
    component_location = component_world_location(component) or unreal.Vector(0.0, 0.0, 0.0)
    if (local_origin is None or local_extent is None) and component_class_name(component) == "NiagaraComponent":
        for method_name, source_name in (
            ("get_fixed_bounds", "niagara_fixed_bounds"),
            ("get_initial_streaming_bounds", "niagara_initial_streaming_bounds"),
        ):
            if not hasattr(asset, method_name):
                continue
            try:
                box_bounds = getattr(asset, method_name)()
            except Exception:
                box_bounds = None
            box_payload = bounds_payload_from_box(box_bounds, component_location, source_name)
            if box_payload and box_payload.get("non_zero"):
                return box_payload
        for property_name, source_name in (
            ("fixed_bounds", "niagara_fixed_bounds_property"),
            ("initial_streaming_bounds", "niagara_initial_streaming_bounds_property"),
        ):
            try:
                box_bounds = asset.get_editor_property(property_name)
            except Exception:
                box_bounds = None
            box_payload = bounds_payload_from_box(box_bounds, component_location, source_name)
            if box_payload and box_payload.get("non_zero"):
                return box_payload
    if local_origin is None or local_extent is None:
        return {
            "origin": {},
            "extent": {},
            "diagonal_length": 0.0,
            "non_zero": False,
            "source": "asset_bounds_unavailable",
        }
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


def niagara_capture_warmup_payload(result) -> dict:
    payload = {
        "success": False,
        "components_requested": 0,
        "components_discovered": 0,
        "components_warmed": 0,
        "world_flushed": False,
        "applied_methods": [],
        "warnings": [],
        "errors": [],
        "entries": [],
    }
    if not result:
        return payload

    entries = []
    for entry in list(getattr(result, "entries", []) or []):
        entries.append(
            {
                "slot_name": slot_name_text(getattr(entry, "slot_name", None), default=""),
                "component_name": str(getattr(entry, "component_name", "") or ""),
                "asset_path": str(getattr(entry, "asset_path", "") or ""),
                "success": bool(getattr(entry, "success", False)),
                "desired_age_seconds": float(getattr(entry, "desired_age_seconds", 0.0) or 0.0),
                "seek_delta_seconds": float(getattr(entry, "seek_delta_seconds", 0.0) or 0.0),
                "advance_step_count": int(getattr(entry, "advance_step_count", 0) or 0),
                "advance_step_delta_seconds": float(getattr(entry, "advance_step_delta_seconds", 0.0) or 0.0),
                "applied_methods": list(getattr(entry, "applied_methods", []) or []),
                "warnings": list(getattr(entry, "warnings", []) or []),
                "errors": list(getattr(entry, "errors", []) or []),
            }
        )

    payload.update(
        {
            "success": bool(getattr(result, "success", False)),
            "components_requested": int(getattr(result, "components_requested", 0) or 0),
            "components_discovered": int(getattr(result, "components_discovered", 0) or 0),
            "components_warmed": int(getattr(result, "components_warmed", 0) or 0),
            "world_flushed": bool(getattr(result, "world_flushed", False)),
            "applied_methods": list(getattr(result, "applied_methods", []) or []),
            "warnings": list(getattr(result, "warnings", []) or []),
            "errors": list(getattr(result, "errors", []) or []),
            "entries": entries,
        }
    )
    return payload


def loaded_asset_path(asset) -> str:
    if not asset:
        return ""
    try:
        return str(asset.get_path_name() or "")
    except Exception:
        return ""


def slot_name_text(value, default: str = "weapon") -> str:
    text = str(value or "").strip()
    return text or default


def normalized_item_kind_text(item_kind: str | None, skeletal_mesh=None, static_mesh=None, niagara_system=None) -> str:
    lower = str(item_kind or "").strip().lower()
    if niagara_system:
        return "niagara_system"
    if static_mesh:
        return "static_mesh"
    if skeletal_mesh:
        return "skeletal_mesh"
    if lower in {"niagara_system", "niagara", "fx"}:
        return "niagara_system"
    if lower in {"static_mesh", "static"}:
        return "static_mesh"
    if lower in {"skeletal_mesh", "skeletal", "skeletalmesh"}:
        return "skeletal_mesh"
    return "skeletal_mesh"


def runtime_slot_binding_entries_from_request(bindings: list[dict]) -> list:
    entries = []
    for binding in bindings:
        entry = unreal.PMXEquipmentSlotBindingEntry()
        set_if_present(entry, "slot_name", binding.get("slot_name") or "weapon")
        set_if_present(entry, "item_package_id", str(binding.get("item_package_id") or ""))
        set_if_present(entry, "item_kind", str(binding.get("item_kind") or "skeletal_mesh"))
        set_if_present(entry, "attach_socket_name", binding.get("attach_socket_name") or "WeaponSocket")
        set_if_present(entry, "skeletal_mesh", load_asset(binding.get("skeletal_mesh_asset")))
        set_if_present(entry, "static_mesh", load_asset(binding.get("static_mesh_asset")))
        set_if_present(entry, "niagara_system", load_asset(binding.get("niagara_system_asset")))
        set_if_present(entry, "b_consumer_ready", bool(binding.get("consumer_ready")))
        set_if_present(entry, "consumer_ready", bool(binding.get("consumer_ready")))
        entries.append(entry)
    return entries


def slot_binding_payload(binding) -> dict:
    if not binding:
        return {
            "slot_name": "weapon",
            "item_package_id": "",
            "item_kind": "skeletal_mesh",
            "attach_socket_name": "WeaponSocket",
            "skeletal_mesh_asset": "",
            "static_mesh_asset": "",
            "niagara_system_asset": "",
            "asset_path": "",
            "consumer_ready": False,
        }
    skeletal_mesh = getattr(binding, "skeletal_mesh", None)
    static_mesh = getattr(binding, "static_mesh", None)
    niagara_system = getattr(binding, "niagara_system", None)
    payload = {
        "slot_name": slot_name_text(getattr(binding, "slot_name", None)),
        "item_package_id": str(getattr(binding, "item_package_id", "") or ""),
        "item_kind": normalized_item_kind_text(
            getattr(binding, "item_kind", ""),
            skeletal_mesh=skeletal_mesh,
            static_mesh=static_mesh,
            niagara_system=niagara_system,
        ),
        "attach_socket_name": str(getattr(binding, "attach_socket_name", "") or "WeaponSocket"),
        "skeletal_mesh_asset": loaded_asset_path(skeletal_mesh),
        "static_mesh_asset": loaded_asset_path(static_mesh),
        "niagara_system_asset": loaded_asset_path(niagara_system),
        "consumer_ready": bool(getattr(binding, "b_consumer_ready", getattr(binding, "consumer_ready", False))),
    }
    payload["asset_path"] = payload["niagara_system_asset"] or payload["static_mesh_asset"] or payload["skeletal_mesh_asset"]
    return payload


def legacy_weapon_slot_binding_payload(pmx_component) -> dict | None:
    if not pmx_component:
        return None
    try:
        desired_weapon_mesh = pmx_component.get_desired_weapon_mesh()
    except Exception:
        desired_weapon_mesh = None
    if not desired_weapon_mesh:
        return None
    attach_socket_name = ""
    if hasattr(pmx_component, "get_attach_socket_name"):
        try:
            attach_socket_name = str(pmx_component.get_attach_socket_name() or "WeaponSocket")
        except Exception:
            attach_socket_name = "WeaponSocket"
    return {
        "slot_name": "weapon",
        "item_package_id": "",
        "item_kind": "skeletal_mesh",
        "attach_socket_name": attach_socket_name or "WeaponSocket",
        "skeletal_mesh_asset": loaded_asset_path(desired_weapon_mesh),
        "static_mesh_asset": "",
        "niagara_system_asset": "",
        "asset_path": loaded_asset_path(desired_weapon_mesh),
        "consumer_ready": bool(desired_weapon_mesh),
    }


def pmx_slot_bindings_payload(pmx_component) -> list[dict]:
    bindings = []
    if pmx_component and hasattr(pmx_component, "get_desired_slot_bindings"):
        try:
            bindings = [slot_binding_payload(binding) for binding in list(pmx_component.get_desired_slot_bindings() or [])]
        except Exception:
            bindings = []
    if bindings:
        return bindings
    legacy = legacy_weapon_slot_binding_payload(pmx_component)
    return [legacy] if legacy else []


def slot_conflict_payload(conflict) -> dict:
    if not conflict:
        return {
            "slot_name": "",
            "resolution": "override_latest",
            "previous_item_package_id": "",
            "incoming_item_package_id": "",
            "previous_item_kind": "",
            "incoming_item_kind": "",
            "previous_attach_socket_name": "",
            "incoming_attach_socket_name": "",
        }
    return {
        "slot_name": slot_name_text(getattr(conflict, "slot_name", None), default=""),
        "resolution": str(getattr(conflict, "resolution", "") or "override_latest"),
        "previous_item_package_id": str(getattr(conflict, "previous_item_package_id", "") or ""),
        "incoming_item_package_id": str(getattr(conflict, "incoming_item_package_id", "") or ""),
        "previous_item_kind": str(getattr(conflict, "previous_item_kind", "") or ""),
        "incoming_item_kind": str(getattr(conflict, "incoming_item_kind", "") or ""),
        "previous_attach_socket_name": str(getattr(conflict, "previous_attach_socket_name", "") or ""),
        "incoming_attach_socket_name": str(getattr(conflict, "incoming_attach_socket_name", "") or ""),
    }


def pmx_slot_conflicts_payload(pmx_component) -> list[dict]:
    if not pmx_component or not hasattr(pmx_component, "get_slot_conflicts"):
        return []
    try:
        return [slot_conflict_payload(conflict) for conflict in list(pmx_component.get_slot_conflicts() or [])]
    except Exception:
        return []


def slot_attach_state_payload(state) -> dict:
    if not state:
        return {
            "slot_name": "",
            "item_package_id": "",
            "item_kind": "",
            "requested_attach_socket_name": "",
            "resolved_attach_socket_name": "",
            "resolved_attach_socket_exists": None,
            "attach_resolution_mode": "",
            "managed_component_name": "",
            "managed_component_class": "",
            "managed_component_asset_path": "",
        }
    return {
        "slot_name": slot_name_text(getattr(state, "slot_name", None), default=""),
        "item_package_id": str(getattr(state, "item_package_id", "") or ""),
        "item_kind": str(getattr(state, "item_kind", "") or ""),
        "requested_attach_socket_name": str(getattr(state, "requested_attach_socket_name", "") or ""),
        "resolved_attach_socket_name": str(getattr(state, "resolved_attach_socket_name", "") or ""),
        "resolved_attach_socket_exists": bool(getattr(state, "b_resolved_attach_socket_exists", getattr(state, "resolved_attach_socket_exists", False))),
        "attach_resolution_mode": str(getattr(state, "attach_resolution_mode", "") or ""),
        "managed_component_name": str(getattr(state, "managed_component_name", "") or ""),
        "managed_component_class": str(getattr(state, "managed_component_class", "") or ""),
        "managed_component_asset_path": str(getattr(state, "managed_component_asset_path", "") or ""),
    }


def pmx_slot_attach_states_payload(pmx_component) -> list[dict]:
    if not pmx_component or not hasattr(pmx_component, "get_resolved_slot_attach_states"):
        return []
    try:
        return [slot_attach_state_payload(state) for state in list(pmx_component.get_resolved_slot_attach_states() or [])]
    except Exception:
        return []


def find_component_by_name(actor, component_name: str):
    if not actor or not component_name:
        return None
    for component_class in (
        getattr(unreal, "SkeletalMeshComponent", None),
        getattr(unreal, "StaticMeshComponent", None),
        getattr(unreal, "NiagaraComponent", None),
    ):
        if component_class is None:
            continue
        try:
            components = list(actor.get_components_by_class(component_class) or [])
        except Exception:
            components = []
        for component in components:
            try:
                if component.get_name() == component_name:
                    return component
            except Exception:
                continue
    return None


def actor_managed_component_for_slot(actor, slot_name: str, primary_component=None):
    if not actor:
        return None
    try:
        pmx_component = actor.get_component_by_class(unreal.PMXCharacterEquipmentComponent)
    except Exception:
        pmx_component = None
    if pmx_component and hasattr(pmx_component, "get_managed_component_for_slot"):
        try:
            managed = pmx_component.get_managed_component_for_slot(to_name(slot_name_text(slot_name)))
            if managed:
                return managed
        except Exception:
            pass
    if slot_name_text(slot_name) == "weapon" and pmx_component and hasattr(pmx_component, "get_managed_weapon_mesh_component"):
        try:
            managed = pmx_component.get_managed_weapon_mesh_component()
            if managed:
                return managed
        except Exception:
            pass
    for attach_state in pmx_slot_attach_states_payload(pmx_component):
        if attach_state.get("slot_name") == slot_name_text(slot_name):
            component = find_component_by_name(actor, attach_state.get("managed_component_name") or "")
            if component:
                return component
    return None


def actor_managed_components_by_slot(actor, pmx_component=None, primary_component=None) -> dict:
    slot_names = []
    if pmx_component:
        slot_names.extend(binding.get("slot_name") for binding in pmx_slot_bindings_payload(pmx_component))
        slot_names.extend(state.get("slot_name") for state in pmx_slot_attach_states_payload(pmx_component))
    normalized_slot_names = [slot_name_text(name) for name in slot_names if name]
    payload = {}
    for slot_name in sorted(set(normalized_slot_names)):
        component = actor_managed_component_for_slot(actor, slot_name, primary_component=primary_component)
        payload[slot_name] = {
            **component_visibility_record(component),
            "bounds": component_bounds_payload(component),
            "attach": component_attach_payload(component),
            "transform": component_transform_payload(component),
        }
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
    slot_bindings = pmx_slot_bindings_payload(pmx_component)
    slot_conflicts = pmx_slot_conflicts_payload(pmx_component)
    slot_attach_states = pmx_slot_attach_states_payload(pmx_component)
    weapon_slot_binding = next((entry for entry in slot_bindings if entry.get("slot_name") == "weapon"), None)
    weapon_attach_state = next((entry for entry in slot_attach_states if entry.get("slot_name") == "weapon"), None)
    payload = {
        "component_name": str(getattr(pmx_component, "get_name", lambda: "")() or "") if pmx_component else "",
        "component_class": component_class_name(pmx_component) if pmx_component else "",
        "desired_weapon_mesh_asset": (weapon_slot_binding or {}).get("skeletal_mesh_asset") or "",
        "requested_attach_socket_name": (weapon_attach_state or {}).get("requested_attach_socket_name") or (weapon_slot_binding or {}).get("attach_socket_name") or "",
        "resolved_attach_socket_name": (weapon_attach_state or {}).get("resolved_attach_socket_name") or "",
        "resolved_attach_socket_exists": (weapon_attach_state or {}).get("resolved_attach_socket_exists"),
        "attach_resolution_mode": (weapon_attach_state or {}).get("attach_resolution_mode") or "",
        "owner_socket_exists_for_requested_name": None,
        "owner_interesting_attach_targets": interesting_attach_targets(owner_mesh),
        "slot_bindings": slot_bindings,
        "slot_attach_state": slot_attach_states,
        "slot_conflicts": slot_conflicts,
    }
    if not pmx_component:
        return payload
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
    if weapon_slot_binding and not payload["desired_weapon_mesh_asset"]:
        payload["desired_weapon_mesh_asset"] = weapon_slot_binding.get("skeletal_mesh_asset") or weapon_slot_binding.get("asset_path") or ""
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
    component = actor_managed_component_for_slot(actor, "weapon", primary_component=primary_component)
    if component:
        return component
    if not actor:
        return None
    try:
        skeletal_components = list(actor.get_components_by_class(unreal.SkeletalMeshComponent) or [])
    except Exception:
        skeletal_components = []
    for component in skeletal_components:
        if primary_component and component == primary_component:
            continue
        if component_asset_path(component):
            return component
    try:
        static_components = list(actor.get_components_by_class(unreal.StaticMeshComponent) or [])
    except Exception:
        static_components = []
    for component in static_components:
        if component_asset_path(component):
            return component
    return skeletal_components[1] if len(skeletal_components) > 1 else None


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
    task_done_once = False
    while time.time() < deadline:
        candidate = find_screenshot_output_path(desired_output_path)
        task_done = bool(task and task.is_valid_task() and task.is_task_done()) if task else False
        task_done_once = task_done_once or task_done
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
        time.sleep(poll_interval_seconds)
    final_candidate = find_screenshot_output_path(desired_output_path)
    final_task_done = bool(task and task.is_valid_task() and task.is_task_done()) if task else False
    return final_candidate, task_done_once or final_task_done


def apply_scene_capture_show_flags(component, capture_profile: str | None = None) -> list[str]:
    warnings = []
    profile_name = str(capture_profile or "").strip().lower()
    if profile_name == "qa_mask_skeletal_only":
        flag_specs = [
            ("Materials", True),
            ("Lighting", False),
            ("PostProcessing", False),
            ("Atmosphere", False),
            ("Fog", False),
            ("Bloom", False),
            ("AntiAliasing", False),
            ("Translucency", True),
            ("TranslucentLighting", False),
            ("Particles", False),
            ("Niagara", False),
            ("StaticMeshes", False),
            ("Landscape", False),
            ("BSP", False),
            ("InstancedStaticMeshes", False),
            ("SkeletalMeshes", True),
        ]
    else:
        flag_specs = [
            ("Particles", True),
            ("Niagara", True),
            ("Translucency", True),
            ("TranslucentLighting", True),
            ("Lighting", True),
            ("Materials", True),
            ("PostProcessing", True),
        ]
    settings = []
    for flag_name, enabled in flag_specs:
        try:
            setting = unreal.EngineShowFlagsSetting()
            setting.set_editor_property("show_flag_name", str(flag_name))
            setting.set_editor_property("enabled", bool(enabled))
            settings.append(setting)
        except Exception as exc:
            warnings.append(f"scene_capture_show_flag_build_failed:{flag_name}:{exc}")
    if not settings:
        return warnings
    try:
        if hasattr(component, "set_show_flag_settings"):
            component.set_show_flag_settings(settings)
        else:
            component.set_editor_property("show_flag_settings", settings)
    except Exception as exc:
        warnings.append(f"scene_capture_show_flags_apply_failed:{exc}")
    return warnings


def apply_scene_capture_component_filters(component, show_only_components: list | None = None) -> list[str]:
    warnings = []
    filtered_components = [item for item in list(show_only_components or []) if item]
    try:
        if hasattr(component, "clear_hidden_components"):
            component.clear_hidden_components()
    except Exception as exc:
        warnings.append(f"scene_capture_clear_hidden_components_failed:{exc}")
    try:
        if hasattr(component, "clear_show_only_components"):
            component.clear_show_only_components()
    except Exception as exc:
        warnings.append(f"scene_capture_clear_show_only_components_failed:{exc}")
    try:
        if hasattr(unreal, "SceneCapturePrimitiveRenderMode"):
            if filtered_components:
                component.set_editor_property(
                    "primitive_render_mode",
                    unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST,
                )
            else:
                component.set_editor_property(
                    "primitive_render_mode",
                    unreal.SceneCapturePrimitiveRenderMode.PRM_RENDER_SCENE_PRIMITIVES,
                )
    except Exception as exc:
        warnings.append(f"scene_capture_primitive_render_mode_failed:{exc}")
    filtered_component_keys = {
        str(getattr(item, "get_path_name", lambda: "")() or "") or str(id(item))
        for item in filtered_components
    }
    owner_components_map = {}
    for filtered_component in filtered_components:
        try:
            owner = filtered_component.get_owner()
        except Exception:
            owner = None
        if not owner:
            continue
        owner_key = str(getattr(owner, "get_path_name", lambda: "")() or "") or str(id(owner))
        if owner_key in owner_components_map:
            continue
        owner_components = []
        for component_class in (getattr(unreal, "SkeletalMeshComponent", None), getattr(unreal, "StaticMeshComponent", None)):
            if component_class is None:
                continue
            try:
                owner_components.extend(list(owner.get_components_by_class(component_class) or []))
            except Exception:
                continue
        owner_components_map[owner_key] = {"owner": owner, "components": owner_components}
        try:
            component.show_only_actor_components(owner)
        except Exception as exc:
            warnings.append(f"scene_capture_show_only_actor_components_failed:{owner_key}:{exc}")
    for owner_entry in owner_components_map.values():
        for owner_component in list(owner_entry.get("components") or []):
            owner_component_key = str(getattr(owner_component, "get_path_name", lambda: "")() or "") or str(id(owner_component))
            if owner_component_key in filtered_component_keys:
                continue
            try:
                component.remove_show_only_component(owner_component)
            except Exception:
                continue
    for filtered_component in filtered_components:
        try:
            component.show_only_component(filtered_component)
        except Exception as exc:
            warnings.append(f"scene_capture_show_only_component_failed:{component_class_name(filtered_component)}:{exc}")
    return warnings


def available_scene_capture_source_names() -> list[str]:
    try:
        return sorted([name for name in dir(unreal.SceneCaptureSource) if str(name).startswith("SCS_")])
    except Exception:
        return []


def resolve_scene_capture_source(scene_capture_source_name: str | None, capture_hdr: bool) -> tuple[object, str, list[str]]:
    warnings = []
    requested_name = str(scene_capture_source_name or "").strip()
    available_names = available_scene_capture_source_names()
    default_candidates = [
        "SCS_FINAL_TONE_CURVE_HDR",
        "SCS_FINAL_COLOR_HDR",
        "SCS_FINAL_COLOR_LDR",
        "SCS_SCENE_COLOR_HDR",
        "SCS_SCENE_COLOR_HDR_NO_ALPHA",
    ] if capture_hdr else [
        "SCS_FINAL_COLOR_LDR",
        "SCS_FINAL_COLOR_HDR",
        "SCS_FINAL_TONE_CURVE_HDR",
        "SCS_SCENE_COLOR_HDR",
        "SCS_SCENE_COLOR_HDR_NO_ALPHA",
    ]

    if requested_name:
        candidate_names = [requested_name]
    else:
        candidate_names = default_candidates

    for candidate_name in candidate_names:
        if hasattr(unreal.SceneCaptureSource, candidate_name):
            return getattr(unreal.SceneCaptureSource, candidate_name), candidate_name, warnings

    fallback_name = "SCS_FINAL_COLOR_HDR" if capture_hdr and hasattr(unreal.SceneCaptureSource, "SCS_FINAL_COLOR_HDR") else "SCS_FINAL_COLOR_LDR"
    if not hasattr(unreal.SceneCaptureSource, fallback_name):
        for candidate_name in available_names:
            if hasattr(unreal.SceneCaptureSource, candidate_name):
                fallback_name = candidate_name
                break
    if requested_name:
        warnings.append(
            "scene_capture_source_unavailable:"
            + requested_name
            + (f":available={','.join(available_names)}" if available_names else "")
        )
    return getattr(unreal.SceneCaptureSource, fallback_name), fallback_name, warnings


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
    scene_capture_source_name: str | None = None,
    scene_capture_warmup_count: int = 2,
    scene_capture_warmup_delay_seconds: float = 0.05,
    capture_profile: str | None = None,
    show_only_components: list | None = None,
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
        resolved_capture_source, resolved_capture_source_name, source_warnings = resolve_scene_capture_source(scene_capture_source_name, capture_hdr)
        warnings.extend(source_warnings)
        component.set_editor_property("capture_source", resolved_capture_source)
        component.set_editor_property("capture_every_frame", False)
        component.set_editor_property("capture_on_movement", False)
        set_if_present(component, "always_persist_rendering_state", True)
        warnings.extend(apply_scene_capture_show_flags(component, capture_profile=capture_profile))
        warnings.extend(apply_scene_capture_component_filters(component, show_only_components=show_only_components))
        if hasattr(component, "fov_angle") and hasattr(capture_camera, "get_camera_component"):
            try:
                camera_component = capture_camera.get_camera_component()
                fov_angle = camera_component.get_editor_property("field_of_view")
                component.set_editor_property("fov_angle", float(fov_angle))
            except Exception:
                pass
        warmup_count = max(int(scene_capture_warmup_count or 0), 1)
        warmup_delay_seconds = max(float(scene_capture_warmup_delay_seconds or 0.0), 0.01)
        time.sleep(max(delay_seconds, 0.05))
        for warmup_index in range(warmup_count):
            component.capture_scene()
            try:
                world.send_all_end_of_frame_updates()
            except Exception:
                pass
            if warmup_index + 1 < warmup_count:
                time.sleep(warmup_delay_seconds)
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
            "scene_capture_source": resolved_capture_source_name,
            "scene_capture_warmup_count": warmup_count,
            "capture_profile": str(capture_profile or ""),
        }
    except Exception as exc:
        return {
            "output_exists": False,
            "warnings": warnings,
            "errors": [f"render_target_capture_failed:{exc}"],
            "capture_profile": str(capture_profile or ""),
        }
    finally:
        if scene_capture_actor:
            try:
                actor_subsystem.destroy_actor(scene_capture_actor)
            except Exception:
                pass

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



