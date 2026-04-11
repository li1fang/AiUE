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


def test_workbench_window_demo_request_controls(qtbot, tmp_path: Path, monkeypatch):
    pack = build_fixture_pack(tmp_path)
    workspace_config_path = tmp_path / "local" / "pipeline_workspace.local.json"
    workspace_config_path.parent.mkdir(parents=True, exist_ok=True)
    workspace_config_path.write_text("{}", encoding="utf-8")

    def fake_invoke(selection, *, workspace_config, result_json_path=None, dry_run=False):
        return {
            "status": "pass",
            "request_kind": selection.request_kind,
            "dry_run": dry_run,
            "selected_package_id": selection.selected_package_id,
            "request_payload": selection.request_payload,
            "result_json_path": str(tmp_path / "dry_run_result.json"),
            "host_key": "demo",
            "payload": {"workspace_config": str(workspace_config)},
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

    qtbot.mouseClick(window.invoke_action_request_button, Qt.LeftButton)
    payload = window.current_dump_payload()
    assert payload["demo_request_control"]["status"] == "pass"
    assert payload["demo_request_control"]["operation"] == "invoke"
    assert payload["demo_request_control"]["request_kind"] == "action_preview"
    assert payload["demo_request_control"]["host_key"] == "demo"
    assert payload["demo_request_control"]["dry_run"] is False
