from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from aiue_core.schema_utils import load_json, write_json
from aiue_t1.evidence_pack import build_evidence_pack


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures"
REPORT_FIXTURES = FIXTURE_ROOT / "reports"
WORKBENCH_SCRIPT = REPO_ROOT / "tools" / "run_t2_workbench.ps1"
DEMO_REQUEST_SCRIPT = REPO_ROOT / "tools" / "run_e2_demo_request.ps1"
DEFAULT_E2_SESSION_NAME = "playable_demo_e2_session.json"
DEFAULT_E2_CONTROL_STATE_NAME = "playable_demo_e2_control_state.json"


def write_fixture_feature_ledger(repo_root: Path) -> Path:
    ledger_path = repo_root / "docs" / "governance" / "feature_ledger_cn.v1.json"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        ledger_path,
        {
            "ledger_version": "v1",
            "lines": [
                {
                    "line_id": "validation_quality",
                    "title_cn": "验证与质量线",
                    "items": [
                        {
                            "item_id": "q5a_edge_band_burial_detection",
                            "title_cn": "Q5A 黄边边缘压埋检测",
                            "status": "规划",
                            "priority": "未知",
                            "triage_state": "待分诊",
                            "evidence_gate_ids": ["visible_conflict_inspection_q5a", "volumetric_inspection_q5c_lite"],
                        }
                    ],
                },
                {
                    "line_id": "body_platform",
                    "title_cn": "参数化人体平台线",
                    "items": [
                        {
                            "item_id": "c2_canonical_fusion_fixture",
                            "title_cn": "C2 Canonical Fusion Fixture",
                            "status": "开发中",
                            "priority": "P1",
                            "triage_state": "进行中",
                            "evidence_gate_ids": ["canonical_fusion_fixture_c2"],
                        }
                    ],
                },
            ],
        },
    )
    return ledger_path


def materialize_report_fixtures(target_root: Path, *, include_governance: bool = True) -> Path:
    target_root.mkdir(parents=True, exist_ok=True)
    placeholder_root = str(FIXTURE_ROOT).replace("\\", "/")
    for report_path in REPORT_FIXTURES.glob("*.json"):
        if not include_governance and report_path.name in {
            "latest_dynamic_balance_governance_progress_report.json",
            "latest_test_governance_round1_report.json",
        }:
            continue
        payload = load_json(report_path)
        serialized = json.dumps(payload)
        serialized = serialized.replace("__FIXTURE_ROOT__", placeholder_root)
        write_json(target_root / report_path.name, json.loads(serialized))
    return target_root


def write_fixture_q5c_report(verification_root: Path) -> Path:
    verification_root.mkdir(parents=True, exist_ok=True)
    image_path = str((FIXTURE_ROOT / "images" / "front.ppm").resolve())
    q5c_report_path = verification_root / "latest_volumetric_inspection_q5c_lite_report.json"
    write_json(
        q5c_report_path,
        {
            "gate_id": "volumetric_inspection_q5c_lite",
            "status": "pass",
            "generated_at_utc": "2026-04-12T01:00:00+00:00",
            "counts": {
                "required_package_count": 1,
                "resolved_package_count": 1,
                "packages": 1,
                "passing_packages": 1,
                "packages_without_penetration_clusters": 1,
                "packages_with_borderline_fit": 0,
                "packages_with_floating_failures": 0,
                "packages_with_penetration_failures": 0,
                "packages_with_mixed_failures": 0,
            },
            "per_package_results": [
                {
                    "package_id": "pkg_alpha",
                    "status": "pass",
                    "fit_diagnostic_class": "pass_stable",
                    "embedding_ratio": 0.48,
                    "floating_ratio": 0.02,
                    "penetration_ratio": 0.0,
                    "diagnostic_signals": {
                        "embedding_ratio_below_threshold": False,
                        "floating_ratio_exceeded": False,
                        "penetration_ratio_exceeded": False,
                        "borderline_fit": False,
                    },
                    "threshold_deltas": {
                        "embedding_ratio_delta_to_min": 0.18,
                        "floating_ratio_delta_to_max": -0.18,
                        "penetration_ratio_delta_to_max": -0.02,
                    },
                    "failed_requirements": [],
                    "artifacts": {
                        "q5c_debug_image_path": image_path,
                    },
                }
            ],
        },
    )
    return q5c_report_path


def write_fixture_q5c_contrast_report(verification_root: Path) -> Path:
    verification_root.mkdir(parents=True, exist_ok=True)
    baseline_image_path = str((FIXTURE_ROOT / "images" / "front.ppm").resolve())
    best_pass_image_path = str((FIXTURE_ROOT / "images" / "side.ppm").resolve())
    closest_fail_image_path = str((FIXTURE_ROOT / "images" / "after.ppm").resolve())
    report_path = verification_root / "latest_q5c_lite_contrast_lab_report.json"
    write_json(
        report_path,
        {
            "gate_id": "q5c_lite_contrast_lab",
            "status": "pass",
            "generated_at_utc": "2026-04-12T01:10:00+00:00",
            "fixed_execution_profile": {
                "required_reference_cases": [
                    "baseline_current",
                    "best_pass_reference",
                    "closest_fail_reference",
                ]
            },
            "per_package_results": [
                {
                    "package_id": "pkg_alpha",
                    "status": "pass",
                    "selected_case_ids": [
                        "baseline_current",
                        "best_pass_reference",
                        "closest_fail_reference",
                    ],
                    "search_summary": {
                        "explored_case_count": 11,
                        "pass_case_count": 6,
                        "fail_case_count": 5,
                    },
                    "case_results": [
                        {
                            "case_id": "baseline_current",
                            "status": "pass",
                            "fit_diagnostic_class": "pass_stable",
                            "risk_band": "watch",
                            "risk_reason": "penetration_ratio_margin_to_failure:0.0200",
                            "delta_z": 0.0,
                            "closest_margin_metric": "penetration_ratio_margin_to_failure",
                            "closest_margin_value": 0.02,
                            "analysis": {
                                "quality_class": "watch",
                                "embedding_ratio": 0.48,
                                "floating_ratio": 0.02,
                                "penetration_ratio": 0.0,
                                "local_fit_volume": 1200.0,
                            },
                            "artifacts": {
                                "debug_image_path": baseline_image_path,
                            },
                        },
                        {
                            "case_id": "best_pass_reference",
                            "status": "pass",
                            "fit_diagnostic_class": "pass_stable",
                            "risk_band": "watch",
                            "risk_reason": "penetration_ratio_margin_to_failure:0.0200",
                            "delta_z": -30.0,
                            "closest_margin_metric": "penetration_ratio_margin_to_failure",
                            "closest_margin_value": 0.02,
                            "analysis": {
                                "quality_class": "watch",
                                "embedding_ratio": 0.52,
                                "floating_ratio": 0.01,
                                "penetration_ratio": 0.0,
                                "local_fit_volume": 1260.0,
                            },
                            "artifacts": {
                                "debug_image_path": best_pass_image_path,
                            },
                        },
                        {
                            "case_id": "closest_fail_reference",
                            "status": "fail",
                            "fit_diagnostic_class": "floating_fit_out_of_range",
                            "risk_band": "fail",
                            "risk_reason": "floating_ratio_margin_to_failure:-0.0407",
                            "delta_z": 20.0,
                            "closest_margin_metric": "floating_ratio_margin_to_failure",
                            "closest_margin_value": -0.0407,
                            "analysis": {
                                "quality_class": "fail",
                                "embedding_ratio": 0.31,
                                "floating_ratio": 0.0607,
                                "penetration_ratio": 0.01,
                                "local_fit_volume": 980.0,
                            },
                            "artifacts": {
                                "debug_image_path": closest_fail_image_path,
                            },
                        },
                    ],
                }
            ],
        },
    )
    return report_path


def write_fixture_m1_report(verification_root: Path) -> Path:
    verification_root.mkdir(parents=True, exist_ok=True)
    front_image_path = str((FIXTURE_ROOT / "images" / "front.ppm").resolve())
    side_image_path = str((FIXTURE_ROOT / "images" / "side.ppm").resolve())
    report_path = verification_root / "latest_material_texture_proof_m1_report.json"
    write_json(
        report_path,
        {
            "gate_id": "material_texture_proof_m1",
            "status": "pass",
            "generated_at_utc": "2026-04-12T02:00:00+00:00",
            "per_package_results": [
                {
                    "package_id": "pkg_alpha",
                    "sample_id": "fixture_alpha",
                    "status": "pass",
                    "import_evidence": {
                        "character": {
                            "status": "pass",
                            "expected_texture_count": 13,
                            "imported_texture_count": 13,
                        },
                        "default_weapon": {
                            "status": "pass",
                            "expected_texture_count": 3,
                            "imported_texture_count": 3,
                        },
                    },
                    "host_visual_evidence": {
                        "status": "pass",
                        "material_evidence": {
                            "main_mesh": {
                                "material_slot_count": 30,
                                "material_asset_paths": [
                                    "/Game/Fixture/Materials/MI_Alpha_Body",
                                    "/Game/Fixture/Materials/MI_Alpha_Face",
                                ],
                            },
                            "weapon_mesh": {
                                "material_slot_count": 1,
                                "material_asset_paths": [
                                    "/Game/Fixture/Materials/MI_Alpha_Weapon",
                                ],
                            },
                        },
                        "shots": [
                            {
                                "shot_id": "front",
                                "image_path": front_image_path,
                            },
                            {
                                "shot_id": "side",
                                "image_path": side_image_path,
                            },
                        ],
                    },
                    "failed_requirements": [],
                }
            ],
        },
    )
    return report_path


def write_fixture_e2b_report(verification_root: Path) -> Path:
    verification_root.mkdir(parents=True, exist_ok=True)
    front_image_path = str((FIXTURE_ROOT / "images" / "front.ppm").resolve())
    side_image_path = str((FIXTURE_ROOT / "images" / "side.ppm").resolve())
    after_image_path = str((FIXTURE_ROOT / "images" / "after.ppm").resolve())
    report_path = verification_root / "latest_playable_demo_e2b_credible_showcase_report.json"
    write_json(
        report_path,
        {
            "gate_id": "playable_demo_e2b_credible_showcase",
            "status": "pass",
            "generated_at_utc": "2026-04-12T02:10:00+00:00",
            "per_package_results": [
                {
                    "package_id": "pkg_alpha",
                    "status": "pass",
                    "hero_shot": {
                        "before_image_path": front_image_path,
                        "after_image_path": side_image_path,
                    },
                    "action_preview": {
                        "status": "pass",
                        "key_image_paths": {
                            "primary_before": front_image_path,
                            "primary_after": after_image_path,
                        },
                    },
                    "animation_preview": {
                        "status": "pass",
                        "key_image_paths": {
                            "primary_before": side_image_path,
                            "primary_after": after_image_path,
                        },
                    },
                }
            ],
        },
    )
    return report_path


def write_fixture_e2c_report(verification_root: Path, *, status: str = "pass") -> Path:
    verification_root.mkdir(parents=True, exist_ok=True)
    front_image_path = str((FIXTURE_ROOT / "images" / "front.ppm").resolve())
    side_image_path = str((FIXTURE_ROOT / "images" / "side.ppm").resolve())
    after_image_path = str((FIXTURE_ROOT / "images" / "after.ppm").resolve())
    report_path = verification_root / "latest_playable_demo_e2c_credible_showcase_polish_report.json"
    write_json(
        report_path,
        {
            "gate_id": "playable_demo_e2c_credible_showcase_polish",
            "status": status,
            "generated_at_utc": "2026-04-12T04:10:00+00:00",
            "counts": {
                "resolved_package_count": 1,
                "passing_packages": 1,
                "compare_ready_packages": 1,
                "replay_ready_packages": 1,
                "history_ready_packages": 1,
                "diversity_ready_packages": 1,
                "packages_with_material_reference": 1,
                "packages_with_hero_shots": 1,
            },
            "consumed_reports": {
                "e2b": str((verification_root / "latest_playable_demo_e2b_credible_showcase_report.json").resolve()),
                "dv2": str((verification_root / "latest_diversity_matrix_dv2_report.json").resolve()),
            },
            "artifacts": {
                "polish_state_path": str((verification_root.parent / "Saved" / "demo" / "e2" / "latest" / "playable_demo_e2_polish_state.json").resolve()),
            },
            "per_package_results": [
                {
                    "package_id": "pkg_alpha",
                    "sample_id": "fixture_alpha",
                    "status": status,
                    "key_images": {
                        "hero_before": front_image_path,
                        "hero_after": side_image_path,
                        "action_after": after_image_path,
                        "animation_after": side_image_path,
                        "compare_action_after": after_image_path,
                        "compare_animation_after": side_image_path,
                    },
                    "polish_summary": {
                        "hero_ready": True,
                        "material_ready": True,
                        "replay_ready": True,
                        "compare_ready": True,
                        "history_ready": True,
                        "diversity_ready": True,
                    },
                }
            ],
        },
    )
    return report_path


def write_fixture_a1_report(verification_root: Path, *, status: str = "pass") -> Path:
    verification_root.mkdir(parents=True, exist_ok=True)
    front_image_path = str((FIXTURE_ROOT / "images" / "front.ppm").resolve())
    after_image_path = str((FIXTURE_ROOT / "images" / "after.ppm").resolve())
    report_path = verification_root / "latest_action_candidate_provider_a1_report.json"
    write_json(
        report_path,
        {
            "gate_id": "action_candidate_provider_a1",
            "status": status,
            "generated_at_utc": "2026-04-12T05:10:00+00:00",
            "counts": {
                "resolved_package_count": 1,
                "passing_packages": 1,
                "resolved_candidate_count": 1,
                "passing_candidates": 1,
                "candidate_source_count": 1,
            },
            "external_candidate_sources": [
                {
                    "provider_name": "fixture_provider_v1",
                    "source_id": "fixture_provider_from_session",
                    "source_kind": "fixture_session_derivation",
                    "candidate_count": 1,
                    "package_ids": ["pkg_alpha"],
                }
            ],
            "artifacts": {
                "provider_context_path": str((verification_root.parent / "Saved" / "demo" / "a1" / "latest" / "action_candidate_provider_context.json").resolve()),
                "candidate_manifest_path": str((verification_root.parent / "Saved" / "demo" / "a1" / "latest" / "action_candidate_manifest.json").resolve()),
                "provider_state_path": str((verification_root.parent / "Saved" / "demo" / "a1" / "latest" / "action_candidate_provider_state.json").resolve()),
            },
            "per_package_results": [
                {
                    "package_id": "pkg_alpha",
                    "sample_id": "fixture_alpha",
                    "candidate_id": "candidate_MM_Attack_01",
                    "selected_animation_preset_id": "MM_Attack_01",
                    "status": status,
                    "warning_flags": [],
                    "credibility_summary": {
                        "subject_visible": True,
                        "before_image_present": True,
                        "after_image_present": True,
                        "animation_pose_verified": True,
                        "external_motion_verified": True,
                        "warning_flags": [],
                    },
                }
            ],
            "per_candidate_results": [
                {
                    "package_id": "pkg_alpha",
                    "sample_id": "fixture_alpha",
                    "provider_name": "fixture_provider_v1",
                    "source_id": "fixture_provider_from_session",
                    "candidate_id": "candidate_MM_Attack_01",
                    "candidate_payload_kind": "session_animation_preset_ref",
                    "selected_animation_preset_id": "MM_Attack_01",
                    "status": status,
                    "warning_flags": [],
                    "key_images": {
                        "primary_before": front_image_path,
                        "primary_after": after_image_path,
                    },
                    "credibility_summary": {
                        "subject_visible": True,
                        "before_image_present": True,
                        "after_image_present": True,
                        "animation_pose_verified": True,
                        "external_motion_verified": True,
                        "warning_flags": [],
                    },
                }
            ],
        },
    )
    return report_path


def write_fixture_pv1_report(verification_root: Path, *, status: str = "attention") -> Path:
    verification_root.mkdir(parents=True, exist_ok=True)
    report_path = verification_root / "latest_manual_playable_demo_validation_pv1_report.json"
    write_json(
        report_path,
        {
            "gate_id": "manual_playable_demo_validation_pv1",
            "status": status,
            "generated_at_utc": "2026-04-12T02:20:00+00:00",
            "operator": "fixture_user",
            "checked_package_ids": ["pkg_alpha"],
            "checked_package_count": 1,
            "checked_packages": [
                {
                    "package_id": "pkg_alpha",
                    "action_preset_id": "showcase_root_translate_and_turn",
                    "animation_preset_id": "MM_Attack_01",
                }
            ],
            "notes": "fixture",
        },
    )
    return report_path


def write_fixture_c0_report(verification_root: Path, *, status: str = "pass") -> Path:
    verification_root.mkdir(parents=True, exist_ok=True)
    report_path = verification_root / "latest_modular_morphology_inventory_c0_report.json"
    write_json(
        report_path,
        {
            "gate_id": "modular_morphology_inventory_c0",
            "status": status,
            "generated_at_utc": "2026-04-14T02:00:00+00:00",
            "source_root": str((verification_root.parent / "body_source").resolve()),
            "counts": {
                "module_count": 6,
                "classified_module_count": 6,
                "unknown_module_count": 0,
                "family_count": 2,
                "candidate_fixture_family_count": 1,
            },
            "module_kind_counts": {
                "head": 2,
                "hair": 1,
                "bust_variant": 1,
                "core_torso_arm": 1,
                "leg_profile": 1,
            },
            "canonical_fixture_family_id": "family_alpha",
            "candidate_fixture_family_ids": ["family_alpha"],
            "per_family_results": [
                {
                    "family_id": "family_alpha",
                    "family_root": str((verification_root.parent / "body_source" / "family_alpha").resolve()),
                    "module_count": 5,
                    "classified_module_count": 5,
                    "module_kind_counts": {
                        "head": 1,
                        "hair": 1,
                        "bust_variant": 1,
                        "core_torso_arm": 1,
                        "leg_profile": 1,
                    },
                    "module_ids_by_kind": {
                        "head": ["family_alpha/head/head_nohair"],
                        "hair": ["family_alpha/hair/front_hair"],
                        "bust_variant": ["family_alpha/bust/bust_large"],
                        "core_torso_arm": ["family_alpha/core/core_torso_arm"],
                        "leg_profile": ["family_alpha/legs/left_thigh"],
                    },
                    "required_axes_present": {
                        "head": True,
                        "bust_variant": True,
                        "leg_profile": True,
                        "core_torso_arm": True,
                    },
                    "optional_axes_present": {
                        "hair": True,
                    },
                    "candidate_fixture_family": True,
                },
                {
                    "family_id": "family_beta",
                    "family_root": str((verification_root.parent / "body_source" / "family_beta").resolve()),
                    "module_count": 1,
                    "classified_module_count": 1,
                    "module_kind_counts": {
                        "head": 1,
                    },
                    "module_ids_by_kind": {
                        "head": ["family_beta/head/head_alt"],
                    },
                    "required_axes_present": {
                        "head": True,
                        "bust_variant": False,
                        "leg_profile": False,
                        "core_torso_arm": False,
                    },
                    "optional_axes_present": {
                        "hair": False,
                    },
                    "candidate_fixture_family": False,
                },
            ],
            "failed_requirements": [],
        },
    )
    return report_path


def write_fixture_c1_report(verification_root: Path, *, status: str = "pass") -> Path:
    verification_root.mkdir(parents=True, exist_ok=True)
    report_path = verification_root / "latest_parametric_body_contract_c1_report.json"
    write_json(
        report_path,
        {
            "gate_id": "parametric_body_contract_c1",
            "status": status,
            "generated_at_utc": "2026-04-14T03:00:00+00:00",
            "body_family_id": "family_alpha",
            "contract_id": "family_alpha::parametric_body_contract_c1",
            "parametric_body_contract": {
                "contract_id": "family_alpha::parametric_body_contract_c1",
                "contract_version": "c1",
                "body_family_id": "family_alpha",
                "core_module_id": "family_alpha/core/core_torso_arm",
                "supported_head_ids": ["family_alpha/head/head_nohair"],
                "supported_bust_classes": ["family_alpha/bust/bust_large"],
                "supported_leg_length_profiles": ["family_alpha/legs/left_thigh"],
                "compatible_hair_ids": ["family_alpha/hair/front_hair"],
                "fusion_recipe_id": "fusion_recipe::family_alpha::canonical_v1",
                "rig_profile_id": "rig_profile::family_alpha::canonical_v1",
                "material_profile_id": "material_profile::family_alpha::canonical_v1",
                "fixed_core": {
                    "module_kind": "core_torso_arm",
                    "runtime_module_swaps_supported": False,
                },
                "supported_axes": {
                    "head": {
                        "axis_id": "head",
                        "selection_kind": "discrete",
                        "required": True,
                        "supported_values": ["family_alpha/head/head_nohair"],
                    },
                    "bust": {
                        "axis_id": "bust",
                        "selection_kind": "discrete",
                        "required": True,
                        "supported_values": ["family_alpha/bust/bust_large"],
                    },
                    "leg_length": {
                        "axis_id": "leg_length",
                        "selection_kind": "discrete",
                        "required": True,
                        "supported_values": ["family_alpha/legs/left_thigh"],
                    },
                    "hair": {
                        "axis_id": "hair",
                        "selection_kind": "discrete_optional",
                        "required": False,
                        "supported_values": ["family_alpha/hair/front_hair"],
                    },
                },
                "combination_policy": {
                    "domain_profile": "narrow_beauty_family_only",
                    "runtime_raw_fragment_swaps_supported": False,
                    "hair_in_core_contract": False,
                    "notes": [
                        "core torso and arms stay fixed in C1",
                        "raw scan modules are not runtime-consumable in C1",
                    ],
                },
                "selected_family_summary": {
                    "family_id": "family_alpha",
                    "family_root": str((verification_root.parent / "body_source" / "family_alpha").resolve()),
                    "module_count": 5,
                    "classified_module_count": 5,
                    "module_kind_counts": {
                        "head": 1,
                        "hair": 1,
                        "bust_variant": 1,
                        "core_torso_arm": 1,
                        "leg_profile": 1,
                    },
                    "module_ids_by_kind": {
                        "head": ["family_alpha/head/head_nohair"],
                        "hair": ["family_alpha/hair/front_hair"],
                        "bust_variant": ["family_alpha/bust/bust_large"],
                        "core_torso_arm": ["family_alpha/core/core_torso_arm"],
                        "leg_profile": ["family_alpha/legs/left_thigh"],
                    },
                    "required_axes_present": {
                        "head": True,
                        "bust_variant": True,
                        "leg_profile": True,
                        "core_torso_arm": True,
                    },
                    "optional_axes_present": {
                        "hair": True,
                    },
                    "candidate_fixture_family": True,
                },
            },
            "counts": {
                "supported_head_count": 1,
                "supported_bust_class_count": 1,
                "supported_leg_length_profile_count": 1,
                "compatible_hair_count": 1,
            },
            "source_inventory_summary": {
                "source_root": str((verification_root.parent / "body_source").resolve()),
                "counts": {
                    "module_count": 6,
                    "classified_module_count": 6,
                    "unknown_module_count": 0,
                    "family_count": 2,
                    "candidate_fixture_family_count": 1,
                },
                "module_kind_counts": {
                    "head": 2,
                    "hair": 1,
                    "bust_variant": 1,
                    "core_torso_arm": 1,
                    "leg_profile": 1,
                },
                "canonical_fixture_family_id": "family_alpha",
                "per_family_results": [
                    {
                        "family_id": "family_alpha",
                        "family_root": str((verification_root.parent / "body_source" / "family_alpha").resolve()),
                        "module_count": 5,
                        "classified_module_count": 5,
                        "module_kind_counts": {
                            "head": 1,
                            "hair": 1,
                            "bust_variant": 1,
                            "core_torso_arm": 1,
                            "leg_profile": 1,
                        },
                        "module_ids_by_kind": {
                            "head": ["family_alpha/head/head_nohair"],
                            "hair": ["family_alpha/hair/front_hair"],
                            "bust_variant": ["family_alpha/bust/bust_large"],
                            "core_torso_arm": ["family_alpha/core/core_torso_arm"],
                            "leg_profile": ["family_alpha/legs/left_thigh"],
                        },
                        "required_axes_present": {
                            "head": True,
                            "bust_variant": True,
                            "leg_profile": True,
                            "core_torso_arm": True,
                        },
                        "optional_axes_present": {
                            "hair": True,
                        },
                        "candidate_fixture_family": True,
                    },
                    {
                        "family_id": "family_beta",
                        "family_root": str((verification_root.parent / "body_source" / "family_beta").resolve()),
                        "module_count": 1,
                        "classified_module_count": 1,
                        "module_kind_counts": {
                            "head": 1,
                        },
                        "module_ids_by_kind": {
                            "head": ["family_beta/head/head_alt"],
                        },
                        "required_axes_present": {
                            "head": True,
                            "bust_variant": False,
                            "leg_profile": False,
                            "core_torso_arm": False,
                        },
                        "optional_axes_present": {
                            "hair": False,
                        },
                        "candidate_fixture_family": False,
                    },
                ],
            },
            "failed_requirements": [],
        },
    )
    return report_path


def write_fixture_c2_report(verification_root: Path, *, status: str = "pass") -> Path:
    verification_root.mkdir(parents=True, exist_ok=True)
    report_path = verification_root / "latest_canonical_fusion_fixture_c2_report.json"
    write_json(
        report_path,
        {
            "gate_id": "canonical_fusion_fixture_c2",
            "status": status,
            "generated_at_utc": "2026-04-14T04:00:00+00:00",
            "body_family_id": "family_alpha",
            "fixture_id": "family_alpha::lower_body_core_hi",
            "canonical_fusion_fixture": {
                "source_root": str((verification_root.parent / "fusion_fixture_drop" / "family_alpha_lower_body").resolve()),
                "manifest_path": str((verification_root.parent / "fusion_fixture_drop" / "family_alpha_lower_body" / "canonical_fusion_fixture_manifest.json").resolve()),
                "manifest_present": True,
                "fixture_id": "family_alpha::lower_body_core_hi",
                "body_family_id": "family_alpha",
                "fixture_scope": "lower_body_core",
                "source_module_ids": ["family_alpha/core_lower_body_hi"],
                "primary_mesh_relative_path": "meshes/lower_body_core_hi.fbx",
                "primary_mesh_abs_path": str((verification_root.parent / "fusion_fixture_drop" / "family_alpha_lower_body" / "meshes" / "lower_body_core_hi.fbx").resolve()),
                "primary_mesh_format": "fbx",
                "discovered_mesh_relative_paths": ["meshes/lower_body_core_hi.fbx"],
                "discovered_texture_relative_paths": [],
                "material_bundle_relative_root": "materials",
                "texture_relative_paths": [],
                "exporter": {
                    "tool": "houdini",
                    "version": "20.5",
                    "network": "/obj/aiue_body_platform/c2_lower_body_core",
                },
                "coordinate_system": {
                    "linear_unit": "cm",
                    "up_axis": "z",
                    "forward_axis": "x",
                },
                "quality": {
                    "topology_state": "scan_raw_cleaned",
                    "uv_state": "source_preserved",
                    "watertight_expected": False,
                    "runtime_ready": False,
                },
                "fusion_recipe_id": "houdini_recipe::family_alpha::lower_body_core_v1",
                "rig_profile_id": "rig_profile::family_alpha::pending",
                "material_profile_id": "material_profile::family_alpha::scan_source_v1",
                "counts": {
                    "discovered_mesh_count": 1,
                    "discovered_texture_count": 0,
                    "declared_texture_count": 0,
                    "source_module_count": 1,
                },
            },
            "counts": {
                "discovered_mesh_count": 1,
                "discovered_texture_count": 0,
                "declared_texture_count": 0,
                "source_module_count": 1,
            },
            "source_inventory_summary": {
                "source_root": str((verification_root.parent / "body_source").resolve()),
                "counts": {
                    "module_count": 6,
                    "classified_module_count": 6,
                    "unknown_module_count": 0,
                    "family_count": 2,
                    "candidate_fixture_family_count": 1,
                },
                "module_kind_counts": {
                    "head": 2,
                    "hair": 1,
                    "bust_variant": 1,
                    "core_torso_arm": 1,
                    "leg_profile": 1,
                },
                "canonical_fixture_family_id": "family_alpha",
                "per_family_results": [
                    {
                        "family_id": "family_alpha",
                        "family_root": str((verification_root.parent / "body_source" / "family_alpha").resolve()),
                        "module_count": 5,
                        "classified_module_count": 5,
                        "module_kind_counts": {
                            "head": 1,
                            "hair": 1,
                            "bust_variant": 1,
                            "core_torso_arm": 1,
                            "leg_profile": 1,
                        },
                        "module_ids_by_kind": {
                            "head": ["family_alpha/head/head_nohair"],
                            "hair": ["family_alpha/hair/front_hair"],
                            "bust_variant": ["family_alpha/bust/bust_large"],
                            "core_torso_arm": ["family_alpha/core/core_torso_arm"],
                            "leg_profile": ["family_alpha/legs/left_thigh"],
                        },
                        "required_axes_present": {
                            "head": True,
                            "bust_variant": True,
                            "leg_profile": True,
                            "core_torso_arm": True,
                        },
                        "optional_axes_present": {
                            "hair": True,
                        },
                        "candidate_fixture_family": True,
                    },
                    {
                        "family_id": "family_beta",
                        "family_root": str((verification_root.parent / "body_source" / "family_beta").resolve()),
                        "module_count": 1,
                        "classified_module_count": 1,
                        "module_kind_counts": {
                            "head": 1,
                        },
                        "module_ids_by_kind": {
                            "head": ["family_beta/head/head_alt"],
                        },
                        "required_axes_present": {
                            "head": True,
                            "bust_variant": False,
                            "leg_profile": False,
                            "core_torso_arm": False,
                        },
                        "optional_axes_present": {
                            "hair": False,
                        },
                        "candidate_fixture_family": False,
                    }
                ]
            },
            "failed_requirements": [],
        },
    )
    return report_path


def write_fixture_dv1_report(verification_root: Path, *, status: str = "pass") -> Path:
    verification_root.mkdir(parents=True, exist_ok=True)
    front_image_path = str((FIXTURE_ROOT / "images" / "front.ppm").resolve())
    after_image_path = str((FIXTURE_ROOT / "images" / "after.ppm").resolve())
    report_path = verification_root / "latest_diversity_matrix_dv1_report.json"
    write_json(
        report_path,
        {
            "gate_id": "diversity_matrix_dv1",
            "status": status,
            "generated_at_utc": "2026-04-12T02:30:00+00:00",
            "distinct_counts": {
                "character_variant_diversity": 2,
                "weapon_variant_diversity": 2,
                "clothing_fixture_diversity": 1,
                "fx_fixture_diversity": 1,
                "action_variation": 1,
                "animation_variation": 3,
            },
            "coverage_axes": [
                {
                    "axis_id": "character_variant_diversity",
                    "status": "covered",
                    "distinct_count": 2,
                    "observed_values": ["pkg_alpha", "pkg_beta"],
                    "summary": "DV1 currently verifies 2 distinct character bundles on the automated demo-ready path.",
                },
                {
                    "axis_id": "weapon_variant_diversity",
                    "status": "covered",
                    "distinct_count": 2,
                    "observed_values": ["weapon_alpha", "weapon_beta"],
                    "summary": "DV1 currently verifies 2 distinct weapon bundles on the automated demo-ready path.",
                },
                {
                    "axis_id": "clothing_fixture_diversity",
                    "status": "partial",
                    "distinct_count": 1,
                    "observed_values": ["fixture_hair"],
                    "summary": "DV1 currently verifies 1 distinct clothing fixture on the automated demo-ready path.",
                },
                {
                    "axis_id": "fx_fixture_diversity",
                    "status": "partial",
                    "distinct_count": 1,
                    "observed_values": ["fixture_fx"],
                    "summary": "DV1 currently verifies 1 distinct FX fixture on the automated demo-ready path.",
                },
                {
                    "axis_id": "action_variation",
                    "status": "partial",
                    "distinct_count": 1,
                    "observed_values": ["showcase_root_translate_and_turn"],
                    "summary": "DV1 currently verifies 1 distinct action preset on the automated demo-ready path.",
                },
                {
                    "axis_id": "animation_variation",
                    "status": "covered",
                    "distinct_count": 3,
                    "observed_values": ["MM_Attack_01", "MM_Idle", "MF_Unarmed_Walk_Fwd"],
                    "summary": "DV1 currently verifies 3 distinct animation presets on the automated demo-ready path.",
                },
            ],
            "per_package_results": [
                {
                    "package_id": "pkg_alpha",
                    "status": "pass",
                    "action_matrix_runs": [
                        {
                            "status": "pass",
                            "selected_action_preset_id": "showcase_root_translate_and_turn",
                            "key_image_paths": {
                                "primary_after": after_image_path,
                            },
                        }
                    ],
                    "animation_matrix_runs": [
                        {
                            "status": "pass",
                            "selected_animation_preset_id": "MM_Attack_01",
                            "key_image_paths": {
                                "primary_after": front_image_path,
                            },
                        }
                    ],
                }
            ],
        },
    )
    return report_path


def write_fixture_dv2_report(verification_root: Path, *, status: str = "pass") -> Path:
    verification_root.mkdir(parents=True, exist_ok=True)
    front_image_path = str((FIXTURE_ROOT / "images" / "front.ppm").resolve())
    after_image_path = str((FIXTURE_ROOT / "images" / "after.ppm").resolve())
    report_path = verification_root / "latest_diversity_matrix_dv2_report.json"
    write_json(
        report_path,
        {
            "gate_id": "diversity_matrix_dv2",
            "status": status,
            "generated_at_utc": "2026-04-12T03:00:00+00:00",
            "distinct_counts": {
                "character_variant_diversity": 2,
                "weapon_variant_diversity": 2,
                "clothing_fixture_diversity": 2,
                "fx_fixture_diversity": 2,
                "action_variation": 2,
                "animation_variation": 3,
            },
            "coverage_axes": [
                {
                    "axis_id": "character_variant_diversity",
                    "status": "covered",
                    "distinct_count": 2,
                    "observed_values": ["pkg_alpha", "pkg_beta"],
                    "summary": "DV2 currently verifies 2 distinct character bundles on the automated demo-ready path.",
                },
                {
                    "axis_id": "weapon_variant_diversity",
                    "status": "covered",
                    "distinct_count": 2,
                    "observed_values": ["weapon_alpha", "weapon_beta"],
                    "summary": "DV2 currently verifies 2 distinct weapon bundles on the automated demo-ready path.",
                },
                {
                    "axis_id": "clothing_fixture_diversity",
                    "status": "covered",
                    "distinct_count": 2,
                    "observed_values": ["fixture_hair", "fixture_brow_cards"],
                    "summary": "DV2 currently verifies 2 distinct clothing slot fixtures on the automated demo-ready path.",
                },
                {
                    "axis_id": "fx_fixture_diversity",
                    "status": "covered",
                    "distinct_count": 2,
                    "observed_values": ["fixture_directional_burst", "fixture_radial_burst"],
                    "summary": "DV2 currently verifies 2 distinct FX fixtures on the automated demo-ready path.",
                },
                {
                    "axis_id": "action_variation",
                    "status": "covered",
                    "distinct_count": 2,
                    "observed_values": ["showcase_root_translate_and_turn", "dv2_root_translate_forward"],
                    "summary": "DV2 currently verifies 2 distinct verified action presets on the automated demo-ready path.",
                },
                {
                    "axis_id": "animation_variation",
                    "status": "covered",
                    "distinct_count": 3,
                    "observed_values": ["MM_Attack_01", "MM_Idle", "MF_Unarmed_Walk_Fwd"],
                    "summary": "DV2 currently verifies 3 distinct verified animation presets on the automated demo-ready path.",
                },
            ],
            "per_package_results": [
                {
                    "package_id": "pkg_alpha",
                    "status": "pass",
                    "targeted_runs": [
                        {
                            "axis_id": "action_variation",
                            "variant_id": "dv2_root_translate_forward",
                            "status": "pass",
                            "request_kind": "action_preview",
                            "key_image_paths": {
                                "primary_after": after_image_path,
                            },
                        },
                        {
                            "axis_id": "clothing_fixture_diversity",
                            "variant_id": "fixture_brow_cards",
                            "status": "pass",
                            "request_kind": "action_preview",
                            "key_image_paths": {
                                "primary_after": front_image_path,
                            },
                        },
                    ],
                }
            ],
        },
    )
    return report_path


def build_fixture_pack(
    tmp_path: Path,
    *,
    include_governance: bool = True,
    include_c0: bool = False,
    include_c1: bool = False,
    include_c2: bool = False,
    include_dv1: bool = False,
    include_dv2: bool = False,
    include_e2c: bool = False,
    include_a1: bool = False,
    include_m1: bool = False,
    include_e2b: bool = False,
    include_pv1: bool = False,
    include_q5c: bool = False,
    include_q5c_contrast: bool = False,
) -> dict:
    verification_root = materialize_report_fixtures(tmp_path / "verification", include_governance=include_governance)
    write_fixture_feature_ledger(tmp_path)
    if include_c0:
        write_fixture_c0_report(verification_root)
    if include_c1:
        if not include_c0:
            write_fixture_c0_report(verification_root)
        write_fixture_c1_report(verification_root)
    if include_c2:
        if not include_c1:
            if not include_c0:
                write_fixture_c0_report(verification_root)
            write_fixture_c1_report(verification_root)
        write_fixture_c2_report(verification_root)
    if include_dv1:
        write_fixture_dv1_report(verification_root)
    if include_dv2:
        write_fixture_dv2_report(verification_root)
    if include_e2c:
        write_fixture_e2c_report(verification_root)
    if include_a1:
        write_fixture_a1_report(verification_root)
    if include_m1:
        write_fixture_m1_report(verification_root)
    if include_e2b:
        write_fixture_e2b_report(verification_root)
    if include_pv1:
        write_fixture_pv1_report(verification_root)
    if include_q5c:
        write_fixture_q5c_report(verification_root)
    if include_q5c_contrast:
        write_fixture_q5c_contrast_report(verification_root)
    output_root = tmp_path / "tooling" / "pack"
    latest_root = tmp_path / "tooling" / "latest"
    manifest = build_evidence_pack(
        verification_root=verification_root,
        output_root=output_root,
        latest_root=latest_root,
        repo_root=tmp_path,
    )
    session_manifest_path = build_fixture_e2_session(tmp_path)
    return {
        "verification_root": verification_root,
        "manifest_path": output_root / "manifest.json",
        "output_root": output_root,
        "latest_root": latest_root,
        "manifest": manifest,
        "session_manifest_path": session_manifest_path,
    }


def build_fixture_e2_session(tmp_path: Path) -> Path:
    session_root = tmp_path / "Saved" / "demo" / "e2" / "latest"
    session_root.mkdir(parents=True, exist_ok=True)
    session_manifest_path = session_root / DEFAULT_E2_SESSION_NAME
    session_payload = {
        "generated_at_utc": "2026-04-11T05:35:30+00:00",
        "session_id": "playable_demo_e2_bootstrap",
        "session_type": "playable_demo_bootstrap",
        "host_key": "demo",
        "mode": "editor_rendered",
        "level_path": "/Game/Levels/DefaultLevel",
        "default_package_id": "pkg_alpha",
        "switch_order": ["pkg_alpha"],
        "packages": [
            {
                "package_id": "pkg_alpha",
                "sample_id": "fixture_alpha",
                "host_blueprint_asset": "/Game/Fixture/BP_PMXCharacterHost_FixtureAlpha",
                "level_path": "/Game/Levels/DefaultLevel",
                "spawn_location": {"x": 0.0, "y": 0.0, "z": 120.0},
                "spawn_rotation": {"pitch": 0.0, "yaw": 180.0, "roll": 0.0},
                "hero_shot_id": "top",
                "hero_shot_plan": {
                    "shot_id": "top",
                    "camera_id": "top",
                    "camera_source": "explicit_pose",
                    "camera_location": {"x": 92.0, "y": -82.0, "z": 620.0},
                    "camera_rotation": {"pitch": -72.0, "yaw": 138.0, "roll": 0.0},
                    "target_location": {"x": 0.0, "y": 0.0, "z": 240.0},
                },
                "slot_bindings": [
                    {"slot_name": "weapon", "item_kind": "skeletal_mesh"},
                    {"slot_name": "clothing", "item_kind": "skeletal_mesh"},
                    {"slot_name": "fx", "item_kind": "niagara_system"},
                ],
                "clothing_binding": {
                    "slot_name": "clothing",
                    "item_package_id": "fixture_hair",
                    "item_kind": "skeletal_mesh",
                    "attach_socket_name": "Head",
                    "skeletal_mesh_asset": "/Game/Characters/Echo/Meshes/SKM_Echo_Hair.SKM_Echo_Hair",
                },
                "fx_binding": {
                    "slot_name": "fx",
                    "item_package_id": "fixture_fx",
                    "item_kind": "niagara_system",
                    "attach_socket_name": "WeaponSocket",
                    "niagara_system_asset": "/Niagara/DefaultAssets/Templates/Systems/DirectionalBurst.DirectionalBurst",
                    "niagara_desired_age_seconds": 0.08,
                    "niagara_seek_delta_seconds": 0.0166667,
                    "niagara_advance_step_count": 4,
                    "niagara_advance_step_delta_seconds": 0.0166667,
                },
                "action_presets": [
                    {
                        "preset_id": "showcase_root_translate_and_turn",
                        "action_kind": "root_translate_and_turn",
                        "action_distance": 85.0,
                        "action_yaw_delta": 24.0,
                        "action_settle_seconds": 0.2,
                        "status": "pass",
                    }
                ],
                "animation_presets": [
                    {
                        "preset_id": "MM_Attack_01",
                        "family": "attack",
                        "source_gate_id": "demo_retargeted_animation_preview_d8",
                        "requested_animation_asset_path": "/Game/CombatMagicAnims/MM_Attack_01",
                        "resolved_animation_asset_path": "/Game/RTG_MM_Attack_01_PMXPreview",
                        "animation_sample_time_seconds": 0.65,
                        "pose_probe_bone_names": ["Bone_002", "Bone_R_011"],
                        "retarget_source_ik_rig_asset_path": "/Game/Characters/UE4_Mannequin/Rigs/IK_UE4_Mannequin_Retarget",
                        "retarget_target_ik_rig_asset_path": "/Game/PMXPipeline/Retarget/Source/IK_pkg_alpha",
                        "retarget_source_mesh_asset_path": "/Game/Characters/UE4_Mannequin/Meshes/SKM_UE4_Mannequin.SKM_UE4_Mannequin",
                        "retarget_target_mesh_asset_path": "/Game/Fixture/Meshes/SKM_pkg_alpha.SKM_pkg_alpha",
                        "retargeter_asset_path": "/Game/PMXPipeline/Retarget/Demo/RTG_IK_UE4_Mannequin_Retarget_to_pkg_alpha_Preview",
                        "status": "pass",
                    }
                ],
                "evidence": {
                    "hero_before_image_path": str((FIXTURE_ROOT / "images" / "front.ppm").resolve()),
                    "hero_after_image_path": str((FIXTURE_ROOT / "images" / "side.ppm").resolve()),
                },
            }
        ],
        "source_reports": {
            "e1_report_path": str((REPORT_FIXTURES / "latest_demo_cross_bundle_regression_d12_report.json").resolve()),
        },
    }
    write_json(session_manifest_path, session_payload)
    return session_manifest_path


def write_fixture_demo_control_state(
    tmp_path: Path,
    *,
    package_id: str = "pkg_alpha",
    action_preset_id: str = "showcase_root_translate_and_turn",
    animation_preset_id: str = "MM_Attack_01",
) -> Path:
    session_root = tmp_path / "Saved" / "demo" / "e2" / "latest"
    session_root.mkdir(parents=True, exist_ok=True)
    control_state_path = session_root / DEFAULT_E2_CONTROL_STATE_NAME
    image_path = str((FIXTURE_ROOT / "images" / "front.ppm").resolve())
    write_json(
        control_state_path,
        {
            "status": "pass",
            "session_id": "playable_demo_e2_bootstrap",
            "generated_at_utc": "2026-04-11T06:15:00+00:00",
            "selected_package_id": package_id,
            "selected_action_preset_id": action_preset_id,
            "selected_animation_preset_id": animation_preset_id,
            "last_runs_by_package": {
                package_id: {
                    "action_preview": {
                        "request_kind": "action_preview",
                        "operation": "invoke",
                        "request_json_path": str((session_root / "action_request.json").resolve()),
                        "result_json_path": str((session_root / "action_result.json").resolve()),
                        "result_status": "pass",
                        "host_key": "demo",
                        "generated_at_utc": "2026-04-11T06:14:00+00:00",
                        "selected_package_id": package_id,
                        "selected_action_preset_id": action_preset_id,
                        "selected_animation_preset_id": animation_preset_id,
                        "key_image_paths": {
                            "before": [image_path],
                            "after": [image_path],
                            "primary_before": image_path,
                            "primary_after": image_path,
                        },
                        "credibility_summary": {
                            "subject_visible": True,
                            "before_image_present": True,
                            "after_image_present": True,
                            "action_motion_verified": True,
                            "animation_pose_verified": False,
                            "warning_flags": [],
                        },
                    }
                }
            },
        },
    )
    return control_state_path


def create_invalid_manifest(tmp_path: Path) -> Path:
    path = tmp_path / "invalid_manifest.json"
    path.write_text("{ invalid json", encoding="utf-8")
    return path


def create_missing_artifact_manifest(tmp_path: Path) -> Path:
    pack = build_fixture_pack(tmp_path)
    preview_images = list(pack["manifest"]["artifacts"]["preview_images"])
    missing_relative_path = preview_images[0]["relative_path"]
    missing_path = pack["output_root"] / Path(missing_relative_path)
    if missing_path.exists():
        missing_path.unlink()
    return pack["manifest_path"]


def parse_json_from_stdout(stdout: str) -> dict:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start < 0 or end < start:
        raise AssertionError(f"Could not locate JSON payload in stdout:\n{stdout}")
    return json.loads(stdout[start : end + 1])


def run_workbench_process(
    *,
    manifest_path: Path | None = None,
    latest: bool = False,
    session_manifest_path: Path | None = None,
    workspace_config_path: Path | None = None,
    package_id: str | None = None,
    action_preset_id: str | None = None,
    animation_preset_id: str | None = None,
    review_compare_index: int | None = None,
    demo_request_export: bool = False,
    demo_request_dry_run: bool = False,
    demo_request_invoke: bool = False,
    demo_session_round_invoke: bool = False,
    demo_review_replay: bool = False,
    demo_request_kind: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(WORKBENCH_SCRIPT),
        "-DumpStateJson",
        "-ExitAfterLoad",
    ]
    if manifest_path is not None:
        command += ["-Manifest", str(manifest_path)]
    elif latest:
        command += ["-Latest"]
    if session_manifest_path is not None:
        command += ["-SessionManifest", str(session_manifest_path)]
    if workspace_config_path is not None:
        command += ["-WorkspaceConfig", str(workspace_config_path)]
    if package_id is not None:
        command += ["-PackageId", str(package_id)]
    if action_preset_id is not None:
        command += ["-ActionPresetId", str(action_preset_id)]
    if animation_preset_id is not None:
        command += ["-AnimationPresetId", str(animation_preset_id)]
    if review_compare_index is not None:
        command += ["-ReviewCompareIndex", str(review_compare_index)]
    if demo_request_export:
        command += ["-DemoRequestExport"]
    if demo_request_dry_run:
        command += ["-DemoRequestDryRun"]
    if demo_request_invoke:
        command += ["-DemoRequestInvoke"]
    if demo_session_round_invoke:
        command += ["-DemoSessionRoundInvoke"]
    if demo_review_replay:
        command += ["-DemoReviewReplay"]
    if demo_request_kind is not None:
        command += ["-DemoRequestKind", str(demo_request_kind)]
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QT_API"] = "pyside6"
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    payload = parse_json_from_stdout(completed.stdout)
    return completed, payload


def run_demo_request_process(
    *,
    manifest_path: Path,
    session_manifest_path: Path | None = None,
    request_kind: str = "action_preview",
    package_id: str | None = None,
    dump_request_json: bool = True,
    write_request_path: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(DEMO_REQUEST_SCRIPT),
        "-Manifest",
        str(manifest_path),
        "-RequestKind",
        request_kind,
    ]
    if session_manifest_path is not None:
        command += ["-SessionManifest", str(session_manifest_path)]
    if package_id is not None:
        command += ["-PackageId", str(package_id)]
    if dump_request_json:
        command += ["-DumpRequestJson"]
    if write_request_path is not None:
        command += ["-WriteRequestPath", str(write_request_path)]
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    payload = parse_json_from_stdout(completed.stdout)
    return completed, payload
