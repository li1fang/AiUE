from __future__ import annotations

from pathlib import Path

from aiue_t2.demo_request_runner import (
    export_demo_request,
    invoke_demo_request,
    load_demo_request_selection,
)

from tests.t2.helpers import REPO_ROOT, build_fixture_pack, run_demo_request_process


def test_demo_request_selection_resolves_fixture_action_request(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    selection = load_demo_request_selection(
        repo_root=REPO_ROOT,
        manifest_path=pack["manifest_path"],
        session_manifest_path=pack["session_manifest_path"],
        request_kind="action_preview",
    )
    assert selection.request_kind == "action_preview"
    assert selection.selected_package_id == "pkg_alpha"
    assert selection.request_payload["command"] == "action-preview"
    assert selection.request_payload["params"]["package_id"] == "pkg_alpha"
    assert selection.request_payload["params"]["shot_order"] == ["top"]


def test_demo_request_export_and_invoke_use_mocked_host_bridge(tmp_path: Path, monkeypatch):
    pack = build_fixture_pack(tmp_path)
    selection = load_demo_request_selection(
        repo_root=REPO_ROOT,
        manifest_path=pack["manifest_path"],
        session_manifest_path=pack["session_manifest_path"],
        request_kind="animation_preview",
    )
    request_json_path = tmp_path / "request.json"
    written_path = export_demo_request(selection, request_json_path=request_json_path)
    assert written_path.exists()

    captured = {}

    def _fake_run_host_auto_ue_cli(**kwargs):
        captured.update(kwargs)
        return {
            "host_key": kwargs.get("host_key"),
            "payload": {"result": {"status": "pass", "dry_run": kwargs.get("dry_run")}},
            "invocation": {"returncode": 0},
            "output_path": kwargs.get("output_path"),
        }

    monkeypatch.setattr("aiue_t2.demo_request_runner.run_host_auto_ue_cli", _fake_run_host_auto_ue_cli)
    result = invoke_demo_request(
        selection,
        workspace_config=tmp_path / "workspace.local.json",
        result_json_path=tmp_path / "result.json",
        dry_run=True,
    )
    assert result["status"] == "pass"
    assert result["dry_run"] is True
    assert Path(result["request_json_path"]).exists()
    assert captured["command"] == "animation-preview"
    assert captured["dry_run"] is True
    assert captured["params"]["animation_asset_path"] == "/Game/CombatMagicAnims/MM_Attack_01"
    assert captured["params"]["retarget_if_needed"] is True
    assert captured["params"]["retarget_target_ik_rig_asset_path"] == "/Game/PMXPipeline/Retarget/Source/IK_pkg_alpha"
    assert captured["params"]["pose_probe_bone_names"] == ["Bone_002", "Bone_R_011"]


def test_demo_request_cli_dump_request_json(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    request_json_path = tmp_path / "exported_request.json"
    completed, payload = run_demo_request_process(
        manifest_path=pack["manifest_path"],
        session_manifest_path=pack["session_manifest_path"],
        request_kind="action_preview",
        write_request_path=request_json_path,
    )
    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "pass"
    assert payload["request_kind"] == "action_preview"
    assert payload["request_payload"]["command"] == "action-preview"
    assert payload["request_json_path"] == str(request_json_path)
    assert request_json_path.exists()
