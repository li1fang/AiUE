from __future__ import annotations

from .common import *
from .capture import *
from .inspection_quality_q5a_capture import (
    _capture_q5a_pass,
    _component_debug_payload,
    _iter_actor_mesh_components,
)
from .inspection_quality_q5a_materials import _ensure_q5a_mask_materials
from .inspection_session import (
    apply_inspection_configured_loadout,
    destroy_inspection_host,
    prepare_inspection_host_session,
)


def inspect_visible_conflict(request: dict) -> dict:
    prepared = prepare_inspection_host_session(
        request,
        actor_label_prefix="AIUE_VisibleConflict",
        default_location=unreal.Vector(0.0, 0.0, 30000.0),
        default_rotation=make_rotator(0.0, 180.0, 0.0),
        location_keys=("cell_origin",),
        rotation_keys=("cell_rotation",),
    )
    if prepared.get("status") != "pass":
        return prepared

    warnings = list(prepared.get("warnings") or [])
    host_asset_path = prepared["host_asset_path"]
    host_record = prepared.get("host_record")
    actor_subsystem = prepared["actor_subsystem"]
    spawned_host = prepared["spawned_host"]
    try:
        apply_inspection_configured_loadout(spawned_host, warnings)

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
        destroy_inspection_host(actor_subsystem, spawned_host)


__all__ = [
    "inspect_visible_conflict",
]
