from __future__ import annotations

from .common import *
from .capture import *


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
