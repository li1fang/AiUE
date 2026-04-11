from __future__ import annotations

from .common import *
from .retarget_profile import *


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

    pelvis_bone = pick_best_bone_name(bone_names, [["pelvis"], ["hips"], ["下半身"], ["腰"], ["center"]])
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


__all__ = ["retarget_author_chains"]
