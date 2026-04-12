from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from aiue_t1.diversity_matrix import build_diversity_axis, build_diversity_matrix_quality_summary, diversity_status_for_count
from aiue_t1.report_index import build_report_index
from tests.t2.helpers import build_fixture_pack


def _load_dv2_module():
    module_path = Path(__file__).resolve().parents[2] / "workflows" / "pmx_pipeline" / "run_diversity_matrix_dv2.py"
    workflow_dir = str(module_path.parent)
    if workflow_dir not in sys.path:
        sys.path.insert(0, workflow_dir)
    sys.modules.pop("_bootstrap", None)
    spec = importlib.util.spec_from_file_location("run_diversity_matrix_dv2_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_diversity_status_for_count_uses_fixed_thresholds():
    assert diversity_status_for_count("character_variant_diversity", 2) == "covered"
    assert diversity_status_for_count("character_variant_diversity", 1) == "partial"
    assert diversity_status_for_count("character_variant_diversity", 0) == "missing"


def test_build_diversity_axis_normalizes_observed_values():
    axis = build_diversity_axis(
        "animation_variation",
        ["MM_Attack_01", "MM_Attack_01", "MM_Idle"],
        noun_phrase="verified animation presets",
    )
    assert axis["status"] == "covered"
    assert axis["distinct_count"] == 2
    assert axis["observed_values"] == ["MM_Attack_01", "MM_Idle"]


def test_build_diversity_matrix_quality_summary_reads_latest_report(tmp_path):
    pack = build_fixture_pack(tmp_path, include_dv1=True)
    report_index = build_report_index(pack["verification_root"])
    summary = build_diversity_matrix_quality_summary(report_index)
    assert summary["status"] == "pass"
    assert summary["gate_id"] == "diversity_matrix_dv1"
    assert summary["covered_axis_count"] == 3
    assert summary["partial_axis_count"] == 3
    assert summary["distinct_counts"]["character_variant_diversity"] == 2
    assert summary["distinct_counts"]["animation_variation"] == 3


def test_build_diversity_matrix_quality_summary_prefers_dv2_over_dv1(tmp_path):
    pack = build_fixture_pack(tmp_path, include_dv1=True, include_dv2=True)
    report_index = build_report_index(pack["verification_root"])
    summary = build_diversity_matrix_quality_summary(report_index)
    assert summary["status"] == "pass"
    assert summary["gate_id"] == "diversity_matrix_dv2"
    assert summary["covered_axis_count"] == 6
    assert summary["distinct_counts"]["clothing_fixture_diversity"] == 2


def test_dv2_action_request_payload_uses_variant_id_for_action_axis():
    module = _load_dv2_module()
    package_payload = {
        "package_id": "pkg_alpha",
        "sample_id": "sample_alpha",
        "host_blueprint_asset": "/Game/Test/BP_Host",
        "level_path": "/Game/Test/Lvl_Test",
        "spawn_location": {"x": 0.0, "y": 0.0, "z": 0.0},
        "spawn_rotation": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
        "hero_shot_id": "hero",
        "hero_shot_plan": {"shot_id": "hero"},
        "action_presets": [{"preset_id": "showcase_root_translate_and_turn", "action_kind": "root_translate_and_turn"}],
        "animation_presets": [{"preset_id": "MM_Attack_01"}],
    }
    variant = {
        "axis_id": "action_variation",
        "variant_id": "dv2_root_translate_forward",
        "action_kind": "root_translate_forward",
    }
    payload = module._action_request_payload(
        package_payload=package_payload,
        host_key="demo",
        mode="editor_rendered",
        variant=variant,
        output_root=Path("C:/AiUE/Saved/verification/test"),
    )
    assert payload["selected_action_preset_id"] == "dv2_root_translate_forward"


def test_dv2_action_request_payload_keeps_baseline_preset_for_non_action_axis():
    module = _load_dv2_module()
    package_payload = {
        "package_id": "pkg_alpha",
        "sample_id": "sample_alpha",
        "host_blueprint_asset": "/Game/Test/BP_Host",
        "level_path": "/Game/Test/Lvl_Test",
        "spawn_location": {"x": 0.0, "y": 0.0, "z": 0.0},
        "spawn_rotation": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
        "hero_shot_id": "hero",
        "hero_shot_plan": {"shot_id": "hero"},
        "action_presets": [{"preset_id": "showcase_root_translate_and_turn", "action_kind": "root_translate_and_turn"}],
        "animation_presets": [{"preset_id": "MM_Attack_01"}],
    }
    variant = {
        "axis_id": "clothing_fixture_diversity",
        "variant_id": "dv2_kellan_eyebrow_cards_fixture",
        "slot_name": "clothing",
        "item_kind": "static_mesh",
    }
    payload = module._action_request_payload(
        package_payload=package_payload,
        host_key="demo",
        mode="editor_rendered",
        variant=variant,
        output_root=Path("C:/AiUE/Saved/verification/test"),
    )
    assert payload["selected_action_preset_id"] == "showcase_root_translate_and_turn"
