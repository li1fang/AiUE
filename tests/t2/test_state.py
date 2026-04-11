from __future__ import annotations

from pathlib import Path

from aiue_t2.state import build_default_view_state, load_workbench_state

from tests.t2.helpers import build_fixture_pack, create_invalid_manifest, create_missing_artifact_manifest


def test_load_workbench_state_reads_fixture_pack(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    state = load_workbench_state(pack["manifest_path"])
    assert state.status == "pass"
    assert state.summary_counts["reports"] == 7
    assert state.summary_counts["active_line_reports"] == 4
    assert state.summary_counts["platform_line_reports"] == 3
    assert state.slot_debugger["package_count"] == 1
    assert state.default_report_gate_id == "visual_proof_v1"
    assert state.demo_session.status == "pass"
    assert state.demo_session.default_package_id == "pkg_alpha"
    assert len(state.demo_session.packages) == 1
    assert len(state.preview_images) >= 4


def test_dump_payload_exposes_expected_native_state(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    state = load_workbench_state(pack["manifest_path"])
    payload = state.to_dump_payload(build_default_view_state(state))
    assert payload["status"] == "pass"
    assert payload["summary_counts"]["reports"] == 7
    assert payload["report_categories"]["active_line"] == [
        "visual_proof_v1",
        "demo_stage_d1_onboarding",
        "demo_cross_bundle_regression_d12",
        "multi_slot_quality_gate_q4",
    ]
    assert payload["slot_debugger"]["package_count"] == 1
    assert payload["slot_debugger"]["package_ids"] == ["pkg_alpha"]
    assert payload["demo_session"]["status"] == "pass"
    assert payload["demo_session"]["package_ids"] == ["pkg_alpha"]
    assert payload["selected_default_action_preset"] == "showcase_root_translate_and_turn"
    assert payload["selected_default_animation_preset"] == "MM_Attack_01"


def test_load_workbench_state_flags_invalid_manifest(tmp_path: Path):
    state = load_workbench_state(create_invalid_manifest(tmp_path))
    assert state.status == "error"
    assert state.errors[0].code == "manifest_invalid_json"


def test_load_workbench_state_flags_missing_artifact(tmp_path: Path):
    state = load_workbench_state(create_missing_artifact_manifest(tmp_path))
    assert state.status == "error"
    assert any(error.code == "artifact_missing" for error in state.errors)
