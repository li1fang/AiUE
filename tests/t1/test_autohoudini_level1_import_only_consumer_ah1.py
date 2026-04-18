from __future__ import annotations

import json
import sys
from pathlib import Path


PMX_PIPELINE_ROOT = Path(__file__).resolve().parents[2] / "workflows" / "pmx_pipeline"
if str(PMX_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PMX_PIPELINE_ROOT))

from autohoudini_level1 import (  # noqa: E402
    REQUEST_OPERATION,
    REQUEST_SCHEMA_VERSION,
    build_external_result,
    build_import_summary,
    load_level1_request,
    resolve_request_json_path,
)
from aiue_unreal.commands import import_level1_curve_bundle as command_module  # noqa: E402


def _request_payload(**overrides) -> dict:
    payload = {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "operation": REQUEST_OPERATION,
        "toy_yard_motion_view_root": "C:/Projects/toy-yard/05_publish/aiue_motion/autohoudini-level1-demo",
        "package_manifest_path": "C:/Projects/toy-yard/05_publish/aiue_motion/autohoudini-level1-demo/clips/pkg_demo/manifest.json",
        "summary_path": "C:/Projects/toy-yard/05_publish/aiue_motion/autohoudini-level1-demo/summary/motion_suite_summary.json",
        "registry_path": "C:/Projects/toy-yard/05_publish/aiue_motion/autohoudini-level1-demo/summary/motion_clip_registry.json",
        "packet_check_path": "C:/Projects/toy-yard/05_publish/aiue_motion/autohoudini-level1-demo/summary/motion_packet_check.json",
        "producer_signal_path": "C:/Projects/toy-yard/05_publish/aiue_motion/autohoudini-level1-demo/summary/communication_signal.json",
        "curve_csv_path": "C:/Projects/toy-yard/05_publish/aiue_motion/autohoudini-level1-demo/clips/pkg_demo/ue-curves.csv",
        "ue_manifest_path": "C:/Projects/toy-yard/05_publish/aiue_motion/autohoudini-level1-demo/clips/pkg_demo/ue-manifest.json",
        "host_key": "demo",
        "target_package_id": "pkg_demo_001",
        "target_curve_asset_name": "AH_Level1_Test_Curves",
        "curve_asset_root": "/Game/AutoHoudini/Curves",
        "runtime_ready_only": True,
        "consumer_context": {
            "counterparty_system": "autohoudini",
            "source_lane": "autohoudini_level1",
            "transport": "toy_yard_publish_profile",
            "current_aiue_support": "planned_not_implemented",
            "notes": "fixture",
        },
        "target_bone": "spine_03",
        "target_host_blueprint_asset_path": "/Game/AiUE/Hosts/BP_AutoHoudiniPreview.BP_AutoHoudiniPreview",
        "target_skeleton_asset_path": "/Game/AiUE/ImportedAssets/SK_Target.SK_Target_Skeleton",
        "preview_level_path": "/Game/Levels/DefaultLevel",
        "unreal_import_mode": "curve_float_asset_set",
    }
    payload.update(overrides)
    return payload


def _write_request(path: Path, **overrides) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_request_payload(**overrides), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def test_resolve_request_json_path_from_motion_view_root(tmp_path: Path):
    request_path = _write_request(tmp_path / "workspace_views" / "aiue_level1_consumer_request.json")
    workspace = {
        "paths": {
            "toy_yard_motion_view_root": str(tmp_path),
        }
    }

    resolved = resolve_request_json_path(workspace, None)

    assert resolved == request_path.resolve()


def test_load_level1_request_rejects_missing_required_field(tmp_path: Path):
    request_path = _write_request(tmp_path / "request.json", curve_asset_root="")

    try:
        load_level1_request(request_path)
    except ValueError as exc:
        assert "autohoudini_level1_request_missing_field:curve_asset_root" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing curve_asset_root")


def test_build_external_result_marks_preview_not_requested(tmp_path: Path):
    request_payload = _request_payload()
    request_path = _write_request(tmp_path / "request.json")
    import_action_path = tmp_path / "import_level1_curve_bundle.action.json"
    combined_result_path = tmp_path / "autohoudini_aiue_level1_consumer_result_v0.json"
    import_action_payload = {
        "status": "pass",
        "generated_at_utc": "2026-04-18T12:00:00+00:00",
        "warnings": [],
        "errors": [],
        "result": {
            "status": "pass",
            "generated_at_utc": "2026-04-18T12:00:00+00:00",
            "resolved_import_mode": "curve_float_asset_set",
            "bundle_summary": {
                "row_count": 10,
                "channel_count": 4,
                "target_bone": "spine_03",
            },
            "imported_curve_assets": [{}, {}, {}, {}],
            "warnings": [],
            "errors": [],
        },
    }

    external_result = build_external_result(
        import_action_payload=import_action_payload,
        import_action_result_path=str(import_action_path),
        request_payload=request_payload,
        request_json_path=request_path,
        workspace_config_path=tmp_path / "workspace.json",
        combined_result_path=combined_result_path,
        host_key="demo",
    )

    assert external_result["status"] == "pass"
    assert external_result["execution_shell"]["mode"] == "import_only"
    assert external_result["preview_summary"]["requested"] is False
    assert external_result["preview_summary"]["status"] == "not_requested"
    assert external_result["import_summary"]["imported_asset_count"] == 4


def test_build_import_summary_aggregates_host_and_action_errors():
    summary = build_import_summary(
        {
            "status": "fail",
            "warnings": ["action_warning"],
            "errors": ["action_error"],
            "result": {
                "status": "fail",
                "generated_at_utc": "2026-04-18T12:00:00+00:00",
                "resolved_import_mode": "curve_float_asset_set",
                "bundle_summary": {"row_count": 2, "channel_count": 1, "target_bone": "spine_03"},
                "imported_curve_assets": [],
                "warnings": ["host_warning"],
                "errors": ["host_error"],
            },
        }
    )

    assert summary["status"] == "fail"
    assert summary["warnings"] == ["action_warning", "host_warning"]
    assert summary["errors"] == ["action_error", "host_error"]


def test_import_level1_command_prefers_request_host_key(tmp_path: Path, monkeypatch):
    request_path = _write_request(tmp_path / "request.json", host_key="demo")
    workspace = {
        "config_path": str(tmp_path / "workspace.json"),
        "paths": {
            "auto_ue_cli_output_root": str(tmp_path / "actions"),
        },
        "default_host_routes": {
            "import-level1-curve-bundle": "kernel",
        },
    }

    def _fake_resolve_host_paths(workspace_or_config, command=None, host_key=None):
        return {"host_key": str(host_key or "kernel")}

    def _fake_run_host_auto_ue_cli(**kwargs):
        assert kwargs["host_key"] == "demo"
        return {
            "host_key": "demo",
            "output_path": str(tmp_path / "host_result.json"),
            "invocation": {"returncode": 0},
            "payload": {
                "warnings": [],
                "errors": [],
                "result": {
                    "status": "pass",
                    "resolved_import_mode": "curve_float_asset_set",
                    "bundle_summary": {"row_count": 10, "channel_count": 4},
                    "imported_curve_assets": [{}, {}, {}, {}],
                    "warnings": [],
                    "errors": [],
                },
            },
        }

    monkeypatch.setattr(command_module, "resolve_host_paths", _fake_resolve_host_paths)
    monkeypatch.setattr(command_module, "run_host_auto_ue_cli", _fake_run_host_auto_ue_cli)

    result = command_module.run(
        {
            "workspace": workspace,
            "mode": "cmd_nullrhi",
            "output_path": str(tmp_path / "action.json"),
            "delegate_output_path": str(tmp_path / "action_host.json"),
            "action_spec": {"allow_destructive": False, "dry_run": False},
        },
        {"request_json": str(request_path)},
    )

    assert result["host_key"] == "demo"
    assert result["request_json_path"] == str(request_path.resolve())


def test_import_level1_command_uses_workspace_route_when_request_host_key_missing(tmp_path: Path, monkeypatch):
    request_path = _write_request(tmp_path / "request.json", host_key="")
    workspace = {
        "config_path": str(tmp_path / "workspace.json"),
        "paths": {
            "auto_ue_cli_output_root": str(tmp_path / "actions"),
        },
        "default_host_routes": {
            "import-level1-curve-bundle": "kernel",
        },
    }

    def _fake_resolve_host_paths(workspace_or_config, command=None, host_key=None):
        resolved = str(host_key or workspace["default_host_routes"]["import-level1-curve-bundle"])
        return {"host_key": resolved}

    def _fake_run_host_auto_ue_cli(**kwargs):
        assert kwargs["host_key"] == "kernel"
        return {
            "host_key": "kernel",
            "output_path": str(tmp_path / "host_result.json"),
            "invocation": {"returncode": 0},
            "payload": {
                "warnings": [],
                "errors": [],
                "result": {
                    "status": "pass",
                    "resolved_import_mode": "curve_float_asset_set",
                    "bundle_summary": {"row_count": 10, "channel_count": 4},
                    "imported_curve_assets": [{}, {}, {}, {}],
                    "warnings": [],
                    "errors": [],
                },
            },
        }

    monkeypatch.setattr(command_module, "resolve_host_paths", _fake_resolve_host_paths)
    monkeypatch.setattr(command_module, "run_host_auto_ue_cli", _fake_run_host_auto_ue_cli)

    result = command_module.run(
        {
            "workspace": workspace,
            "mode": "cmd_nullrhi",
            "output_path": str(tmp_path / "action.json"),
            "delegate_output_path": str(tmp_path / "action_host.json"),
            "action_spec": {"allow_destructive": False, "dry_run": False},
        },
        {"request_json": str(request_path)},
    )

    assert result["host_key"] == "kernel"
