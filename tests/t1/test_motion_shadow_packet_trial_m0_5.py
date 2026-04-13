from __future__ import annotations

import sys
from pathlib import Path


PMX_PIPELINE_ROOT = Path(__file__).resolve().parents[2] / "workflows" / "pmx_pipeline"
if str(PMX_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PMX_PIPELINE_ROOT))

from run_motion_shadow_packet_trial_m0_5 import (  # noqa: E402
    PREFERRED_PACKAGE_ID,
    build_retarget_preview_params,
    build_motion_communication_signal,
    build_motion_consumer_result,
    classify_motion_failure_class,
    normalize_motion_execution_warnings,
    select_motion_clip,
    should_run_retarget_author_chains,
)


def test_select_motion_clip_prefers_fixed_trial_package():
    registry_payload = {
        "clips": [
            {
                "package_id": "pkg_other",
                "selection_ready": True,
            },
            {
                "package_id": PREFERRED_PACKAGE_ID,
                "selection_ready": True,
            },
        ]
    }
    manifest_index = {
        "pkg_other": Path("C:/tmp/pkg_other/manifest.json"),
        PREFERRED_PACKAGE_ID: Path(f"C:/tmp/{PREFERRED_PACKAGE_ID}/manifest.json"),
    }

    selected = select_motion_clip(registry_payload, manifest_index)

    assert selected is not None
    assert selected["package_id"] == PREFERRED_PACKAGE_ID


def test_classify_motion_failure_class_marks_packet_issue_as_producer_contract():
    failure_class = classify_motion_failure_class(
        {"handoff_ready": False},
        [{"id": "m0_5_packet_handoff_not_ready"}],
        {},
        {},
    )

    signal = build_motion_communication_signal({"handoff_ready": False}, [], failure_class, "fail")

    assert failure_class == "producer_contract_issue"
    assert signal["owner"] == "toy-yard"


def test_classify_motion_failure_class_marks_conversion_failure_as_aiue_owned():
    import_payload = {
        "status": "fail",
        "success": False,
        "errors": ["motion_bvh_conversion_failed"],
        "result": {"errors": ["motion_bvh_conversion_failed"]},
    }

    failure_class = classify_motion_failure_class(
        {"handoff_ready": True},
        [],
        import_payload,
        {},
    )
    signal = build_motion_communication_signal({"handoff_ready": True}, [], failure_class, "fail")

    assert failure_class == "conversion_failed"
    assert signal["owner"] == "aiue"


def test_build_motion_consumer_result_reports_preview_pass_and_owner_none():
    request_payload = {
        "packet_manifest_path": "C:/tmp/manifest.json",
        "target_skeleton_asset_path": "/Game/Test/SK_Test_Skeleton",
        "host_key": "demo",
    }
    selected_clip = {
        "package_id": PREFERRED_PACKAGE_ID,
        "sample_id": "sample_route-a-3s-turn-hand-ready_797943f40a",
        "clip_id": "clip_turn_ready",
        "pack_version": "v0.2",
    }
    import_payload = {
        "status": "pass",
        "success": True,
        "result": {
            "imported_animation_asset_path": "/Game/AiUE/MotionPackets/AN_Test",
            "target_host_asset_path": "/Game/AiUE/Hosts/BP_Test",
            "target_skeleton_asset_path": "/Game/Test/SK_Test_Skeleton",
            "imported_assets": {
                "import_mode": "source_bundle_fallback",
            },
        },
    }
    preview_payload = {
        "status": "pass",
        "success": True,
        "result": {
            "resolved_animation_asset_path": "/Game/AiUE/Generated/AN_Test_RT",
            "native_animation_pose_evaluation": {
                "pose_changed": True,
            },
            "pose_probe_delta": {
                "moving_bone_count": 12,
            },
            "shots": [
                {
                    "before": {"image_path": "C:/tmp/before.png", "subject_visible": True},
                    "after": {"image_path": "C:/tmp/after.png", "subject_visible": True},
                }
            ],
        },
    }
    communication_signal = {
        "should_contact_toy_yard": False,
        "owner": "none",
        "reason": "motion_consumed_and_previewed",
        "recommended_node": None,
    }

    result = build_motion_consumer_result(
        request_payload,
        selected_clip,
        import_payload,
        "C:/tmp/import.action.json",
        preview_payload,
        "C:/tmp/preview.action.json",
        None,
        communication_signal,
    )

    assert result is not None
    assert result["status"] == "pass"
    assert result["operation"] == "animation_preview"
    assert result["communication_signal"]["owner"] == "none"
    assert result["generated_assets"]["animation_asset_path"] == "/Game/AiUE/MotionPackets/AN_Test"
    assert result["generated_assets"]["import_mode"] == "source_bundle_fallback"
    assert result["preview_evidence"]["pose_changed"] is True


def test_build_retarget_preview_params_translates_bootstrap_outputs_for_preview():
    import_result = {
        "imported_assets": {
            "skeletal_mesh_asset_path": "/Game/AiUE/MotionPackets/Source/SKM_Source",
        }
    }
    bootstrap_result = {
        "source_ik_rig_asset_path": "/Game/AiUE/Retarget/Target/IK_TargetHost",
        "target_ik_rig_asset_path": "/Game/AiUE/Retarget/Source/IK_SourceAnim",
        "source_mesh_asset_path": "/Game/AiUE/Characters/SKM_TargetHost",
        "retargeter_asset_path": "/Game/AiUE/Retarget/Demo/RTG_Source_to_Target",
    }

    params = build_retarget_preview_params(import_result, bootstrap_result)

    assert params["retarget_source_ik_rig_asset_path"] == "/Game/AiUE/Retarget/Source/IK_SourceAnim"
    assert params["retarget_target_ik_rig_asset_path"] == "/Game/AiUE/Retarget/Target/IK_TargetHost"
    assert params["retarget_source_mesh_asset_path"] == "/Game/AiUE/MotionPackets/Source/SKM_Source"
    assert params["retarget_target_mesh_asset_path"] == "/Game/AiUE/Characters/SKM_TargetHost"


def test_should_run_retarget_author_chains_when_bootstrap_has_no_chains_or_mappings():
    assert should_run_retarget_author_chains(
        {
            "mapped_chain_count": 0,
            "source_ik_rig_profile": {"chain_count": 4},
        }
    )
    assert should_run_retarget_author_chains(
        {
            "mapped_chain_count": 5,
            "source_ik_rig_profile": {"chain_count": 0},
        }
    )
    assert not should_run_retarget_author_chains(
        {
            "mapped_chain_count": 5,
            "source_ik_rig_profile": {"chain_count": 6},
        }
    )


def test_normalize_motion_execution_warnings_drops_stale_bootstrap_retarget_warnings():
    bootstrap_payload = {
        "warnings": ["source_ik_rig_has_no_retarget_chains", "retargeter_has_no_mapped_target_chains"],
        "result": {
            "warnings": ["source_ik_rig_has_no_retarget_chains", "retargeter_has_no_mapped_target_chains"],
        },
    }
    author_chains_payload = {
        "warnings": ["source_chain_unresolved:Neck"],
        "result": {
            "ready_for_animation_retry": True,
            "warnings": ["source_chain_unresolved:Neck"],
        },
    }

    warnings = normalize_motion_execution_warnings({}, bootstrap_payload, author_chains_payload, {})

    assert "source_ik_rig_has_no_retarget_chains" not in warnings
    assert "retargeter_has_no_mapped_target_chains" not in warnings
    assert "source_chain_unresolved:Neck" in warnings


def test_normalize_motion_execution_warnings_drops_operational_notes_after_success():
    import_payload = {
        "warnings": [
            "explicit_target_skeleton_resolved_by_folder_scan:/Game/PMXPipeline/Characters/Test/Meshes",
            "interchange_fbx_import_disabled_for_motion_import",
            "import_completed_without_animsequence_object_path",
            "target_skeleton_import_failed_falling_back_to_source_bundle",
        ],
        "result": {
            "imported_assets": {
                "import_mode": "source_bundle_fallback",
            },
            "warnings": [
                "explicit_target_skeleton_resolved_by_folder_scan:/Game/PMXPipeline/Characters/Test/Meshes",
                "interchange_fbx_import_disabled_for_motion_import",
                "import_completed_without_animsequence_object_path",
                "target_skeleton_import_failed_falling_back_to_source_bundle",
            ],
        },
    }
    preview_payload = {
        "warnings": ["animation_blueprint_library_unavailable"],
        "result": {
            "native_animation_pose_evaluation": {
                "success": True,
                "pose_changed": True,
            },
            "warnings": ["animation_blueprint_library_unavailable"],
        },
    }

    warnings = normalize_motion_execution_warnings(import_payload, {}, {}, preview_payload)

    assert warnings == []
