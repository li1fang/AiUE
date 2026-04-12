from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt

from aiue_t2.ui import WorkbenchWindow

from tests.t2.helpers import build_fixture_pack


def test_workbench_window_renders_fixture_pack(qtbot, tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    window = WorkbenchWindow(manifest_path=pack["manifest_path"])
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.current_dump_payload()["summary_counts"]["reports"] == 9)
    assert window.summary_cards["reports"].value_label.text() == "9"
    assert window.summary_cards["governance"].value_label.text() == "2"
    assert window.report_tree.topLevelItemCount() == 4
    assert window.metrics_table.rowCount() >= 1
    assert window.slot_table.rowCount() >= 3
    assert "visual_proof_v1" in window.details_text.toPlainText()
    assert "dynamic_balance_governance_progress" in window.current_dump_payload()["report_categories"]["governance_line"]
    assert "test_governance_round1" in window.current_dump_payload()["report_categories"]["governance_line"]
    assert window.current_dump_payload()["governance_balance"]["status"] == "attention"
    assert window.current_dump_payload()["test_governance"]["status"] == "attention"
    assert window.test_governance_summary.isVisible() is True
    assert "Test Governance ATTENTION" in window.test_governance_summary.text()
    assert "automation_ready False" in window.test_governance_summary.text()
    assert "signoff_ready False" in window.test_governance_summary.text()
    assert "manual_playable_demo_validation" in window.test_governance_summary.text()
    assert window.demo_session_package_list.count() == 1
    assert window.demo_action_preset_list.count() == 1
    assert window.demo_animation_preset_list.count() == 1
    assert "playable_demo_e2_bootstrap" in window.demo_session_summary.text()
    assert "pkg_alpha" in window.demo_package_details.toPlainText()
    assert window.invoke_session_round_button.text() == "Invoke Session Round"
    assert "ACTION_PREVIEW" in window.demo_request_summary.text().upper()
    assert '"action_preview"' in window.demo_request_text.toPlainText()
    assert '"animation_preview"' in window.demo_request_text.toPlainText()
    assert window.current_dump_payload()["demo_control_state"]["status"] == "missing"
    assert window.current_dump_payload()["demo_round_state"]["status"] == "missing"
    assert window.current_dump_payload()["demo_review_state"]["status"] == "missing"
    assert window.current_dump_payload()["demo_review_focus"]["status"] == "missing"
    assert window.current_dump_payload()["demo_review_replay_state"]["status"] == "missing"
    assert window.current_dump_payload()["demo_review_history_state"]["status"] == "missing"
    assert window.current_dump_payload()["demo_review_history_focus"]["status"] == "missing"
    assert window.current_dump_payload()["demo_review_compare_state"]["status"] == "missing"
    assert window.current_dump_payload()["demo_review_compare_focus"]["status"] == "missing"
    assert window.current_dump_payload()["selected_default_review_compare_index"] == 0
    assert "Review MISSING" in window.demo_review_summary.text()
    assert window.current_error_codes() == []
    assert window.q5c_quality_summary.isVisible() is False
    assert window.q5c_contrast_summary.isVisible() is False
    assert window.q5c_contrast_case_list.isVisible() is False
    assert window.q5c_contrast_triptych.isVisible() is False
    assert window.q5c_contrast_compare_panel.isVisible() is False


def test_workbench_window_shows_pv1_signoff_summary(qtbot, tmp_path: Path):
    pack = build_fixture_pack(tmp_path, include_pv1=True, include_e2b=True)
    window = WorkbenchWindow(manifest_path=pack["manifest_path"])
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.current_dump_payload()["pv1_signoff"]["status"] == "attention")
    assert window.pv1_signoff_summary.isVisible() is True
    assert "PV1 Signoff ATTENTION" in window.pv1_signoff_summary.text()
    assert "operator fixture_user" in window.pv1_signoff_summary.text()
    assert "package_ids pkg_alpha" in window.pv1_signoff_summary.text()


def test_workbench_window_shows_q5c_quality_summary(qtbot, tmp_path: Path):
    pack = build_fixture_pack(tmp_path, include_q5c=True, include_q5c_contrast=True)
    window = WorkbenchWindow(manifest_path=pack["manifest_path"])
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.current_dump_payload()["quality_summaries"]["q5c_lite"]["status"] == "pass")
    assert window.q5c_quality_summary.isVisible() is True
    assert "Q5C-lite PASS" in window.q5c_quality_summary.text()
    assert "pass_stable:1" in window.q5c_quality_summary.text()
    assert "risk watch | watch 1" in window.q5c_quality_summary.text()
    assert "focus penetration_ratio_margin_to_failure=0.0200 @ pkg_alpha" in window.q5c_quality_summary.text()
    assert window.q5c_contrast_summary.isVisible() is True
    assert "Q5C contrast PASS | package pkg_alpha" in window.q5c_contrast_summary.text()
    assert window.q5c_contrast_case_list.isVisible() is True
    assert window.q5c_contrast_triptych.isVisible() is True
    assert window.q5c_contrast_compare_panel.isVisible() is True
    assert window.q5c_contrast_case_list.count() == 3
    assert window.q5c_contrast_case_list.item(0).text().startswith("baseline_current | PASS")
    assert window.current_dump_payload()["q5c_contrast_focus"]["recommended_preview_image_key"] == "q5c_contrast_pkg_alpha_baseline_current"
    assert window.current_dump_payload()["selected_default_image"] == "q5c_contrast_pkg_alpha_baseline_current"
    assert window.q5c_contrast_triptych.case_title_labels["baseline_current"].text().startswith("Baseline | PASS")
    assert window.q5c_contrast_triptych.case_title_labels["best_pass_reference"].text().startswith("Best Pass | PASS")
    assert window.q5c_contrast_triptych.case_title_labels["closest_fail_reference"].text().startswith("Closest Fail | FAIL")
    assert window.q5c_contrast_triptych.case_image_labels["baseline_current"].pixmap() is not None
    assert not window.q5c_contrast_triptych.case_image_labels["baseline_current"].pixmap().isNull()
    assert "baseline_current -> closest_fail_reference" in window.q5c_contrast_compare_panel.summary_label.text()
    assert window.q5c_contrast_compare_panel.compare_table.rowCount() == 3
    assert window.q5c_contrast_compare_panel.compare_table.item(1, 0).text() == "baseline_current -> closest_fail_reference"
    assert window.q5c_contrast_compare_panel.compare_table.item(1, 1).text() == "pass -> fail"
    assert "floating +0.0407" in window.q5c_contrast_compare_panel.compare_table.item(1, 5).text()
    window.q5c_contrast_case_list.setCurrentRow(2)
    qtbot.waitUntil(
        lambda: window.current_dump_payload()["selected_default_image"] == "q5c_contrast_pkg_alpha_closest_fail_reference"
    )


def test_workbench_window_shows_diversity_matrix_summary(qtbot, tmp_path: Path):
    pack = build_fixture_pack(tmp_path, include_dv1=True)
    window = WorkbenchWindow(manifest_path=pack["manifest_path"])
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.current_dump_payload()["quality_summaries"]["diversity_matrix"]["status"] == "pass")
    assert window.diversity_matrix_summary.isVisible() is True
    assert "DV1 Diversity Matrix PASS" in window.diversity_matrix_summary.text()
    assert "characters 2" in window.diversity_matrix_summary.text()
    assert "animations 3" in window.diversity_matrix_summary.text()


def test_workbench_window_prefers_dv2_diversity_matrix_summary(qtbot, tmp_path: Path):
    pack = build_fixture_pack(tmp_path, include_dv2=True)
    window = WorkbenchWindow(manifest_path=pack["manifest_path"])
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.current_dump_payload()["quality_summaries"]["diversity_matrix"]["gate_id"] == "diversity_matrix_dv2")
    assert window.diversity_matrix_summary.isVisible() is True
    assert "DV2 Diversity Matrix PASS" in window.diversity_matrix_summary.text()
    assert "clothing 2" in window.diversity_matrix_summary.text()


def test_workbench_window_shows_e2c_showcase_summary(qtbot, tmp_path: Path):
    pack = build_fixture_pack(tmp_path, include_e2c=True)
    window = WorkbenchWindow(manifest_path=pack["manifest_path"])
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.current_dump_payload()["quality_summaries"]["e2c_showcase_polish"]["status"] == "pass")
    assert window.demo_showcase_summary.isVisible() is True
    assert "E2C Showcase Polish PASS" in window.demo_showcase_summary.text()
    assert "replay yes" in window.demo_showcase_summary.text()
    assert "compare yes" in window.demo_showcase_summary.text()


def test_workbench_window_demo_request_controls(qtbot, tmp_path: Path, monkeypatch):
    pack = build_fixture_pack(tmp_path)
    workspace_config_path = tmp_path / "local" / "pipeline_workspace.local.json"
    workspace_config_path.parent.mkdir(parents=True, exist_ok=True)
    workspace_config_path.write_text("{}", encoding="utf-8")

    def fake_invoke(selection, *, workspace_config, result_json_path=None, dry_run=False):
        request_json_path = tmp_path / f"{selection.request_kind}_request.json"
        request_json_path.write_text("{}", encoding="utf-8")
        resolved_result_path = Path(result_json_path or (tmp_path / "dry_run_result.json"))
        resolved_result_path.write_text("{}", encoding="utf-8")
        before_image = tmp_path / "before.png"
        after_image = tmp_path / "after.png"
        before_image.write_text("fixture", encoding="utf-8")
        after_image.write_text("fixture", encoding="utf-8")
        return {
            "status": "pass",
            "request_kind": selection.request_kind,
            "dry_run": dry_run,
            "selected_package_id": selection.selected_package_id,
            "selected_action_preset_id": selection.selected_action_preset_id,
            "selected_animation_preset_id": selection.selected_animation_preset_id,
            "request_payload": selection.request_payload,
            "request_json_path": str(request_json_path),
            "result_json_path": str(resolved_result_path),
            "host_key": "demo",
            "payload": {
                "status": "pass",
                "generated_at_utc": "2026-04-11T07:10:00+00:00",
                "result": {
                    "status": "pass",
                    "shots": [
                        {
                            "before": {
                                "image_path": str(before_image.resolve()),
                                "subject_screen_coverage": 0.08,
                                "weapon_screen_coverage": 0.01,
                                "line_of_sight_clear": True,
                                "tracked_slot_coverages": {"fx": {"coverage_ratio": 0.005}},
                            },
                            "after": {
                                "image_path": str(after_image.resolve()),
                                "subject_screen_coverage": 0.07,
                                "weapon_screen_coverage": 0.01,
                                "line_of_sight_clear": True,
                                "tracked_slot_coverages": {"fx": {"coverage_ratio": 0.004}},
                            },
                        }
                    ],
                    "transform_delta": {"distance_delta": 85.0, "yaw_delta": 24.0},
                    "native_animation_pose_evaluation": {"pose_changed": True, "changed_bone_count": 12},
                    "pose_probe_delta": {"moving_bone_count": 8, "max_location_delta": 321.0},
                },
            },
        }

    monkeypatch.setattr("aiue_t2.ui.invoke_demo_request", fake_invoke)

    window = WorkbenchWindow(
        manifest_path=pack["manifest_path"],
        session_manifest_path=pack["session_manifest_path"],
        workspace_config_path=workspace_config_path,
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.demo_session_package_list.count() == 1)

    qtbot.mouseClick(window.export_animation_request_button, Qt.LeftButton)
    payload = window.current_dump_payload()
    assert payload["demo_request_control"]["status"] == "pass"
    assert payload["demo_request_control"]["operation"] == "export"
    assert payload["demo_request_control"]["request_kind"] == "animation_preview"
    assert Path(payload["demo_request_control"]["request_json_path"]).exists()

    qtbot.mouseClick(window.dry_run_animation_request_button, Qt.LeftButton)
    payload = window.current_dump_payload()
    assert payload["demo_request_control"]["status"] == "pass"
    assert payload["demo_request_control"]["operation"] == "dry_run"
    assert payload["demo_request_control"]["request_kind"] == "animation_preview"
    assert payload["demo_request_control"]["host_key"] == "demo"
    assert payload["demo_request_control"]["workspace_config_path"] == str(workspace_config_path.resolve())
    assert payload["demo_request_control"]["dry_run"] is True
    assert payload["demo_control_state"]["status"] == "pass"
    assert payload["demo_control_state"]["selected_package_id"] == "pkg_alpha"
    assert payload["demo_control_state"]["last_runs_by_package"]["pkg_alpha"]["animation_preview"]["credibility_summary"]["animation_pose_verified"] is True

    qtbot.mouseClick(window.invoke_action_request_button, Qt.LeftButton)
    payload = window.current_dump_payload()
    assert payload["demo_request_control"]["status"] == "pass"
    assert payload["demo_request_control"]["operation"] == "invoke"
    assert payload["demo_request_control"]["request_kind"] == "action_preview"
    assert payload["demo_request_control"]["host_key"] == "demo"
    assert payload["demo_request_control"]["dry_run"] is False
    assert payload["demo_control_state"]["last_runs_by_package"]["pkg_alpha"]["action_preview"]["credibility_summary"]["action_motion_verified"] is True
    assert "action_preview" in window.demo_control_state_text.toPlainText()

    qtbot.mouseClick(window.invoke_session_round_button, Qt.LeftButton)
    payload = window.current_dump_payload()
    assert payload["demo_round_control"]["status"] == "pass"
    assert payload["demo_round_control"]["operation"] == "invoke_session_round"
    assert payload["demo_round_state"]["status"] == "pass"
    assert payload["demo_review_state"]["status"] == "pass"
    assert payload["demo_review_focus"]["status"] == "pass"
    assert payload["demo_review_focus"]["selected_package_id"] == "pkg_alpha"
    assert payload["demo_review_replay_state"]["status"] == "missing"
    assert payload["demo_review_history_state"]["status"] == "missing"
    assert payload["demo_review_compare_state"]["status"] == "missing"
    assert payload["demo_round_state"]["counts"]["package_count"] == 1
    assert payload["demo_round_state"]["counts"]["action_motion_verified"] == 1
    assert payload["demo_round_state"]["counts"]["animation_pose_verified"] == 1
    assert payload["demo_review_state"]["summary"]["passing_packages"] == 1
    assert payload["demo_review_state"]["package_reviews"][0]["action_review"]["status"] == "pass"
    assert payload["demo_review_state"]["package_reviews"][0]["animation_review"]["status"] == "pass"
    assert "Review PASS" in window.demo_review_summary.text()
    assert "round_state" in window.demo_control_state_text.toPlainText()


def test_workbench_window_demo_review_navigation_buttons(qtbot, tmp_path: Path, monkeypatch):
    pack = build_fixture_pack(tmp_path)
    workspace_config_path = tmp_path / "local" / "pipeline_workspace.local.json"
    workspace_config_path.parent.mkdir(parents=True, exist_ok=True)
    workspace_config_path.write_text("{}", encoding="utf-8")
    opened_paths: list[str] = []

    def fake_invoke(selection, *, workspace_config, result_json_path=None, dry_run=False):
        request_json_path = tmp_path / f"{selection.request_kind}_request.json"
        request_json_path.write_text("{}", encoding="utf-8")
        resolved_result_path = Path(result_json_path or (tmp_path / f"{selection.request_kind}_result.json"))
        resolved_result_path.write_text("{}", encoding="utf-8")
        before_image = tmp_path / f"{selection.request_kind}_before.png"
        after_image = tmp_path / f"{selection.request_kind}_after.png"
        before_image.write_text("fixture", encoding="utf-8")
        after_image.write_text("fixture", encoding="utf-8")
        return {
            "status": "pass",
            "request_kind": selection.request_kind,
            "dry_run": dry_run,
            "selected_package_id": selection.selected_package_id,
            "selected_action_preset_id": selection.selected_action_preset_id,
            "selected_animation_preset_id": selection.selected_animation_preset_id,
            "request_payload": selection.request_payload,
            "request_json_path": str(request_json_path),
            "result_json_path": str(resolved_result_path),
            "host_key": "demo",
            "payload": {
                "status": "pass",
                "generated_at_utc": "2026-04-11T07:10:00+00:00",
                "result": {
                    "status": "pass",
                    "shots": [
                        {
                            "before": {
                                "image_path": str(before_image.resolve()),
                                "subject_screen_coverage": 0.08,
                                "weapon_screen_coverage": 0.01,
                                "line_of_sight_clear": True,
                                "tracked_slot_coverages": {"fx": {"coverage_ratio": 0.005}},
                            },
                            "after": {
                                "image_path": str(after_image.resolve()),
                                "subject_screen_coverage": 0.07,
                                "weapon_screen_coverage": 0.01,
                                "line_of_sight_clear": True,
                                "tracked_slot_coverages": {"fx": {"coverage_ratio": 0.004}},
                            },
                        }
                    ],
                    "transform_delta": {"distance_delta": 85.0, "yaw_delta": 24.0},
                    "native_animation_pose_evaluation": {"pose_changed": True, "changed_bone_count": 12},
                    "pose_probe_delta": {"moving_bone_count": 8, "max_location_delta": 321.0},
                },
            },
        }

    monkeypatch.setattr("aiue_t2.ui.invoke_demo_request", fake_invoke)
    window = WorkbenchWindow(
        manifest_path=pack["manifest_path"],
        session_manifest_path=pack["session_manifest_path"],
        workspace_config_path=workspace_config_path,
    )
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_open_in_explorer", lambda path: opened_paths.append(str(path)))
    window.show()
    qtbot.waitUntil(lambda: window.demo_session_package_list.count() == 1)

    qtbot.mouseClick(window.invoke_session_round_button, Qt.LeftButton)
    payload = window.current_dump_payload()
    assert payload["demo_review_focus"]["status"] == "pass"

    qtbot.mouseClick(window.open_review_artifact_button, Qt.LeftButton)
    qtbot.mouseClick(window.open_hero_before_button, Qt.LeftButton)
    qtbot.mouseClick(window.open_action_after_button, Qt.LeftButton)
    qtbot.mouseClick(window.open_animation_after_button, Qt.LeftButton)

    assert any(path.endswith("playable_demo_e2_review_state.json") for path in opened_paths)
    assert any(path.endswith(".png") for path in opened_paths)


def test_workbench_window_demo_review_replay_controls(qtbot, tmp_path: Path, monkeypatch):
    pack = build_fixture_pack(tmp_path)
    workspace_config_path = tmp_path / "local" / "pipeline_workspace.local.json"
    workspace_config_path.parent.mkdir(parents=True, exist_ok=True)
    workspace_config_path.write_text("{}", encoding="utf-8")

    def fake_invoke(selection, *, workspace_config, result_json_path=None, dry_run=False):
        request_json_path = tmp_path / f"{selection.request_kind}_request.json"
        request_json_path.write_text("{}", encoding="utf-8")
        resolved_result_path = Path(result_json_path or (tmp_path / f"{selection.request_kind}_result.json"))
        resolved_result_path.write_text("{}", encoding="utf-8")
        before_image = tmp_path / f"{selection.request_kind}_before.png"
        after_image = tmp_path / f"{selection.request_kind}_after.png"
        before_image.write_text("fixture", encoding="utf-8")
        after_image.write_text("fixture", encoding="utf-8")
        return {
            "status": "pass",
            "request_kind": selection.request_kind,
            "dry_run": dry_run,
            "selected_package_id": selection.selected_package_id,
            "selected_action_preset_id": selection.selected_action_preset_id,
            "selected_animation_preset_id": selection.selected_animation_preset_id,
            "request_payload": selection.request_payload,
            "request_json_path": str(request_json_path),
            "result_json_path": str(resolved_result_path),
            "host_key": "demo",
            "payload": {
                "status": "pass",
                "generated_at_utc": "2026-04-11T07:10:00+00:00",
                "result": {
                    "status": "pass",
                    "shots": [
                        {
                            "before": {
                                "image_path": str(before_image.resolve()),
                                "subject_screen_coverage": 0.08,
                                "weapon_screen_coverage": 0.01,
                                "line_of_sight_clear": True,
                                "tracked_slot_coverages": {"fx": {"coverage_ratio": 0.005}},
                            },
                            "after": {
                                "image_path": str(after_image.resolve()),
                                "subject_screen_coverage": 0.07,
                                "weapon_screen_coverage": 0.01,
                                "line_of_sight_clear": True,
                                "tracked_slot_coverages": {"fx": {"coverage_ratio": 0.004}},
                            },
                        }
                    ],
                    "transform_delta": {"distance_delta": 85.0, "yaw_delta": 24.0},
                    "native_animation_pose_evaluation": {"pose_changed": True, "changed_bone_count": 12},
                    "pose_probe_delta": {"moving_bone_count": 8, "max_location_delta": 321.0},
                },
            },
        }

    opened_paths: list[str] = []
    monkeypatch.setattr("aiue_t2.ui.invoke_demo_request", fake_invoke)
    window = WorkbenchWindow(
        manifest_path=pack["manifest_path"],
        session_manifest_path=pack["session_manifest_path"],
        workspace_config_path=workspace_config_path,
    )
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_open_in_explorer", lambda path: opened_paths.append(str(path)))
    window.show()
    qtbot.waitUntil(lambda: window.demo_session_package_list.count() == 1)

    qtbot.mouseClick(window.invoke_session_round_button, Qt.LeftButton)
    assert window.current_dump_payload()["demo_review_focus"]["status"] == "pass"

    qtbot.mouseClick(window.replay_action_button, Qt.LeftButton)
    payload = window.current_dump_payload()
    assert payload["demo_review_replay_control"]["status"] == "pass"
    assert payload["demo_review_replay_control"]["request_kind"] == "action_preview"
    assert payload["demo_review_replay_state"]["status"] == "pass"
    assert payload["demo_review_replay_state"]["last_replays_by_package"]["pkg_alpha"]["action_preview"]["credibility_summary"]["action_motion_verified"] is True

    qtbot.mouseClick(window.replay_animation_button, Qt.LeftButton)
    payload = window.current_dump_payload()
    assert payload["demo_review_replay_control"]["status"] == "pass"
    assert payload["demo_review_replay_control"]["request_kind"] == "animation_preview"
    assert payload["demo_review_replay_state"]["last_replays_by_package"]["pkg_alpha"]["animation_preview"]["credibility_summary"]["animation_pose_verified"] is True
    assert payload["demo_review_history_state"]["status"] == "pass"
    assert payload["demo_review_history_focus"]["status"] == "pass"
    assert payload["demo_review_history_focus"]["event_count"] == 2
    assert payload["demo_review_history_focus"]["replay_kinds"] == ["action_preview", "animation_preview"]
    assert payload["demo_review_compare_state"]["status"] == "pass"
    assert payload["demo_review_compare_focus"]["status"] == "pass"
    assert payload["demo_review_compare_focus"]["compare_ready"] is True
    assert payload["demo_review_compare_focus"]["latest_action_event"]["request_kind"] == "action_preview"
    assert payload["demo_review_compare_focus"]["latest_animation_event"]["request_kind"] == "animation_preview"
    assert "Review History PASS" in window.demo_review_history_summary.text()
    assert "Review Compare PASS" in window.demo_review_compare_summary.text()
    assert "Review Replay PASS" in window.demo_review_replay_summary.text()

    qtbot.mouseClick(window.replay_action_button, Qt.LeftButton)
    qtbot.mouseClick(window.replay_animation_button, Qt.LeftButton)
    payload = window.current_dump_payload()
    assert payload["demo_review_compare_focus"]["available_pair_count"] == 2
    assert payload["demo_review_compare_focus"]["selected_pair_index"] == 0
    assert "Pair 1/2" in window.demo_review_compare_summary.text()

    qtbot.mouseClick(window.older_compare_button, Qt.LeftButton)
    payload = window.current_dump_payload()
    assert payload["demo_review_compare_focus"]["selected_pair_index"] == 1
    assert "Pair 2/2" in window.demo_review_compare_summary.text()

    qtbot.mouseClick(window.open_compare_action_after_button, Qt.LeftButton)
    qtbot.mouseClick(window.open_compare_animation_after_button, Qt.LeftButton)
    assert len(opened_paths) == 2
    assert all(path.endswith(".png") for path in opened_paths)

    qtbot.mouseClick(window.newer_compare_button, Qt.LeftButton)
    payload = window.current_dump_payload()
    assert payload["demo_review_compare_focus"]["selected_pair_index"] == 0
