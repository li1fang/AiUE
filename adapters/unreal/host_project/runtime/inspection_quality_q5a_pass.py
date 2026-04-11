from __future__ import annotations

from .common import *
from .capture import *
from .inspection_quality_q5a_state import (
    _apply_component_visibility,
    _apply_material_override,
    _component_material_paths,
    _component_path_name,
    _flush_editor_render_state,
    _restore_render_state,
    _snapshot_render_state,
)


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


__all__ = ["_capture_q5a_pass"]
