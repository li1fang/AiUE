from __future__ import annotations

from .common import *
from .retarget_profile import *
from .retarget_session import (
    apply_retarget_configured_loadout,
    destroy_retarget_host,
    prepare_retarget_host_session,
)


def retarget_bootstrap(request: dict) -> dict:
    prepared = prepare_retarget_host_session(
        request,
        actor_label_prefix="AIUE_RetargetBootstrap",
        default_location=unreal.Vector(0.0, 0.0, 120.0),
        default_rotation=make_rotator(0.0, 180.0, 0.0),
        require_animation_asset=True,
    )
    if prepared.get("status") != "pass":
        return prepared

    warnings = list(prepared.get("warnings") or [])
    level_path = prepared.get("level_path")
    host_asset_path = prepared["host_asset_path"]
    host_record = prepared.get("host_record")
    animation_asset_path = str(prepared.get("animation_asset_path") or "")
    animation_asset = prepared.get("animation_asset")
    actor_subsystem = prepared["actor_subsystem"]
    spawned_host = prepared["spawned_host"]
    errors = []
    try:
        apply_retarget_configured_loadout(spawned_host, warnings)

        time.sleep(max(float(request.get("settle_delay_seconds") or 0.2), 0.05))
        primary_mesh = actor_primary_mesh_component(spawned_host)
        source_mesh_asset = skeletal_mesh_asset_from_component(primary_mesh)
        source_mesh_path = ""
        source_skeleton_path = ""
        if source_mesh_asset:
            try:
                source_mesh_path = source_mesh_asset.get_path_name()
            except Exception:
                source_mesh_path = ""
            source_skeleton_asset = skeleton_asset_from_skeletal_mesh_asset(source_mesh_asset)
            if source_skeleton_asset:
                try:
                    source_skeleton_path = source_skeleton_asset.get_path_name()
                except Exception:
                    source_skeleton_path = ""
        if not source_mesh_asset:
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": ["source_skeletal_mesh_missing"],
            }

        target_ik_rig_asset, target_selection = choose_target_ik_rig_asset(animation_asset, str(request.get("target_ik_rig_asset_path") or ""))
        if not target_ik_rig_asset:
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": ["target_ik_rig_missing"],
            }

        source_ik_rig_request_path = str(request.get("source_ik_rig_asset_path") or "")
        if not source_ik_rig_request_path:
            asset_root = str(request.get("asset_root") or "/Game/PMXPipeline").rstrip("/")
            source_ik_rig_request_path = f"{asset_root}/Retarget/Source/IK_{sanitize_segment(host_record.get('character_package_id') if host_record else 'pmx_source')}"
        source_ik_rig_asset, source_ik_rig_created = create_or_load_ik_rig_asset(source_ik_rig_request_path)
        if not source_ik_rig_asset:
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": [f"source_ik_rig_create_failed:{source_ik_rig_request_path}"],
            }

        source_controller = unreal.IKRigController.get_controller(source_ik_rig_asset)
        source_mesh_applied = False
        auto_retarget_definition_applied = False
        if source_controller:
            try:
                source_mesh_applied = bool(source_controller.set_skeletal_mesh(source_mesh_asset))
            except Exception as exc:
                warnings.append(f"source_ik_rig_set_skeletal_mesh_failed:{exc}")
            try:
                auto_retarget_definition_applied = bool(source_controller.apply_auto_generated_retarget_definition())
            except Exception as exc:
                warnings.append(f"source_ik_rig_auto_retarget_definition_failed:{exc}")
        else:
            errors.append("source_ik_rig_controller_missing")

        target_controller = unreal.IKRigController.get_controller(target_ik_rig_asset)
        target_mesh_asset = target_controller.get_skeletal_mesh() if target_controller else None
        target_mesh_path = ""
        if target_mesh_asset:
            try:
                target_mesh_path = target_mesh_asset.get_path_name()
            except Exception:
                target_mesh_path = ""

        retargeter_request_path = str(request.get("retargeter_asset_path") or "")
        if not retargeter_request_path:
            asset_root = str(request.get("asset_root") or "/Game/PMXPipeline").rstrip("/")
            target_slug = sanitize_segment(base_name_from_asset_path(target_selection.get("resolved_asset_path") or target_mesh_path or "target"))
            retargeter_request_path = f"{asset_root}/Retarget/Demo/RTG_{sanitize_segment(host_record.get('character_package_id') if host_record else 'pmx_source')}_to_{target_slug}"
        retargeter_asset, retargeter_created = create_or_load_retargeter_asset(retargeter_request_path)
        if not retargeter_asset:
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": [f"retargeter_create_failed:{retargeter_request_path}"],
            }

        retargeter_controller = unreal.IKRetargeterController.get_controller(retargeter_asset)
        if not retargeter_controller:
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": ["retargeter_controller_missing"],
            }

        source_enum = retarget_source_enum_value()
        target_enum = retarget_target_enum_value()
        auto_map_enum = auto_map_chain_type_value()
        if source_enum is None or target_enum is None:
            errors.append("retarget_source_or_target_enum_missing")

        source_assignment_ok = False
        target_assignment_ok = False
        if source_enum is not None and target_enum is not None:
            try:
                retargeter_controller.set_ik_rig(source_enum, source_ik_rig_asset)
                source_assignment_ok = True
            except Exception as exc:
                warnings.append(f"retargeter_set_source_ik_rig_failed:{exc}")
            try:
                retargeter_controller.set_ik_rig(target_enum, target_ik_rig_asset)
                target_assignment_ok = True
            except Exception as exc:
                warnings.append(f"retargeter_set_target_ik_rig_failed:{exc}")
            if source_mesh_asset:
                try:
                    retargeter_controller.set_preview_mesh(source_enum, source_mesh_asset)
                except Exception as exc:
                    warnings.append(f"retargeter_set_source_preview_mesh_failed:{exc}")
            if target_mesh_asset:
                try:
                    retargeter_controller.set_preview_mesh(target_enum, target_mesh_asset)
                except Exception as exc:
                    warnings.append(f"retargeter_set_target_preview_mesh_failed:{exc}")

        try:
            retargeter_controller.add_default_ops()
        except Exception as exc:
            warnings.append(f"retargeter_add_default_ops_failed:{exc}")
        if source_enum is not None:
            try:
                retargeter_controller.assign_ik_rig_to_all_ops(source_enum, source_ik_rig_asset)
            except Exception as exc:
                warnings.append(f"retargeter_assign_source_ik_rig_failed:{exc}")
        if target_enum is not None:
            try:
                retargeter_controller.assign_ik_rig_to_all_ops(target_enum, target_ik_rig_asset)
            except Exception as exc:
                warnings.append(f"retargeter_assign_target_ik_rig_failed:{exc}")

        op_count = 0
        try:
            op_count = int(retargeter_controller.get_num_retarget_ops() or 0)
        except Exception:
            op_count = 0
        for index in range(op_count):
            try:
                retargeter_controller.run_op_initial_setup(index)
            except Exception as exc:
                warnings.append(f"retargeter_run_op_initial_setup_failed:{index}:{exc}")
        auto_map_invoked = False
        if auto_map_enum is not None:
            try:
                retargeter_controller.auto_map_chains(auto_map_enum, True)
                auto_map_invoked = True
            except Exception as exc:
                warnings.append(f"retargeter_auto_map_failed:{exc}")

        source_ik_rig_profile = ik_rig_profile_payload(source_ik_rig_asset)
        target_ik_rig_profile = ik_rig_profile_payload(target_ik_rig_asset)
        target_chain_names = [item.get("chain_name") or "" for item in target_ik_rig_profile.get("chains") or [] if item.get("chain_name")]
        mapped_chain_records = []
        mapped_chain_count = 0
        for target_chain_name in target_chain_names:
            source_chain_name = ""
            try:
                source_chain_name = str(retargeter_controller.get_source_chain(to_name(target_chain_name)) or "")
            except Exception:
                source_chain_name = ""
            if source_chain_name in {"None", "NAME_None"}:
                source_chain_name = ""
            if source_chain_name:
                mapped_chain_count += 1
            mapped_chain_records.append(
                {
                    "target_chain_name": target_chain_name,
                    "source_chain_name": source_chain_name,
                    "mapped": bool(source_chain_name),
                }
            )

        save_loaded_asset(source_ik_rig_asset)
        save_loaded_asset(retargeter_asset)
        status = "pass" if source_assignment_ok and target_assignment_ok and not errors else "fail"
        if source_ik_rig_profile.get("chain_count", 0) == 0:
            warnings.append("source_ik_rig_has_no_retarget_chains")
        if mapped_chain_count == 0:
            warnings.append("retargeter_has_no_mapped_target_chains")
        recommended_next_step_id = "retry_animation_preview_with_retargeter" if mapped_chain_count > 0 else "author_source_retarget_chains"
        recommended_next_step_reason = (
            "The retargeter has at least one mapped chain, so the next step is retrying a real animation preview through the new retarget assets."
            if mapped_chain_count > 0
            else "The bootstrap assets exist, but the imported PMX source rig still has no mapped retarget chains."
        )
        return {
            "status": status,
            "package_id": host_record.get("character_package_id") if host_record else request.get("package_id"),
            "sample_id": host_record.get("sample_id") if host_record else request.get("sample_id"),
            "host_id": spawned_host.get_path_name(),
            "host_blueprint_asset": host_asset_path,
            "level_path": level_path or get_current_level_path(),
            "animation_asset_path": animation_asset_path,
            "source_mesh_asset_path": source_mesh_path,
            "source_skeleton_asset_path": source_skeleton_path,
            "source_ik_rig_asset_path": canonical_asset_path(source_ik_rig_asset.get_path_name()),
            "source_ik_rig_created": source_ik_rig_created,
            "source_mesh_applied_to_ik_rig": source_mesh_applied,
            "source_auto_generated_retarget_definition_applied": auto_retarget_definition_applied,
            "target_ik_rig_asset_path": canonical_asset_path(target_ik_rig_asset.get_path_name()),
            "target_ik_rig_selection": target_selection,
            "retargeter_asset_path": canonical_asset_path(retargeter_asset.get_path_name()),
            "retargeter_created": retargeter_created,
            "source_ik_rig_assigned": source_assignment_ok,
            "target_ik_rig_assigned": target_assignment_ok,
            "auto_map_invoked": auto_map_invoked,
            "operation_count": op_count,
            "source_ik_rig_profile": source_ik_rig_profile,
            "target_ik_rig_profile": target_ik_rig_profile,
            "mapped_chain_count": mapped_chain_count,
            "mapped_chain_records": mapped_chain_records,
            "recommended_next_step_id": recommended_next_step_id,
            "recommended_next_step_reason": recommended_next_step_reason,
            "warnings": warnings,
            "errors": errors,
        }
    finally:
        destroy_retarget_host(actor_subsystem, spawned_host)


__all__ = ["retarget_bootstrap"]
