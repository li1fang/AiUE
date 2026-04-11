from __future__ import annotations

from .common import *
from .capture import *


Q5A_BODY_MASK_MATERIAL_PATH = "/AiUEPmxRuntime/Q5A/M_Q5A_BodyMask_Green.M_Q5A_BodyMask_Green"
Q5A_SLOT_MASK_MATERIAL_PATH = "/AiUEPmxRuntime/Q5A/M_Q5A_SlotMask_Red.M_Q5A_SlotMask_Red"
Q5A_BASE_MASK_MATERIAL_PATH = "/AiUEPmxRuntime/Q5A/M_Q5A_UnlitMaskBase.M_Q5A_UnlitMaskBase"
Q5A_ASSET_DIRECTORY = "/AiUEPmxRuntime/Q5A"


def _configure_q5a_base_material(base_material) -> None:
    if not base_material:
        return
    for property_name, value in (
        ("two_sided", True),
        ("blend_mode", unreal.BlendMode.BLEND_OPAQUE),
        ("shading_model", unreal.MaterialShadingModel.MSM_UNLIT),
        ("used_with_skeletal_mesh", True),
    ):
        try:
            base_material.set_editor_property(property_name, value)
        except Exception:
            pass
    try:
        unreal.MaterialEditingLibrary.recompile_material(base_material)
    except Exception:
        pass
    save_loaded_asset(base_material)


def _configure_q5a_color_material(material) -> None:
    if not material:
        return
    for property_name, value in (
        ("two_sided", True),
        ("blend_mode", unreal.BlendMode.BLEND_OPAQUE),
        ("shading_model", unreal.MaterialShadingModel.MSM_UNLIT),
        ("used_with_skeletal_mesh", True),
        ("used_with_static_meshes", True),
    ):
        try:
            material.set_editor_property(property_name, value)
        except Exception:
            pass
    try:
        unreal.MaterialEditingLibrary.recompile_material(material)
    except Exception:
        pass
    save_loaded_asset(material)


def _ensure_q5a_color_material(asset_name: str, asset_path: str, color) -> object | None:
    material = unreal.EditorAssetLibrary.load_asset(asset_path)
    if material:
        _configure_q5a_color_material(material)
        return material
    try:
        if not unreal.EditorAssetLibrary.does_directory_exist(Q5A_ASSET_DIRECTORY):
            unreal.EditorAssetLibrary.make_directory(Q5A_ASSET_DIRECTORY)
    except Exception:
        pass
    try:
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        factory = unreal.MaterialFactoryNew()
        material = asset_tools.create_asset(asset_name, Q5A_ASSET_DIRECTORY, unreal.Material, factory)
        if material:
            color_expression = unreal.MaterialEditingLibrary.create_material_expression(
                material,
                unreal.MaterialExpressionConstant3Vector,
                -384,
                0,
            )
            color_expression.set_editor_property("constant", color)
            unreal.MaterialEditingLibrary.connect_material_property(color_expression, "", unreal.MaterialProperty.MP_BASE_COLOR)
            unreal.MaterialEditingLibrary.connect_material_property(color_expression, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
            _configure_q5a_color_material(material)
        return material
    except Exception:
        return unreal.EditorAssetLibrary.load_asset(asset_path)


def _ensure_q5a_mask_materials() -> tuple[object, object, list[str]]:
    warnings = []
    body_material = unreal.EditorAssetLibrary.load_asset(Q5A_BODY_MASK_MATERIAL_PATH)
    slot_material = unreal.EditorAssetLibrary.load_asset(Q5A_SLOT_MASK_MATERIAL_PATH)
    if body_material and slot_material:
        _configure_q5a_color_material(body_material)
        _configure_q5a_color_material(slot_material)
        return body_material, slot_material, warnings

    try:
        if not unreal.EditorAssetLibrary.does_directory_exist(Q5A_ASSET_DIRECTORY):
            unreal.EditorAssetLibrary.make_directory(Q5A_ASSET_DIRECTORY)
    except Exception as exc:
        warnings.append(f"qa_material_directory_prepare_failed:{exc}")

    base_material = unreal.EditorAssetLibrary.load_asset(Q5A_BASE_MASK_MATERIAL_PATH)
    if not base_material:
        try:
            asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
            factory = unreal.MaterialFactoryNew()
            base_material = asset_tools.create_asset("M_Q5A_UnlitMaskBase", Q5A_ASSET_DIRECTORY, unreal.Material, factory)
            if base_material:
                parameter_expression = unreal.MaterialEditingLibrary.create_material_expression(
                    base_material,
                    unreal.MaterialExpressionVectorParameter,
                    -384,
                    0,
                )
                parameter_expression.set_editor_property("parameter_name", "MaskColor")
                parameter_expression.set_editor_property("default_value", unreal.LinearColor(1.0, 0.0, 0.0, 1.0))
                unreal.MaterialEditingLibrary.connect_material_property(parameter_expression, "", unreal.MaterialProperty.MP_BASE_COLOR)
                unreal.MaterialEditingLibrary.connect_material_property(parameter_expression, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
                _configure_q5a_base_material(base_material)
        except Exception as exc:
            warnings.append(f"qa_material_create_failed:base:{exc}")
            base_material = unreal.EditorAssetLibrary.load_asset(Q5A_BASE_MASK_MATERIAL_PATH)
    if base_material:
        _configure_q5a_base_material(base_material)

    body_material = body_material or _ensure_q5a_color_material("M_Q5A_BodyMask_Green", Q5A_BODY_MASK_MATERIAL_PATH, unreal.LinearColor(0.0, 1.0, 0.0, 1.0))
    slot_material = slot_material or _ensure_q5a_color_material("M_Q5A_SlotMask_Red", Q5A_SLOT_MASK_MATERIAL_PATH, unreal.LinearColor(1.0, 0.0, 0.0, 1.0))
    if not body_material:
        body_material = unreal.EditorAssetLibrary.load_asset("/AiUEPmxRuntime/Q5A/MI_Q5A_BodyMask_Green.MI_Q5A_BodyMask_Green")
    if not slot_material:
        slot_material = unreal.EditorAssetLibrary.load_asset("/AiUEPmxRuntime/Q5A/MI_Q5A_SlotMask_Red.MI_Q5A_SlotMask_Red")
    try:
        save_directory(Q5A_ASSET_DIRECTORY)
    except Exception:
        pass
    return body_material, slot_material, warnings


def _component_path_name(component) -> str:
    if not component:
        return ""
    if hasattr(component, "get_path_name"):
        try:
            return str(component.get_path_name() or "")
        except Exception:
            pass
    return str(getattr(component, "get_name", lambda: "")() or "")


def _component_material_slot_count(component) -> int:
    if not component or not hasattr(component, "get_num_materials"):
        return 0
    try:
        return int(component.get_num_materials() or 0)
    except Exception:
        return 0


def _component_materials(component) -> list:
    materials = []
    slot_count = _component_material_slot_count(component)
    for index in range(slot_count):
        material = None
        try:
            material = component.get_material(index)
        except Exception:
            material = None
        materials.append(material)
    return materials


def _component_material_paths(component) -> list[str]:
    material_paths = []
    for material in _component_materials(component):
        if material and hasattr(material, "get_path_name"):
            try:
                material_paths.append(str(material.get_path_name() or ""))
                continue
            except Exception:
                pass
        material_paths.append("")
    return material_paths


def _component_debug_payload(component) -> dict:
    return {
        **component_visibility_record(component),
        "path_name": _component_path_name(component),
        "bounds": component_bounds_payload(component),
        "attach": component_attach_payload(component),
        "world_transform": component_transform_payload(component),
        "material_slot_count": _component_material_slot_count(component),
        "materials": _component_material_paths(component),
    }


def _iter_actor_mesh_components(actor) -> list:
    if not actor:
        return []
    components = []
    for component_class in (getattr(unreal, "SkeletalMeshComponent", None), getattr(unreal, "StaticMeshComponent", None)):
        if component_class is None:
            continue
        try:
            components.extend(list(actor.get_components_by_class(component_class) or []))
        except Exception:
            continue
    return components


def _snapshot_render_state(components: list) -> list[dict]:
    entries = []
    seen = set()
    for component in components or []:
        if not component:
            continue
        component_key = _component_path_name(component) or str(id(component))
        if component_key in seen:
            continue
        seen.add(component_key)
        entry = {
            "component": component,
            "component_name": str(getattr(component, "get_name", lambda: "")() or ""),
            "component_path": component_key,
            "visible": None,
            "hidden_in_game": None,
            "cast_shadow": None,
            "render_in_main_pass": None,
            "render_in_depth_pass": None,
            "materials": _component_materials(component),
        }
        for property_name in ("visible", "hidden_in_game", "cast_shadow", "render_in_main_pass", "render_in_depth_pass"):
            try:
                entry[property_name] = component.get_editor_property(property_name)
            except Exception:
                entry[property_name] = None
        entries.append(entry)
    return entries


def _apply_component_visibility(component, visible: bool) -> list[str]:
    warnings = []
    if not component:
        return warnings
    try:
        if hasattr(component, "set_visibility"):
            component.set_visibility(bool(visible), True)
        else:
            component.set_editor_property("visible", bool(visible))
    except Exception as exc:
        warnings.append(f"set_visibility_failed:{_component_path_name(component)}:{exc}")
    try:
        component.set_editor_property("visible", bool(visible))
    except Exception:
        pass
    try:
        if hasattr(component, "set_hidden_in_game"):
            component.set_hidden_in_game(not bool(visible), True)
    except Exception:
        pass
    try:
        component.set_editor_property("hidden_in_game", not bool(visible))
    except Exception:
        pass
    for property_name, value in (
        ("render_in_main_pass", bool(visible)),
        ("render_in_depth_pass", bool(visible)),
    ):
        try:
            component.set_editor_property(property_name, value)
        except Exception:
            pass
    try:
        component.set_editor_property("cast_shadow", bool(visible))
    except Exception:
        pass
    try:
        if hasattr(component, "mark_render_state_dirty"):
            component.mark_render_state_dirty()
    except Exception:
        pass
    for method_name in ("post_edit_change", "reregister_component"):
        try:
            if hasattr(component, method_name):
                getattr(component, method_name)()
        except Exception:
            pass
    return warnings


def _apply_material_override(component, material_asset) -> list[str]:
    warnings = []
    if not component:
        return warnings
    slot_count = max(_component_material_slot_count(component), 1)
    for material_index in range(slot_count):
        try:
            component.set_material(material_index, material_asset)
        except Exception as exc:
            warnings.append(f"set_material_failed:{_component_path_name(component)}:{material_index}:{exc}")
    try:
        if hasattr(component, "mark_render_state_dirty"):
            component.mark_render_state_dirty()
    except Exception:
        pass
    for method_name in ("post_edit_change", "reregister_component"):
        try:
            if hasattr(component, method_name):
                getattr(component, method_name)()
        except Exception:
            pass
    return warnings


def _restore_render_state(entries: list[dict]) -> list[str]:
    errors = []
    for entry in entries or []:
        component = entry.get("component")
        if not component:
            errors.append(f"restore_component_missing:{entry.get('component_path') or entry.get('component_name') or 'unknown'}")
            continue
        try:
            visible_value = entry.get("visible")
            _apply_component_visibility(component, True if visible_value is None else bool(visible_value))
            if entry.get("hidden_in_game") is not None:
                try:
                    component.set_editor_property("hidden_in_game", bool(entry.get("hidden_in_game")))
                except Exception:
                    pass
            if entry.get("cast_shadow") is not None:
                try:
                    component.set_editor_property("cast_shadow", bool(entry.get("cast_shadow")))
                except Exception:
                    pass
            for property_name in ("render_in_main_pass", "render_in_depth_pass"):
                if entry.get(property_name) is not None:
                    try:
                        component.set_editor_property(property_name, bool(entry.get(property_name)))
                    except Exception:
                        pass
            materials = list(entry.get("materials") or [])
            slot_count = max(_component_material_slot_count(component), len(materials))
            for material_index in range(slot_count):
                material = materials[material_index] if material_index < len(materials) else None
                try:
                    component.set_material(material_index, material)
                except Exception as exc:
                    errors.append(
                        f"restore_material_failed:{entry.get('component_path') or entry.get('component_name') or 'unknown'}:{material_index}:{exc}"
                    )
            try:
                if hasattr(component, "mark_render_state_dirty"):
                    component.mark_render_state_dirty()
            except Exception:
                pass
            for method_name in ("post_edit_change", "reregister_component"):
                try:
                    if hasattr(component, method_name):
                        getattr(component, method_name)()
                except Exception:
                    pass
        except Exception as exc:
            errors.append(f"restore_component_failed:{entry.get('component_path') or entry.get('component_name') or 'unknown'}:{exc}")
    return errors


def _flush_editor_render_state() -> None:
    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        world = None
    if world:
        try:
            world.send_all_end_of_frame_updates()
        except Exception:
            pass
    try:
        level_editor_subsystem().editor_invalidate_viewports()
    except Exception:
        pass
    time.sleep(0.05)


def _apply_q5a_pass_state(
    *,
    render_components: list,
    body_component,
    slot_component,
    body_material,
    slot_material,
    pass_id: str,
) -> tuple[list[str], list[str]]:
    warnings = []
    errors = []
    visible_component_keys = set()
    if pass_id in {"body_only", "combined_visible"} and body_component:
        visible_component_keys.add(_component_path_name(body_component) or str(id(body_component)))
    if pass_id in {"slot_only", "combined_visible"} and slot_component:
        visible_component_keys.add(_component_path_name(slot_component) or str(id(slot_component)))

    for component in render_components:
        component_key = _component_path_name(component) or str(id(component))
        warnings.extend(_apply_component_visibility(component, component_key in visible_component_keys))

    if pass_id in {"body_only", "combined_visible"} and body_component:
        warnings.extend(_apply_material_override(body_component, body_material))
    if pass_id in {"slot_only", "combined_visible"} and slot_component:
        warnings.extend(_apply_material_override(slot_component, slot_material))

    if pass_id in {"body_only", "combined_visible"} and not body_component:
        errors.append("body_component_missing")
    if pass_id in {"slot_only", "combined_visible"} and not slot_component:
        errors.append("slot_component_missing")
    return warnings, errors


def _capture_q5a_pass(
    *,
    spawned_host,
    request: dict,
    output_path: Path,
    shot_plan: dict,
    pass_id: str,
    body_component,
    slot_component,
    render_components: list,
    body_material,
    slot_material,
) -> dict:
    state_entries = _snapshot_render_state(render_components)
    warnings = []
    errors = []
    capture_result = {}
    show_only_components = []
    if pass_id in {"body_only", "combined_visible"} and body_component:
        show_only_components.append(body_component)
    if pass_id in {"slot_only", "combined_visible"} and slot_component:
        show_only_components.append(slot_component)
    try:
        apply_warnings, apply_errors = _apply_q5a_pass_state(
            render_components=render_components,
            body_component=body_component,
            slot_component=slot_component,
            body_material=body_material,
            slot_material=slot_material,
            pass_id=pass_id,
        )
        warnings.extend(apply_warnings)
        errors.extend(apply_errors)
        if not errors:
            body_materials_after_apply = _component_material_paths(body_component)
            slot_materials_after_apply = _component_material_paths(slot_component)
            body_visibility_after_apply = component_visibility_record(body_component)
            slot_visibility_after_apply = component_visibility_record(slot_component)
            _flush_editor_render_state()
            capture_result = capture_frame_for_actor_object(
                spawned_host,
                {
                    "output_path": str(output_path.resolve()),
                    "width": int(request.get("capture_width") or request.get("width") or 1280),
                    "height": int(request.get("capture_height") or request.get("height") or 720),
                    "capture_hdr": bool(request.get("capture_hdr", False)),
                    "capture_profile": str(request.get("capture_profile") or "qa_mask_skeletal_only"),
                    "scene_capture_source": str(request.get("scene_capture_source") or "SCS_FINAL_COLOR_LDR"),
                    "scene_capture_warmup_count": int(request.get("scene_capture_warmup_count") or 2),
                    "scene_capture_warmup_delay_seconds": float(request.get("scene_capture_warmup_delay_seconds") or 0.05),
                    "capture_delay_seconds": float(request.get("capture_delay_seconds") or 0.2),
                    "timeout_seconds": float(request.get("timeout_seconds") or 15.0),
                    "file_stability_window_seconds": float(request.get("file_stability_window_seconds") or 0.75),
                    "poll_interval_seconds": float(request.get("poll_interval_seconds") or 0.1),
                    "force_automation_capture": bool(request.get("force_automation_capture", False)),
                    "prime_niagara_before_capture": False,
                    "camera_mode": "explicit_pose",
                    "camera_source": str(shot_plan.get("camera_source") or "explicit_pose"),
                    "camera_location": shot_plan.get("camera_location"),
                    "camera_rotation": shot_plan.get("camera_rotation"),
                    "_show_only_components": show_only_components,
                },
                output_path.resolve(),
            )
            warnings.extend(list(capture_result.get("warnings") or []))
            errors.extend(list(capture_result.get("errors") or []))
            if not capture_result.get("output_exists"):
                errors.append("mask_capture_failed")
    finally:
        restore_errors = _restore_render_state(state_entries)
        _flush_editor_render_state()
        if restore_errors:
            errors.extend(["state_restore_failed"] + restore_errors)
    status = "pass" if not errors else "fail"
    return {
        "pass_id": pass_id,
        "status": status,
        "image_path": str(output_path.resolve()),
        "capture_backend": str(capture_result.get("capture_backend") or ""),
        "scene_capture_source": str(capture_result.get("scene_capture_source") or ""),
        "capture_profile": str(capture_result.get("capture_profile") or request.get("capture_profile") or ""),
        "show_only_component_paths": [
            _component_path_name(component)
            for component in show_only_components
            if component
        ],
        "body_materials_after_apply": body_materials_after_apply if "body_materials_after_apply" in locals() else [],
        "slot_materials_after_apply": slot_materials_after_apply if "slot_materials_after_apply" in locals() else [],
        "body_visibility_after_apply": body_visibility_after_apply if "body_visibility_after_apply" in locals() else {},
        "slot_visibility_after_apply": slot_visibility_after_apply if "slot_visibility_after_apply" in locals() else {},
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
    }


def inspect_visible_conflict(request: dict) -> dict:
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
    actor_label = str(request.get("actor_label") or f"AIUE_VisibleConflict_{sanitize_segment(host_record.get('character_package_id') if host_record else host_asset_path)}")
    spawned_host = actor_subsystem.spawn_actor_from_object(blueprint_asset, cell_origin, cell_rotation, True)
    if not spawned_host:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"failed_to_spawn_host:{host_asset_path}"],
        }

    spawned_host.set_actor_label(actor_label)
    try:
        try:
            spawned_host.apply_configured_loadout()
        except Exception as exc:
            warnings.append(f"apply_configured_loadout_failed:{exc}")

        override_bindings = list(request.get("slot_binding_overrides") or [])
        if override_bindings:
            if hasattr(unreal, "PMXEquipmentBlueprintLibrary"):
                try:
                    unreal.PMXEquipmentBlueprintLibrary.apply_slot_bindings(
                        spawned_host,
                        runtime_slot_binding_entries_from_request(override_bindings),
                    )
                except Exception as exc:
                    return {
                        "status": "fail",
                        "warnings": warnings,
                        "errors": [f"apply_slot_binding_overrides_failed:{exc}"],
                    }
            else:
                return {
                    "status": "fail",
                    "warnings": warnings,
                    "errors": ["pmx_blueprint_library_unavailable"],
                }

        time.sleep(max(float(request.get("settle_delay_seconds") or 0.2), 0.05))
        try:
            pmx_component = spawned_host.get_component_by_class(unreal.PMXCharacterEquipmentComponent)
        except Exception:
            pmx_component = None
        primary_mesh = actor_primary_mesh_component(spawned_host)
        slot_name = slot_name_text(request.get("slot_name"), default="clothing")
        slot_component = actor_managed_component_for_slot(spawned_host, slot_name, primary_component=primary_mesh)
        managed_components_by_slot = actor_managed_components_by_slot(spawned_host, pmx_component, primary_component=primary_mesh)
        slot_attach_state = pmx_slot_attach_states_payload(pmx_component)
        slot_conflicts = pmx_slot_conflicts_payload(pmx_component)
        slot_bindings = pmx_slot_bindings_payload(pmx_component)
        clothing_binding = next((binding for binding in slot_bindings if binding.get("slot_name") == slot_name), {})
        clothing_attach_state = next((entry for entry in slot_attach_state if entry.get("slot_name") == slot_name), {})

        body_material, slot_material, qa_material_warnings = _ensure_q5a_mask_materials()
        warnings.extend(qa_material_warnings)
        package_errors = []
        if not primary_mesh:
            package_errors.append("body_component_missing")
        if not slot_component:
            package_errors.append("slot_component_missing")
        if not body_material:
            package_errors.append("qa_material_missing:body")
        if not slot_material:
            package_errors.append("qa_material_missing:slot")

        output_root = Path(request.get("output_root") or (Path(unreal.Paths.project_saved_dir()) / "pmx_pipeline" / "visible_conflict")).expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        shot_plans = build_visual_proof_shots(spawned_host, request)
        requested_shot_ids = [str(value) for value in list(request.get("requested_shot_ids") or []) if str(value)]
        if requested_shot_ids:
            requested_id_set = set(requested_shot_ids)
            shot_plans = [shot_plan for shot_plan in shot_plans if str(shot_plan.get("shot_id") or "") in requested_id_set]
        if not shot_plans:
            package_errors.append("requested_shots_missing")

        render_components = _iter_actor_mesh_components(spawned_host)
        shot_results = []
        if not package_errors:
            for shot_plan in shot_plans:
                shot_id = str(shot_plan.get("shot_id") or "shot")
                shot_output_root = output_root / shot_id
                shot_output_root.mkdir(parents=True, exist_ok=True)
                pass_results = {}
                shot_errors = []
                shot_warnings = []
                for pass_id in ("body_only", "slot_only", "combined_visible"):
                    pass_output_path = shot_output_root / f"{pass_id}.png"
                    pass_result = _capture_q5a_pass(
                        spawned_host=spawned_host,
                        request=request,
                        output_path=pass_output_path,
                        shot_plan=shot_plan,
                        pass_id=pass_id,
                        body_component=primary_mesh,
                        slot_component=slot_component,
                        render_components=render_components,
                        body_material=body_material,
                        slot_material=slot_material,
                    )
                    pass_results[pass_id] = pass_result
                    shot_warnings.extend(list(pass_result.get("warnings") or []))
                    shot_errors.extend(list(pass_result.get("errors") or []))
                shot_results.append(
                    {
                        "shot_id": shot_id,
                        "camera_id": str(shot_plan.get("camera_id") or shot_id),
                        "camera_source": "anchor_actor" if str(request.get("camera_mode") or "") == "anchor_actor" else str(shot_plan.get("camera_source") or "explicit_pose"),
                        "status": "pass" if not shot_errors else "fail",
                        "artifacts": {
                            "body_only_image_path": str((shot_output_root / "body_only.png").resolve()),
                            "slot_only_image_path": str((shot_output_root / "slot_only.png").resolve()),
                            "combined_visible_image_path": str((shot_output_root / "combined_visible.png").resolve()),
                        },
                        "body_component": _component_debug_payload(primary_mesh),
                        "slot_component": _component_debug_payload(slot_component),
                        "pass_results": pass_results,
                        "failed_requirements": sorted(set(shot_errors)),
                        "warnings": sorted(set(shot_warnings)),
                        "errors": sorted(set(shot_errors)),
                    }
                )

        final_errors = list(package_errors)
        final_warnings = list(warnings)
        final_errors.extend(
            error
            for shot_result in shot_results
            for error in list(shot_result.get("errors") or [])
        )
        final_warnings.extend(
            warning
            for shot_result in shot_results
            for warning in list(shot_result.get("warnings") or [])
        )
        return {
            "status": "pass" if not final_errors else "fail",
            "package_id": host_record.get("character_package_id") if host_record else request.get("package_id"),
            "sample_id": host_record.get("sample_id") if host_record else request.get("sample_id"),
            "host_id": spawned_host.get_path_name(),
            "host_blueprint_asset": host_asset_path,
            "slot_name": slot_name,
            "body_component": _component_debug_payload(primary_mesh),
            "slot_component": _component_debug_payload(slot_component),
            "slot_bindings": slot_bindings,
            "managed_components_by_slot": managed_components_by_slot,
            "slot_attach_state": slot_attach_state,
            "slot_conflicts": slot_conflicts,
            "clothing_binding": clothing_binding,
            "clothing_attach_state": clothing_attach_state,
            "shot_results": shot_results,
            "artifacts": {
                "output_root": str(output_root.resolve()),
            },
            "warnings": sorted(set(final_warnings)),
            "errors": sorted(set(final_errors)),
        }
    finally:
        try:
            actor_subsystem.destroy_actor(spawned_host)
        except Exception:
            pass
