from __future__ import annotations

from .common import *
from .capture import load_level
from .retarget_profile import *
from .retarget_preview import *

# Command shim: profiling/tooling helpers live in retarget_profile/preview.
def retarget_preflight(request: dict) -> dict:
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

    animation_asset_path = str(request.get("animation_asset_path") or "")
    animation_asset = load_asset_from_any_path(animation_asset_path)
    if not animation_asset:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"animation_asset_load_failed:{animation_asset_path or 'missing'}"],
        }

    spawn_location = vector_from_request(request.get("location"), unreal.Vector(0.0, 0.0, 120.0))
    spawn_rotation = rotator_from_request(request.get("rotation"), make_rotator(0.0, 180.0, 0.0))
    actor_label = str(request.get("actor_label") or f"AIUE_RetargetPreflight_{sanitize_segment(host_record.get('character_package_id') if host_record else host_asset_path)}")
    spawned_host = actor_subsystem.spawn_actor_from_object(blueprint_asset, spawn_location, spawn_rotation, True)
    if not spawned_host:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"failed_to_spawn_host:{host_asset_path}"],
        }

    spawned_host.set_actor_label(actor_label)
    blocking_reasons = []
    try:
        try:
            spawned_host.apply_configured_loadout()
        except Exception as exc:
            warnings.append(f"apply_configured_loadout_failed:{exc}")

        time.sleep(max(float(request.get("settle_delay_seconds") or 0.2), 0.05))
        primary_mesh = actor_primary_mesh_component(spawned_host)
        compatibility = animation_compatibility_payload(primary_mesh, animation_asset)
        source_profile = skeleton_profile_payload_from_component(primary_mesh)
        target_profile = animation_skeleton_profile_payload(animation_asset)
        tooling = retarget_tooling_inventory(
            str(host_record.get("sample_id") if host_record else request.get("sample_id") or ""),
            str(host_record.get("character_package_id") if host_record else request.get("package_id") or ""),
            source_profile,
            target_profile,
        )

        if not compatibility.get("mesh_skeleton_asset_path"):
            blocking_reasons.append("source_skeleton_missing")
        if not compatibility.get("animation_skeleton_asset_path"):
            blocking_reasons.append("animation_skeleton_missing")

        requires_retarget = not compatibility.get("compatible")
        viable = bool(
            compatibility.get("compatible")
            or (
                tooling.get("can_author_new_retarget_assets")
                and source_profile.get("skeleton_asset_path")
                and target_profile.get("skeleton_asset_path")
            )
        )
        if requires_retarget and not tooling.get("can_author_new_retarget_assets"):
            blocking_reasons.append("ik_retarget_tooling_unavailable")
        if requires_retarget and (source_profile.get("humanoid_markers") or {}).get("manual_chain_mapping_likely"):
            warnings.append("source_skeleton_will_need_manual_chain_mapping")

        next_steps = retarget_recommendations(compatibility, source_profile, target_profile, tooling)
        return {
            "status": "pass" if viable and not blocking_reasons else "fail",
            "package_id": host_record.get("character_package_id") if host_record else request.get("package_id"),
            "sample_id": host_record.get("sample_id") if host_record else request.get("sample_id"),
            "host_id": spawned_host.get_path_name(),
            "host_blueprint_asset": host_asset_path,
            "level_path": level_path or get_current_level_path(),
            "animation_asset_path": animation_asset_path,
            "animation_compatibility": compatibility,
            "source_skeleton_profile": source_profile,
            "target_skeleton_profile": target_profile,
            "retarget_tooling": tooling,
            "retarget_readiness": {
                "direct_animation_compatible": bool(compatibility.get("compatible")),
                "requires_retarget": requires_retarget,
                "viable": viable and not blocking_reasons,
                "blocking_reasons": sorted(set(blocking_reasons)),
                "recommended_next_steps": next_steps,
            },
            "warnings": warnings,
            "errors": [] if viable and not blocking_reasons else sorted(set(blocking_reasons)),
        }
    finally:
        try:
            actor_subsystem.destroy_actor(spawned_host)
        except Exception:
            pass


def retarget_bootstrap(request: dict) -> dict:
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

    animation_asset_path = str(request.get("animation_asset_path") or "")
    animation_asset = load_asset_from_any_path(animation_asset_path)
    if not animation_asset:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"animation_asset_load_failed:{animation_asset_path or 'missing'}"],
        }

    spawn_location = vector_from_request(request.get("location"), unreal.Vector(0.0, 0.0, 120.0))
    spawn_rotation = rotator_from_request(request.get("rotation"), make_rotator(0.0, 180.0, 0.0))
    actor_label = str(request.get("actor_label") or f"AIUE_RetargetBootstrap_{sanitize_segment(host_record.get('character_package_id') if host_record else host_asset_path)}")
    spawned_host = actor_subsystem.spawn_actor_from_object(blueprint_asset, spawn_location, spawn_rotation, True)
    if not spawned_host:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"failed_to_spawn_host:{host_asset_path}"],
        }

    spawned_host.set_actor_label(actor_label)
    errors = []
    try:
        try:
            spawned_host.apply_configured_loadout()
        except Exception as exc:
            warnings.append(f"apply_configured_loadout_failed:{exc}")

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
        try:
            actor_subsystem.destroy_actor(spawned_host)
        except Exception:
            pass


def retarget_author_chains(request: dict) -> dict:
    warnings = []
    source_ik_rig_asset_path = str(request.get("source_ik_rig_asset_path") or "")
    retargeter_asset_path = str(request.get("retargeter_asset_path") or "")
    target_ik_rig_asset_path = str(request.get("target_ik_rig_asset_path") or "")

    source_ik_rig_asset = load_asset_from_any_path(source_ik_rig_asset_path)
    if not source_ik_rig_asset:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"source_ik_rig_load_failed:{source_ik_rig_asset_path or 'missing'}"],
        }
    retargeter_asset = load_asset_from_any_path(retargeter_asset_path)
    if not retargeter_asset:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"retargeter_load_failed:{retargeter_asset_path or 'missing'}"],
        }
    target_ik_rig_asset = load_asset_from_any_path(target_ik_rig_asset_path) if target_ik_rig_asset_path else None

    source_controller = unreal.IKRigController.get_controller(source_ik_rig_asset)
    retargeter_controller = unreal.IKRetargeterController.get_controller(retargeter_asset)
    if not source_controller:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": ["source_ik_rig_controller_missing"],
        }
    if not retargeter_controller:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": ["retargeter_controller_missing"],
        }

    bone_names, bone_name_source = bone_names_from_ik_rig_controller(source_controller)
    if not bone_names:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": ["source_bone_names_unresolved"],
        }

    existing_chains = ik_rig_chain_records(source_controller)
    clear_existing = bool(request.get("clear_existing_chains", True))
    removed_chain_names = []
    if clear_existing:
        for chain_record in existing_chains:
            chain_name = str(chain_record.get("chain_name") or "")
            if not chain_name:
                continue
            try:
                if source_controller.remove_retarget_chain(to_name(chain_name)):
                    removed_chain_names.append(chain_name)
            except Exception as exc:
                warnings.append(f"remove_source_chain_failed:{chain_name}:{exc}")

    planned_chains, planning_warnings, planning_diagnostics = planned_source_chain_records(bone_names)
    warnings.extend(planning_warnings)

    authored_chain_records = []
    for chain in planned_chains:
        chain_name = chain["chain_name"]
        start_bone = chain["start_bone"]
        end_bone = chain["end_bone"]
        goal_name = chain.get("goal_name") or ""
        try:
            created_name = source_controller.add_retarget_chain(
                to_name(chain_name),
                to_name(start_bone),
                to_name(end_bone),
                to_name(goal_name) if goal_name else unreal.Name("None"),
            )
            authored_chain_records.append(
                {
                    "requested_chain_name": chain_name,
                    "created_chain_name": str(created_name or chain_name),
                    "start_bone": start_bone,
                    "end_bone": end_bone,
                    "goal_name": goal_name,
                    "planning_reason": chain.get("planning_reason") or "",
                }
            )
        except Exception as exc:
            warnings.append(f"add_source_chain_failed:{chain_name}:{exc}")

    pelvis_bone = pick_best_bone_name(bone_names, [["pelvis"], ["hips"], ["\u4e0b\u534a\u8eab"], ["\u8170"], ["center"]])
    if not pelvis_bone:
        spine_chain = next((item for item in planned_chains if str(item.get("chain_name") or "") == "Spine"), None)
        root_chain = next((item for item in planned_chains if str(item.get("chain_name") or "") == "root"), None)
        pelvis_bone = str((spine_chain or {}).get("start_bone") or (root_chain or {}).get("end_bone") or "")
    retarget_root_set = False
    if pelvis_bone:
        try:
            retarget_root_set = bool(source_controller.set_retarget_root(to_name(pelvis_bone)))
        except Exception as exc:
            warnings.append(f"set_source_retarget_root_failed:{pelvis_bone}:{exc}")
    else:
        warnings.append("source_retarget_root_unresolved")

    source_enum = retarget_source_enum_value()
    target_enum = retarget_target_enum_value()
    auto_map_enum = auto_map_chain_type_value()
    if source_enum is not None:
        try:
            retargeter_controller.assign_ik_rig_to_all_ops(source_enum, source_ik_rig_asset)
        except Exception as exc:
            warnings.append(f"retargeter_reassign_source_ik_rig_failed:{exc}")
    if target_enum is not None and target_ik_rig_asset:
        try:
            retargeter_controller.assign_ik_rig_to_all_ops(target_enum, target_ik_rig_asset)
        except Exception as exc:
            warnings.append(f"retargeter_reassign_target_ik_rig_failed:{exc}")
    auto_map_invoked = False
    if auto_map_enum is not None:
        try:
            retargeter_controller.auto_map_chains(auto_map_enum, True)
            auto_map_invoked = True
        except Exception as exc:
            warnings.append(f"retargeter_auto_map_failed:{exc}")

    source_profile = ik_rig_profile_payload(source_ik_rig_asset)
    target_profile = ik_rig_profile_payload(target_ik_rig_asset) if target_ik_rig_asset else {
        "asset_path": canonical_asset_path(target_ik_rig_asset_path),
        "skeletal_mesh_asset_path": "",
        "skeleton_asset_path": "",
        "retarget_root": "",
        "chain_count": 0,
        "chains": [],
    }
    target_chain_names = [item.get("chain_name") or "" for item in target_profile.get("chains") or [] if item.get("chain_name")]
    mapped_chain_records = []
    mapped_chain_count = 0
    exact_named_mapped_chain_count = 0
    exact_named_mapped_chain_names = []
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
        exact_named_match = bool(source_chain_name and source_chain_name == target_chain_name)
        if exact_named_match:
            exact_named_mapped_chain_count += 1
            exact_named_mapped_chain_names.append(target_chain_name)
        mapped_chain_records.append(
            {
                "target_chain_name": target_chain_name,
                "source_chain_name": source_chain_name,
                "mapped": bool(source_chain_name),
                "exact_named_match": exact_named_match,
            }
        )

    save_loaded_asset(source_ik_rig_asset)
    save_loaded_asset(retargeter_asset)
    errors = []
    if source_profile.get("chain_count", 0) == 0:
        errors.append("source_chain_authoring_failed")
    if mapped_chain_count == 0:
        warnings.append("retargeter_still_has_no_mapped_target_chains")
    meaningful_required_chain_names = ["root", "Spine", "LeftClavicle", "RightClavicle", "LeftArm", "RightArm"]
    authored_chain_name_set = {str(item.get("created_chain_name") or item.get("requested_chain_name") or "") for item in authored_chain_records}
    missing_meaningful_source_chain_names = [name for name in meaningful_required_chain_names if name not in authored_chain_name_set]
    missing_meaningful_mapped_chain_names = [name for name in meaningful_required_chain_names if name not in exact_named_mapped_chain_names]
    if missing_meaningful_source_chain_names:
        warnings.append(f"meaningful_source_chains_missing:{','.join(missing_meaningful_source_chain_names)}")
    if exact_named_mapped_chain_count == 0:
        warnings.append("retargeter_has_no_exact_named_chain_mappings")
    if exact_named_mapped_chain_count < 4:
        warnings.append("retargeter_exact_named_chain_mapping_insufficient_for_upper_body_preview")

    ready_for_animation_retry = bool(exact_named_mapped_chain_count >= 4 and not missing_meaningful_mapped_chain_names[:4])
    recommended_next_step_id = "retry_animation_preview_with_retargeter" if ready_for_animation_retry else "refine_source_chain_mapping"
    recommended_next_step_reason = (
        "The PMX source rig now has enough exact-named upper-body chain mappings to justify retrying animation preview through the retargeter."
        if ready_for_animation_retry
        else "The PMX source rig is no longer blank, but its exact-named upper-body chain mappings are still incomplete."
    )

    return {
        "status": "pass" if not errors else "fail",
        "source_ik_rig_asset_path": canonical_asset_path(source_ik_rig_asset.get_path_name()),
        "retargeter_asset_path": canonical_asset_path(retargeter_asset.get_path_name()),
        "target_ik_rig_asset_path": canonical_asset_path(target_ik_rig_asset.get_path_name()) if target_ik_rig_asset else canonical_asset_path(target_ik_rig_asset_path),
        "source_bone_name_source": bone_name_source,
        "source_bone_count": len(bone_names),
        "source_bone_name_sample": bone_names[:40],
        "removed_chain_names": removed_chain_names,
        "planned_chains": planned_chains,
        "planning_diagnostics": planning_diagnostics,
        "authored_chain_records": authored_chain_records,
        "retarget_root_bone": pelvis_bone,
        "retarget_root_set": retarget_root_set,
        "auto_map_invoked": auto_map_invoked,
        "source_ik_rig_profile": source_profile,
        "target_ik_rig_profile": target_profile,
        "mapped_chain_count": mapped_chain_count,
        "exact_named_mapped_chain_count": exact_named_mapped_chain_count,
        "exact_named_mapped_chain_names": exact_named_mapped_chain_names,
        "meaningful_required_chain_names": meaningful_required_chain_names,
        "missing_meaningful_source_chain_names": missing_meaningful_source_chain_names,
        "missing_meaningful_mapped_chain_names": missing_meaningful_mapped_chain_names,
        "mapped_chain_records": mapped_chain_records,
        "ready_for_animation_retry": ready_for_animation_retry,
        "recommended_next_step_id": recommended_next_step_id,
        "recommended_next_step_reason": recommended_next_step_reason,
        "warnings": warnings,
        "errors": errors,
    }


__all__ = [
    "retarget_preflight",
    "retarget_bootstrap",
    "retarget_author_chains",
]


