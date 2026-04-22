from __future__ import annotations

from pathlib import Path

from .common import *
from .composition_import_assets import enrich_related_assets, import_skeletal_mesh
from .inspection_visual_shots import capture_visual_shot_set
from .inspection_visual_state import component_material_evidence


def _resolve_imported_skeletal_mesh(imported_assets: dict, mesh_destination: str):
    candidate_paths = []
    skeletal_mesh_path = str(imported_assets.get("skeletal_mesh") or "")
    if skeletal_mesh_path:
        candidate_paths.append(skeletal_mesh_path)
    candidate_paths.extend(str(path) for path in list(imported_assets.get("other") or []))

    try:
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        for asset_data in list(registry.get_assets_by_path(to_name(mesh_destination), recursive=True)):
            if asset_class_name(asset_data) == "SkeletalMesh":
                candidate_paths.append(asset_object_path(asset_data))
    except Exception:
        pass

    resolved_candidates = []
    seen = set()
    for candidate in candidate_paths:
        normalized = str(candidate or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        asset = load_asset(normalized)
        if asset:
            resolved_candidates.append((normalized, asset))
            continue
        fallback_object_path = ""
        if "." in normalized:
            fallback_object_path = object_path_from_asset_path(asset_path_from_object_path(normalized))
        else:
            fallback_object_path = object_path_from_asset_path(normalized)
        asset = load_asset(fallback_object_path)
        if asset:
            resolved_candidates.append((path_for_loaded_asset(asset) or fallback_object_path, asset))
            continue

    def _diagonal_length(asset) -> float:
        for property_name in ("extended_bounds", "imported_bounds", "bounds"):
            try:
                bounds_value = asset.get_editor_property(property_name)
            except Exception:
                bounds_value = None
            if bounds_value and hasattr(bounds_value, "box_extent"):
                extent = bounds_value.box_extent
                return float(math.sqrt((extent.x * extent.x) + (extent.y * extent.y) + (extent.z * extent.z)))
        if hasattr(asset, "get_bounds"):
            try:
                bounds_value = asset.get_bounds()
            except Exception:
                bounds_value = None
            if bounds_value and hasattr(bounds_value, "box_extent"):
                extent = bounds_value.box_extent
                return float(math.sqrt((extent.x * extent.x) + (extent.y * extent.y) + (extent.z * extent.z)))
        return 0.0

    if resolved_candidates:
        resolved_candidates.sort(key=lambda entry: _diagonal_length(entry[1]), reverse=True)
        return resolved_candidates[0]
    return "", None


def _align_preview_mesh_to_actor(primary_mesh, actor) -> dict:
    actor_location = actor.get_actor_location() if actor else unreal.Vector(0.0, 0.0, 0.0)
    before_bounds = component_bounds_payload(primary_mesh, fallback_actor=actor)
    if not before_bounds.get("non_zero"):
        return {
            "applied": False,
            "reason": "bounds_unavailable",
            "before_bounds": before_bounds,
            "after_bounds": before_bounds,
            "world_delta": serialize_vector(unreal.Vector(0.0, 0.0, 0.0)),
        }
    origin = vector_from_request(before_bounds.get("origin"), actor_location)
    extent = vector_from_request(before_bounds.get("extent"), unreal.Vector(0.0, 0.0, 0.0))
    desired_origin = unreal.Vector(float(actor_location.x), float(actor_location.y), float(origin.z))
    desired_bottom_z = float(actor_location.z)
    current_bottom_z = float(origin.z) - float(extent.z)
    world_delta = unreal.Vector(
        float(desired_origin.x) - float(origin.x),
        float(desired_origin.y) - float(origin.y),
        float(desired_bottom_z) - float(current_bottom_z),
    )
    applied = False
    if world_delta.length() > 0.01:
        if hasattr(primary_mesh, "get_world_location") and hasattr(primary_mesh, "set_world_location"):
            try:
                current_location = primary_mesh.get_world_location()
                target_location = unreal.Vector(
                    float(current_location.x) + float(world_delta.x),
                    float(current_location.y) + float(world_delta.y),
                    float(current_location.z) + float(world_delta.z),
                )
                primary_mesh.set_world_location(target_location, False, False)
                applied = True
            except Exception:
                applied = False
        if not applied and hasattr(primary_mesh, "get_relative_location") and hasattr(primary_mesh, "set_relative_location"):
            try:
                current_location = primary_mesh.get_relative_location()
                target_location = unreal.Vector(
                    float(current_location.x) + float(world_delta.x),
                    float(current_location.y) + float(world_delta.y),
                    float(current_location.z) + float(world_delta.z),
                )
                primary_mesh.set_relative_location(target_location, False, False)
                applied = True
            except Exception:
                applied = False
    after_bounds = component_bounds_payload(primary_mesh, fallback_actor=actor)
    return {
        "applied": applied,
        "reason": "aligned_to_actor_origin_and_floor" if applied else "no_alignment_needed",
        "before_bounds": before_bounds,
        "after_bounds": after_bounds,
        "world_delta": serialize_vector(world_delta),
    }


def inspect_source_handoff_mesh_visual(request: dict) -> dict:
    mesh_source_path = Path(str(request.get("mesh_source_path") or "")).expanduser().resolve()
    if not mesh_source_path.exists():
        return {
            "status": "fail",
            "warnings": [],
            "errors": [f"mesh_source_missing:{mesh_source_path}"],
        }
    if mesh_source_path.suffix.lower() != ".fbx":
        return {
            "status": "fail",
            "warnings": [],
            "errors": [f"mesh_source_unsupported_format:{mesh_source_path.suffix.lower()}"],
        }

    asset_root = str(request.get("asset_root") or "/Game/PMXPipeline/BaseMeshTrial/BM1Smoke")
    item_token = sanitize_segment(
        str(request.get("fixture_id") or request.get("package_id") or request.get("item_id") or mesh_source_path.stem)
    )
    mesh_destination = f"{asset_root.rstrip('/')}/{item_token}"
    output_root = Path(
        request.get("output_root")
        or (Path(unreal.Paths.project_saved_dir()) / "pmx_pipeline" / "base_mesh_ue_smoke")
    ).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    imported_assets = import_skeletal_mesh(mesh_source_path, mesh_destination, create_physics_asset=False)
    imported_assets = enrich_related_assets(imported_assets, mesh_destination, mesh_source_path.stem)
    skeletal_mesh_asset_path = str(imported_assets.get("skeletal_mesh") or "")
    if not skeletal_mesh_asset_path:
        return {
            "status": "fail",
            "warnings": [],
            "errors": ["skeletal_mesh_missing_after_import"],
            "imported_assets": imported_assets,
            "asset_destination": mesh_destination,
        }

    skeletal_mesh_asset_path, skeletal_mesh_asset = _resolve_imported_skeletal_mesh(imported_assets, mesh_destination)
    if not skeletal_mesh_asset:
        return {
            "status": "fail",
            "warnings": [],
            "errors": [f"skeletal_mesh_load_failed:{skeletal_mesh_asset_path}"],
            "imported_assets": imported_assets,
            "asset_destination": mesh_destination,
        }

    actor_subsystem = editor_actor_subsystem()
    spawn_location = vector_from_request(request.get("cell_origin"), unreal.Vector(0.0, 0.0, 30000.0))
    spawn_rotation = rotator_from_request(request.get("cell_rotation"), make_rotator(0.0, 180.0, 0.0))
    actor = actor_subsystem.spawn_actor_from_class(unreal.Character.static_class(), spawn_location, spawn_rotation, True)
    if not actor:
        return {
            "status": "fail",
            "warnings": [],
            "errors": ["failed_to_spawn_preview_character"],
            "imported_assets": imported_assets,
            "asset_destination": mesh_destination,
        }

    actor.set_actor_label(str(request.get("actor_label") or f"AIUE_BaseMeshSmoke_{item_token}"))
    try:
        primary_mesh = actor.get_editor_property("mesh") if hasattr(actor, "get_editor_property") else None
        if not primary_mesh:
            return {
                "status": "fail",
                "warnings": [],
                "errors": ["preview_character_mesh_component_missing"],
                "imported_assets": imported_assets,
                "asset_destination": mesh_destination,
            }
        primary_mesh.set_skeletal_mesh(skeletal_mesh_asset)
        bounds_after_assign = component_bounds_payload(primary_mesh, fallback_actor=actor)
        height = float(((bounds_after_assign.get("extent") or {}).get("z") or 0.0)) * 2.0
        if height > 0.01:
            target_height = max(float(request.get("target_height_units") or 180.0), 10.0)
            scale_factor = target_height / height
            primary_mesh.set_world_scale3d(unreal.Vector(scale_factor, scale_factor, scale_factor))
        alignment = _align_preview_mesh_to_actor(primary_mesh, actor)
        time.sleep(max(float(request.get("settle_delay_seconds") or 0.2), 0.05))

        bounds = component_bounds_payload(primary_mesh, fallback_actor=actor)
        transform = component_transform_payload(primary_mesh)
        main_mesh_component = component_visibility_record(primary_mesh)
        material_evidence = component_material_evidence(primary_mesh)
        failed_requirements = []
        if not main_mesh_component.get("component_name"):
            failed_requirements.append("mesh_component_missing")
        if not bounds.get("non_zero"):
            failed_requirements.append("bounds_invalid")
        if int(material_evidence.get("material_slot_count") or 0) <= 0 and not list(material_evidence.get("material_slot_names") or []):
            failed_requirements.append("material_evidence_missing")

        shot_result = capture_visual_shot_set(
            spawned_host=actor,
            request={
                **request,
                "require_weapon_visible": False,
            },
            output_root=output_root,
            primary_mesh=primary_mesh,
            weapon_mesh=None,
        )
        failed_requirements.extend(list(shot_result.get("failed_requirements") or []))
        failed_requirements = sorted(set(str(item) for item in failed_requirements if str(item)))
        return {
            "status": "pass" if not failed_requirements else "fail",
            "fixture_id": str(request.get("fixture_id") or ""),
            "package_id": str(request.get("package_id") or ""),
            "item_id": str(request.get("item_id") or ""),
            "asset_destination": mesh_destination,
            "mesh_source_path": str(mesh_source_path),
            "imported_assets": imported_assets,
            "character_mesh_asset": skeletal_mesh_asset_path,
            "main_mesh_component": main_mesh_component,
            "main_mesh_bounds": bounds,
            "main_mesh_world_transform": transform,
            "preview_alignment": alignment,
            "material_evidence": material_evidence,
            "shots": list(shot_result.get("shots") or []),
            "failed_requirements": failed_requirements,
            "warnings": [],
            "errors": [] if not failed_requirements else failed_requirements,
        }
    finally:
        try:
            actor_subsystem.destroy_actor(actor)
        except Exception:
            pass


__all__ = ["inspect_source_handoff_mesh_visual"]
