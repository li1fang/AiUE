from __future__ import annotations

from pathlib import Path

from tests.t2.helpers import (
    REPO_ROOT,
    build_fixture_pack,
    create_invalid_manifest,
    create_missing_artifact_manifest,
    run_workbench_process,
)


def test_workbench_cli_seven_open_cycles(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    for _ in range(7):
        completed, payload = run_workbench_process(manifest_path=pack["manifest_path"])
        assert completed.returncode == 0, completed.stderr
        assert payload["status"] == "pass"
        assert payload["summary_counts"]["reports"] == 7
        assert payload["summary_counts"]["active_line_reports"] == 4
        assert payload["summary_counts"]["platform_line_reports"] == 3
        assert payload["slot_debugger"]["package_count"] == 1
        assert payload["demo_session"]["status"] == "pass"
        assert payload["demo_session"]["package_ids"] == ["pkg_alpha"]
        assert sorted(payload["demo_request"]["request_kinds"]) == ["action_preview", "animation_preview"]
        assert set(payload["report_categories"]) == {"active_line", "platform_line", "historical_other"}


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
    assert set(payload["report_categories"]) == {"active_line", "platform_line", "historical_other"}
    assert payload["summary_counts"]["active_line_reports"] >= 1
    assert payload["summary_counts"]["platform_line_reports"] >= 1
    assert payload["slot_debugger"]["package_count"] >= 1
    assert payload["demo_session"]["status"] in {"pass", "missing"}
    assert payload["demo_request"]["status"] in {"pass", "missing", "error"}


def test_workbench_cli_demo_request_export_fixture(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    completed, payload = run_workbench_process(
        manifest_path=pack["manifest_path"],
        session_manifest_path=pack["session_manifest_path"],
        demo_request_export=True,
        demo_request_kind="animation_preview",
    )
    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "pass"
    assert payload["demo_request_control"]["status"] == "pass"
    assert payload["demo_request_control"]["operation"] == "export"
    assert payload["demo_request_control"]["request_kind"] == "animation_preview"
    assert Path(payload["demo_request_control"]["request_json_path"]).exists()
