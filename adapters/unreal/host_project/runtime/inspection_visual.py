from __future__ import annotations

from .common import *
from .inspection_session import (
    apply_inspection_configured_loadout,
    destroy_inspection_host,
    prepare_inspection_host_session,
)
from .inspection_visual_capture import capture_visual_state_for_host


def inspect_host_visual(request: dict) -> dict:
    prepared = prepare_inspection_host_session(
        request,
        actor_label_prefix="AIUE_VisualProof",
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

        output_root = Path(request.get("output_root") or (Path(unreal.Paths.project_saved_dir()) / "pmx_pipeline" / "visual_proof")).expanduser().resolve()
        result = capture_visual_state_for_host(
            spawned_host,
            request,
            host_asset_path,
            host_record,
            output_root,
            override_bindings=list(request.get("slot_binding_overrides") or []),
        )
        result["warnings"] = sorted(set(list(warnings) + list(result.get("warnings") or [])))
        return result
    finally:
        destroy_inspection_host(actor_subsystem, spawned_host)

def inspect_live_fx_visual_pair(request: dict) -> dict:
    prepared = prepare_inspection_host_session(
        request,
        actor_label_prefix="AIUE_LiveFxVisualPair",
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

        output_root = Path(request.get("output_root") or (Path(unreal.Paths.project_saved_dir()) / "pmx_pipeline" / "live_fx_visual_pair")).expanduser().resolve()
        baseline_root = output_root / "baseline"
        with_fx_root = output_root / "with_fx"
        baseline_request = dict(request)
        baseline_request.pop("slot_binding_overrides", None)
        baseline_request.pop("with_fx_slot_binding_overrides", None)
        baseline_request.pop("baseline_slot_binding_overrides", None)
        baseline_result = capture_visual_state_for_host(
            spawned_host,
            baseline_request,
            host_asset_path,
            host_record,
            baseline_root,
            override_bindings=list(request.get("baseline_slot_binding_overrides") or []),
        )
        with_fx_result = capture_visual_state_for_host(
            spawned_host,
            request,
            host_asset_path,
            host_record,
            with_fx_root,
            override_bindings=list(request.get("with_fx_slot_binding_overrides") or request.get("slot_binding_overrides") or []),
        )
        baseline_result_path = output_root / "baseline_result.json"
        with_fx_result_path = output_root / "with_fx_result.json"
        write_json(baseline_result_path, {"result": baseline_result})
        write_json(with_fx_result_path, {"result": with_fx_result})
        errors = sorted(
            set(
                list(baseline_result.get("errors") or [])
                + list(with_fx_result.get("errors") or [])
            )
        )
        return {
            "status": "pass" if baseline_result.get("status") == "pass" and with_fx_result.get("status") == "pass" else "fail",
            "package_id": host_record.get("character_package_id") if host_record else request.get("package_id"),
            "sample_id": host_record.get("sample_id") if host_record else request.get("sample_id"),
            "host_id": spawned_host.get_path_name(),
            "host_blueprint_asset": host_asset_path,
            "baseline_result": baseline_result,
            "with_fx_result": with_fx_result,
            "warnings": sorted(set(list(warnings) + list(baseline_result.get("warnings") or []) + list(with_fx_result.get("warnings") or []))),
            "errors": errors,
            "artifacts": {
                "pair_output_root": str(output_root.resolve()),
                "baseline_result_path": str(baseline_result_path.resolve()),
                "with_fx_result_path": str(with_fx_result_path.resolve()),
            },
        }
    finally:
        destroy_inspection_host(actor_subsystem, spawned_host)


__all__ = [
    "capture_visual_state_for_host",
    "inspect_host_visual",
    "inspect_live_fx_visual_pair",
]
