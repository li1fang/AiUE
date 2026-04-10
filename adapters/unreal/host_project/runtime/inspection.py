from __future__ import annotations

from .common import *
from .capture import *
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
            shot_quality = build_shot_quality_payload(
                capture_result,
                subject_coverage,
                weapon_coverage,
                line_of_sight,
                subject_min_screen_coverage,
                weapon_min_screen_coverage,
            )
            subject_pass_count += int(
                bool((shot_quality.get("quality_gate") or {}).get("subject_visible"))
                and bool((shot_quality.get("quality_gate") or {}).get("line_of_sight_clear"))
                and bool((shot_quality.get("quality_gate") or {}).get("capture_succeeded"))
            )
            weapon_pass_count += int(bool((shot_quality.get("quality_gate") or {}).get("weapon_visible")))
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
                    "line_of_sight_clear": bool((shot_quality.get("quality_gate") or {}).get("line_of_sight_clear")),
                    "line_of_sight": line_of_sight,
                    "subject_coverage": subject_coverage,
                    "weapon_coverage": weapon_coverage,
                    "status": shot_quality["status"],
                    "warnings": shot_quality["warnings"],
                    "errors": shot_quality["errors"],
                    "quality_gate": shot_quality["quality_gate"],
                    "camera_plan_assessment": shot_quality["camera_plan_assessment"],
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


