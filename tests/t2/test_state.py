from __future__ import annotations

from pathlib import Path
import threading
import time

from aiue_t2.state import build_default_view_state, load_workbench_state, wait_for_manifest_path

from tests.t2.helpers import build_fixture_pack, create_invalid_manifest, create_missing_artifact_manifest


def test_load_workbench_state_reads_fixture_pack(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    state = load_workbench_state(pack["manifest_path"])
    assert state.status == "pass"
    assert state.summary_counts["reports"] == 9
    assert state.summary_counts["active_line_reports"] == 4
    assert state.summary_counts["platform_line_reports"] == 3
    assert state.summary_counts["governance_line_reports"] == 2
    assert state.slot_debugger["package_count"] == 1
    assert state.default_report_gate_id == "visual_proof_v1"
    assert state.governance_balance.status == "attention"
    assert state.governance_balance.recommended_next_round_kind == "flexible"
    assert state.test_governance.status == "attention"
    assert state.test_governance.checkpoint_ready is False
    assert state.test_governance.automation_checkpoint_ready is False
    assert state.test_governance.signoff_checkpoint_ready is False
    assert state.demo_session.status == "pass"
    assert state.demo_session.default_package_id == "pkg_alpha"
    assert len(state.demo_session.packages) == 1
    assert state.demo_request.status == "pass"
    assert sorted(state.demo_request.requests) == ["action_preview", "animation_preview"]
    assert len(state.preview_images) >= 4
    assert state.quality_summaries["q5c_lite"]["status"] == "missing"
    assert state.quality_summaries["q5c_contrast"]["status"] == "missing"


def test_dump_payload_exposes_expected_native_state(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    state = load_workbench_state(pack["manifest_path"])
    payload = state.to_dump_payload(build_default_view_state(state))
    assert payload["status"] == "pass"
    assert payload["summary_counts"]["reports"] == 9
    assert payload["report_categories"]["active_line"] == [
        "visual_proof_v1",
        "demo_stage_d1_onboarding",
        "demo_cross_bundle_regression_d12",
        "multi_slot_quality_gate_q4",
    ]
    assert payload["report_categories"]["governance_line"] == [
        "dynamic_balance_governance_progress",
        "test_governance_round1",
    ]
    assert payload["slot_debugger"]["package_count"] == 1
    assert payload["slot_debugger"]["package_ids"] == ["pkg_alpha"]
    assert payload["governance_balance"]["status"] == "attention"
    assert payload["governance_balance"]["recommended_next_round_kind"] == "flexible"
    assert payload["test_governance"]["status"] == "attention"
    assert payload["test_governance"]["checkpoint_ready"] is False
    assert payload["test_governance"]["automation_checkpoint_ready"] is False
    assert payload["test_governance"]["signoff_checkpoint_ready"] is False
    assert payload["test_governance"]["required_lane_ids"] == [
        "repo_surface",
        "schema_contracts",
        "t2_smoke",
    ]
    assert payload["test_governance"]["high_priority_blind_spot_ids"] == [
        "material_texture_loading",
        "manual_playable_demo_validation",
    ]
    assert payload["test_governance"]["high_priority_automation_blind_spot_ids"] == [
        "material_texture_loading",
    ]
    assert payload["test_governance"]["high_priority_signoff_blind_spot_ids"] == [
        "manual_playable_demo_validation",
    ]
    assert payload["quality_summaries"]["q5c_lite"]["status"] == "missing"
    assert payload["q5c_contrast_focus"]["status"] == "missing"
    assert "tools/t2/python/aiue_t2/ui.py" in payload["governance_balance"]["hotspot_paths"]
    assert payload["demo_session"]["status"] == "pass"
    assert payload["demo_session"]["package_ids"] == ["pkg_alpha"]
    assert payload["selected_default_action_preset"] == "showcase_root_translate_and_turn"
    assert payload["selected_default_animation_preset"] == "MM_Attack_01"
    assert payload["demo_request"]["status"] == "pass"
    assert sorted(payload["demo_request"]["request_kinds"]) == ["action_preview", "animation_preview"]
    assert payload["demo_request"]["requests"]["action_preview"]["command"] == "action-preview"
    assert payload["demo_request"]["requests"]["animation_preview"]["command"] == "animation-preview"


def test_load_workbench_state_flags_invalid_manifest(tmp_path: Path):
    state = load_workbench_state(create_invalid_manifest(tmp_path))
    assert state.status == "error"
    assert state.errors[0].code == "manifest_invalid_json"


def test_load_workbench_state_flags_missing_artifact(tmp_path: Path):
    state = load_workbench_state(create_missing_artifact_manifest(tmp_path))
    assert state.status == "error"
    assert any(error.code == "artifact_missing" for error in state.errors)


def test_load_workbench_state_handles_missing_governance_report(tmp_path: Path):
    pack = build_fixture_pack(tmp_path, include_governance=False)
    state = load_workbench_state(pack["manifest_path"])
    assert state.status == "pass"
    assert state.summary_counts["governance_line_reports"] == 0
    assert state.governance_balance.status == "missing"
    assert state.test_governance.status == "missing"


def test_wait_for_manifest_path_tolerates_short_missing_latest(tmp_path: Path):
    manifest_path = tmp_path / "tooling" / "latest" / "manifest.json"

    def _writer() -> None:
        time.sleep(0.2)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text("{}", encoding="utf-8")

    thread = threading.Thread(target=_writer)
    thread.start()
    resolved = wait_for_manifest_path(manifest_path, timeout_seconds=1.0, poll_interval_seconds=0.05)
    thread.join(timeout=1.0)
    assert resolved == manifest_path.resolve()
    assert resolved.exists()


def test_load_workbench_state_reads_q5c_quality_summary(tmp_path: Path):
    pack = build_fixture_pack(tmp_path, include_q5c=True)
    state = load_workbench_state(pack["manifest_path"])
    q5c_summary = state.quality_summaries["q5c_lite"]
    assert q5c_summary["status"] == "pass"
    assert q5c_summary["package_count"] == 1
    assert q5c_summary["diagnostic_class_counts"]["pass_stable"] == 1
    assert q5c_summary["risk_band_counts"]["watch"] == 1
    assert q5c_summary["highest_risk_band"] == "watch"
    assert q5c_summary["watchlist_count"] == 1
    assert q5c_summary["watchlist_package_ids"] == ["pkg_alpha"]
    assert q5c_summary["focus_package_id"] == "pkg_alpha"
    assert q5c_summary["focus_metric"] == "penetration_ratio_margin_to_failure"
    assert q5c_summary["focus_margin_to_failure"] == 0.02
    assert q5c_summary["packages"][0]["closest_margin_metric"] == "penetration_ratio_margin_to_failure"
    assert q5c_summary["packages"][0]["closest_margin_value"] == 0.02
    assert q5c_summary["packages"][0]["risk_band"] == "watch"
    assert q5c_summary["packages"][0]["artifact_image_path"].endswith("q5c_pkg_alpha_debug.ppm")


def test_load_workbench_state_reads_q5c_contrast_focus(tmp_path: Path):
    pack = build_fixture_pack(tmp_path, include_q5c=True, include_q5c_contrast=True)
    state = load_workbench_state(pack["manifest_path"])
    payload = state.to_dump_payload(build_default_view_state(state))
    contrast_summary = state.quality_summaries["q5c_contrast"]
    contrast_focus = payload["q5c_contrast_focus"]
    assert contrast_summary["status"] == "pass"
    assert contrast_summary["package_count"] == 1
    assert contrast_summary["required_case_ids"] == [
        "baseline_current",
        "best_pass_reference",
        "closest_fail_reference",
    ]
    assert state.default_image_key == "q5c_contrast_pkg_alpha_baseline_current"
    assert contrast_focus["status"] == "pass"
    assert contrast_focus["selected_package_id"] == "pkg_alpha"
    assert contrast_focus["case_ids"] == [
        "baseline_current",
        "best_pass_reference",
        "closest_fail_reference",
    ]
    assert contrast_focus["recommended_preview_image_key"] == "q5c_contrast_pkg_alpha_baseline_current"
    assert contrast_focus["cases"][0]["debug_image_path"].endswith("q5c_contrast_pkg_alpha_baseline_current.ppm")
    assert contrast_focus["compare_mode_status"] == "pass"
    assert len(contrast_focus["compare_rows"]) == 3
    assert contrast_focus["compare_summary_text"].startswith(
        "baseline_current -> closest_fail_reference | status pass -> fail"
    )
    fail_compare = next(
        row for row in contrast_focus["compare_rows"] if row["pair_label"] == "baseline_current -> closest_fail_reference"
    )
    assert fail_compare["status_transition"] == "pass -> fail"
    assert fail_compare["risk_transition"] == "watch -> fail"
    assert fail_compare["delta_z_change"] == 20.0
    assert round(float(fail_compare["closest_margin_change"]), 4) == -0.0607
    assert round(float(fail_compare["floating_ratio_change"]), 4) == 0.0407
    assert "floating +0.0407" in fail_compare["key_delta_text"]


def test_load_workbench_state_reads_m1_material_summary_and_pv1_report(tmp_path: Path):
    pack = build_fixture_pack(tmp_path, include_m1=True, include_pv1=True, include_e2b=True)
    state = load_workbench_state(pack["manifest_path"])
    payload = state.to_dump_payload(build_default_view_state(state))
    m1_summary = state.quality_summaries["m1_material_proof"]
    assert m1_summary["status"] == "pass"
    assert m1_summary["package_count"] == 1
    assert m1_summary["packages"][0]["package_id"] == "pkg_alpha"
    assert m1_summary["packages"][0]["character_imported_texture_count"] == 13
    assert payload["quality_summaries"]["m1_material_proof"]["status"] == "pass"
    assert "manual_playable_demo_validation_pv1" in payload["report_categories"]["governance_line"]
    assert payload["pv1_signoff"]["status"] == "attention"
    assert payload["pv1_signoff"]["operator"] == "fixture_user"
    assert payload["pv1_signoff"]["checked_package_ids"] == ["pkg_alpha"]
    assert "playable_demo_e2b_credible_showcase" in payload["report_categories"]["historical_other"]


def test_load_workbench_state_reads_dv1_diversity_summary(tmp_path: Path):
    pack = build_fixture_pack(tmp_path, include_dv1=True)
    state = load_workbench_state(pack["manifest_path"])
    payload = state.to_dump_payload(build_default_view_state(state))
    diversity_summary = state.quality_summaries["diversity_matrix"]
    assert diversity_summary["status"] == "pass"
    assert diversity_summary["covered_axis_count"] == 3
    assert diversity_summary["distinct_counts"]["character_variant_diversity"] == 2
    assert "diversity_matrix_dv1" in payload["report_categories"]["governance_line"]
    assert payload["quality_summaries"]["diversity_matrix"]["status"] == "pass"
