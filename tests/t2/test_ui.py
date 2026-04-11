from __future__ import annotations

from pathlib import Path

from aiue_t2.ui import WorkbenchWindow

from tests.t2.helpers import build_fixture_pack


def test_workbench_window_renders_fixture_pack(qtbot, tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    window = WorkbenchWindow(manifest_path=pack["manifest_path"])
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.current_dump_payload()["summary_counts"]["reports"] == 7)
    assert window.summary_cards["reports"].value_label.text() == "7"
    assert window.report_tree.topLevelItemCount() == 3
    assert window.metrics_table.rowCount() >= 1
    assert window.slot_table.rowCount() >= 3
    assert "visual_proof_v1" in window.details_text.toPlainText()
    assert window.demo_session_package_list.count() == 1
    assert window.demo_action_preset_list.count() == 1
    assert window.demo_animation_preset_list.count() == 1
    assert "playable_demo_e2_bootstrap" in window.demo_session_summary.text()
    assert "pkg_alpha" in window.demo_package_details.toPlainText()
    assert "ACTION_PREVIEW" in window.demo_request_summary.text().upper()
    assert '"action_preview"' in window.demo_request_text.toPlainText()
    assert '"animation_preview"' in window.demo_request_text.toPlainText()
    assert window.current_error_codes() == []
