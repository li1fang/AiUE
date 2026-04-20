from __future__ import annotations

from pathlib import Path

from aiue_t2.demo_review_compare_state import write_demo_review_compare_state
from aiue_t2.demo_review_history_state import load_demo_review_history_state, write_demo_review_history_event

from tests.t2.helpers import (
    REPO_ROOT,
    build_fixture_pack,
    create_invalid_manifest,
    create_missing_artifact_manifest,
    run_workbench_process,
)


def _replay_run(tmp_path: Path, *, request_kind: str, generated_at_utc: str) -> dict:
    before_image = tmp_path / f"{request_kind}_{generated_at_utc.replace(':', '').replace('+', '').replace('-', '')}_before.png"
    after_image = tmp_path / f"{request_kind}_{generated_at_utc.replace(':', '').replace('+', '').replace('-', '')}_after.png"
    before_image.write_text("fixture", encoding="utf-8")
    after_image.write_text("fixture", encoding="utf-8")
    return {
        "request_kind": request_kind,
        "operation": "review_replay",
        "request_json_path": str((tmp_path / f"{request_kind}_request.json").resolve()),
        "result_json_path": str((tmp_path / f"{request_kind}_result.json").resolve()),
        "result_status": "pass",
        "host_key": "demo",
        "generated_at_utc": generated_at_utc,
        "selected_package_id": "pkg_alpha",
        "selected_action_preset_id": "showcase_root_translate_and_turn",
        "selected_animation_preset_id": "MM_Attack_01",
        "key_image_paths": {
            "primary_before": str(before_image.resolve()),
            "primary_after": str(after_image.resolve()),
        },
        "credibility_summary": {
            "subject_visible": True,
            "before_image_present": True,
            "after_image_present": True,
            "action_motion_verified": request_kind == "action_preview",
            "animation_pose_verified": request_kind == "animation_preview",
            "warning_flags": [],
        },
    }


def test_workbench_cli_seven_open_cycles(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    for _ in range(7):
        completed, payload = run_workbench_process(manifest_path=pack["manifest_path"])
        assert completed.returncode == 0, completed.stderr
        assert payload["status"] == "pass"
        assert payload["summary_counts"]["reports"] == 10
        assert payload["summary_counts"]["active_line_reports"] == 4
        assert payload["summary_counts"]["platform_line_reports"] == 3
        assert payload["summary_counts"]["body_platform_line_reports"] == 0
        assert payload["summary_counts"]["governance_line_reports"] == 3
        assert payload["slot_debugger"]["package_count"] == 1
        assert payload["governance_balance"]["status"] == "attention"
        assert payload["test_governance"]["status"] == "attention"
        assert payload["qa_full"]["status"] == "attention"
        assert payload["qa_full"]["root_failure_count"] == 1
        assert payload["qa_full"]["cascade_failure_count"] == 1
        assert payload["qa_full"]["environment_failure_count"] == 1
        assert payload["feature_ledger"]["status"] == "pass"
        assert payload["feature_ledger"]["experimental_item_count"] == 1
        assert payload["feature_ledger"]["unknown_priority_count"] == 1
        assert payload["feature_ledger"]["pending_triage_count"] == 1
        assert payload["test_governance"]["checkpoint_ready"] is False
        assert payload["test_governance"]["automation_checkpoint_ready"] is False
        assert payload["test_governance"]["signoff_checkpoint_ready"] is False
        assert payload["quality_summaries"]["q5c_lite"]["status"] == "missing"
        assert payload["demo_session"]["status"] == "pass"
        assert payload["demo_session"]["package_ids"] == ["pkg_alpha"]
        assert payload["demo_control_state"]["status"] == "missing"
        assert payload["demo_round_state"]["status"] == "missing"
        assert payload["demo_review_state"]["status"] == "missing"
        assert payload["demo_review_focus"]["status"] == "missing"
        assert payload["demo_review_replay_state"]["status"] == "missing"
        assert payload["demo_review_history_state"]["status"] == "missing"
        assert payload["demo_review_history_focus"]["status"] == "missing"
        assert payload["demo_review_compare_state"]["status"] == "missing"
        assert payload["demo_review_compare_focus"]["status"] == "missing"
        assert sorted(payload["demo_request"]["request_kinds"]) == ["action_preview", "animation_preview"]
        assert set(payload["report_categories"]) == {"active_line", "platform_line", "body_platform_line", "governance_line", "historical_other"}


def test_workbench_cli_error_injections(tmp_path: Path):
    missing_manifest = tmp_path / "missing_manifest.json"
    completed, payload = run_workbench_process(manifest_path=missing_manifest)
    assert completed.returncode != 0
    assert payload["status"] == "error"
    assert payload["errors"][0]["code"] == "manifest_missing"

    completed, payload = run_workbench_process(manifest_path=create_invalid_manifest(tmp_path))
    assert completed.returncode != 0
    assert payload["status"] == "error"
    assert payload["errors"][0]["code"] == "manifest_invalid_json"

    completed, payload = run_workbench_process(manifest_path=create_missing_artifact_manifest(tmp_path))
    assert completed.returncode != 0
    assert payload["status"] == "error"
    assert any(item["code"] == "artifact_missing" for item in payload["errors"])


def test_workbench_cli_reads_latest_manifest_smoke():
    latest_manifest = REPO_ROOT / "Saved" / "tooling" / "t1" / "latest" / "manifest.json"
    assert latest_manifest.exists()
    completed, payload = run_workbench_process(latest=True)
    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "pass"
    assert set(payload["report_categories"]) == {"active_line", "platform_line", "body_platform_line", "governance_line", "historical_other"}
    assert payload["summary_counts"]["active_line_reports"] >= 1
    assert payload["summary_counts"]["platform_line_reports"] >= 1
    assert payload["summary_counts"]["body_platform_line_reports"] >= 0
    assert payload["summary_counts"]["governance_line_reports"] >= 0
    assert payload["slot_debugger"]["package_count"] >= 1
    assert payload["governance_balance"]["status"] in {"pass", "attention", "missing"}
    assert payload["test_governance"]["status"] in {"pass", "attention", "missing"}
    assert payload["feature_ledger"]["status"] in {"pass", "missing", "error"}
    assert payload["demo_session"]["status"] in {"pass", "missing"}
    assert payload["demo_request"]["status"] in {"pass", "missing", "error"}
    assert payload["demo_review_replay_state"]["status"] in {"pass", "missing", "error"}
    assert payload["demo_review_history_state"]["status"] in {"pass", "missing", "error"}
    assert payload["demo_review_compare_state"]["status"] in {"pass", "missing", "error"}


def test_workbench_cli_reads_body_platform_summary(tmp_path: Path):
    pack = build_fixture_pack(tmp_path, include_c0=True)
    completed, payload = run_workbench_process(manifest_path=pack["manifest_path"])
    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "pass"
    assert payload["summary_counts"]["body_platform_line_reports"] == 1
    assert payload["report_categories"]["body_platform_line"] == ["modular_morphology_inventory_c0"]
    assert payload["quality_summaries"]["body_platform"]["status"] == "pass"
    assert payload["quality_summaries"]["body_platform"]["canonical_fixture_family_id"] == "family_alpha"


def test_workbench_cli_prefers_c1_body_platform_summary(tmp_path: Path):
    pack = build_fixture_pack(tmp_path, include_c1=True)
    completed, payload = run_workbench_process(manifest_path=pack["manifest_path"])
    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "pass"
    assert payload["summary_counts"]["body_platform_line_reports"] == 2
    assert payload["report_categories"]["body_platform_line"] == [
        "modular_morphology_inventory_c0",
        "parametric_body_contract_c1",
    ]
    assert payload["quality_summaries"]["body_platform"]["gate_id"] == "parametric_body_contract_c1"
    assert payload["quality_summaries"]["body_platform"]["contract_id"] == "family_alpha::parametric_body_contract_c1"


def test_workbench_cli_prefers_c2_body_platform_summary(tmp_path: Path):
    pack = build_fixture_pack(tmp_path, include_c2=True)
    completed, payload = run_workbench_process(manifest_path=pack["manifest_path"])
    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "pass"
    assert payload["summary_counts"]["body_platform_line_reports"] == 3
    assert payload["report_categories"]["body_platform_line"] == [
        "modular_morphology_inventory_c0",
        "parametric_body_contract_c1",
        "canonical_fusion_fixture_c2",
    ]
    assert payload["quality_summaries"]["body_platform"]["gate_id"] == "canonical_fusion_fixture_c2"
    assert payload["quality_summaries"]["body_platform"]["fixture_id"] == "family_alpha::lower_body_core_hi"


def test_workbench_cli_demo_request_export_fixture(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    completed, payload = run_workbench_process(
        manifest_path=pack["manifest_path"],
        session_manifest_path=pack["session_manifest_path"],
        package_id="pkg_alpha",
        action_preset_id="showcase_root_translate_and_turn",
        animation_preset_id="MM_Attack_01",
        demo_request_export=True,
        demo_request_kind="animation_preview",
    )
    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "pass"
    assert payload["demo_request_control"]["status"] == "pass"
    assert payload["demo_request_control"]["operation"] == "export"
    assert payload["demo_request_control"]["request_kind"] == "animation_preview"
    assert payload["selected_default_package"] == "pkg_alpha"
    assert payload["selected_default_action_preset"] == "showcase_root_translate_and_turn"
    assert payload["selected_default_animation_preset"] == "MM_Attack_01"
    assert Path(payload["demo_request_control"]["request_json_path"]).exists()


def test_workbench_cli_handles_missing_governance_report(tmp_path: Path):
    pack = build_fixture_pack(tmp_path, include_governance=False)
    completed, payload = run_workbench_process(manifest_path=pack["manifest_path"])
    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "pass"
    assert payload["summary_counts"]["governance_line_reports"] == 0
    assert payload["governance_balance"]["status"] == "missing"
    assert payload["test_governance"]["status"] == "missing"
    assert payload["qa_full"]["status"] == "missing"
    assert payload["feature_ledger"]["status"] == "pass"


def test_workbench_cli_reads_q5c_quality_summary(tmp_path: Path):
    pack = build_fixture_pack(tmp_path, include_q5c=True, include_q5c_contrast=True)
    completed, payload = run_workbench_process(manifest_path=pack["manifest_path"])
    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "pass"
    assert payload["quality_summaries"]["q5c_lite"]["status"] == "pass"
    assert payload["quality_summaries"]["q5c_lite"]["diagnostic_class_counts"]["pass_stable"] == 1
    assert payload["quality_summaries"]["q5c_lite"]["risk_band_counts"]["watch"] == 1
    assert payload["quality_summaries"]["q5c_lite"]["highest_risk_band"] == "watch"
    assert payload["quality_summaries"]["q5c_lite"]["watchlist_count"] == 1
    assert payload["quality_summaries"]["q5c_lite"]["watchlist_package_ids"] == ["pkg_alpha"]
    assert payload["quality_summaries"]["q5c_lite"]["focus_package_id"] == "pkg_alpha"
    assert payload["quality_summaries"]["q5c_lite"]["focus_metric"] == "penetration_ratio_margin_to_failure"
    assert payload["quality_summaries"]["q5c_lite"]["focus_margin_to_failure"] == 0.02
    assert payload["quality_summaries"]["q5c_lite"]["packages"][0]["package_id"] == "pkg_alpha"
    assert payload["q5c_contrast_focus"]["status"] == "pass"
    assert payload["q5c_contrast_focus"]["selected_package_id"] == "pkg_alpha"
    assert payload["q5c_contrast_focus"]["case_ids"] == [
        "baseline_current",
        "best_pass_reference",
        "closest_fail_reference",
    ]
    assert payload["q5c_contrast_focus"]["recommended_preview_image_key"] == "q5c_contrast_pkg_alpha_baseline_current"
    assert payload["q5c_contrast_focus"]["compare_mode_status"] == "pass"
    assert len(payload["q5c_contrast_focus"]["compare_rows"]) == 3
    assert payload["q5c_contrast_focus"]["compare_summary_text"].startswith(
        "baseline_current -> closest_fail_reference | status pass -> fail"
    )


def test_workbench_cli_review_compare_index_fixture(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    for generated_at_utc, request_kind in (
        ("2026-04-11T10:00:00+00:00", "action_preview"),
        ("2026-04-11T10:01:00+00:00", "animation_preview"),
        ("2026-04-11T10:02:00+00:00", "action_preview"),
        ("2026-04-11T10:03:00+00:00", "animation_preview"),
    ):
        write_demo_review_history_event(
            session_manifest_path=pack["session_manifest_path"],
            source_review_state_path=str((tmp_path / "review.json").resolve()),
            source_replay_state_path=str((tmp_path / "replay.json").resolve()),
            session_id="playable_demo_e2_bootstrap",
            selected_package_id="pkg_alpha",
            request_kind=request_kind,
            replay_run=_replay_run(tmp_path, request_kind=request_kind, generated_at_utc=generated_at_utc),
        )
    history_state = load_demo_review_history_state(pack["session_manifest_path"])
    write_demo_review_compare_state(
        session_manifest_path=pack["session_manifest_path"],
        demo_review_history_state=history_state,
    )
    completed, payload = run_workbench_process(
        manifest_path=pack["manifest_path"],
        session_manifest_path=pack["session_manifest_path"],
        package_id="pkg_alpha",
        review_compare_index=1,
    )
    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "pass"
    assert payload["demo_review_compare_state"]["status"] == "pass"
    assert payload["demo_review_compare_focus"]["status"] == "pass"
    assert payload["demo_review_compare_focus"]["selected_pair_index"] == 1
    assert payload["demo_review_compare_focus"]["available_pair_count"] == 2
