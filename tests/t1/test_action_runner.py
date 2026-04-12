from __future__ import annotations

from pathlib import Path

from aiue_unreal.action_runner import run_action
from aiue_unreal.execution_errors import ActionResultError


def test_run_action_preserves_structured_result_for_host_failures(tmp_path: Path, monkeypatch):
    workspace = {
        "project_root": str(tmp_path),
        "paths": {
            "auto_ue_cli_output_root": str(tmp_path / "actions"),
        },
    }

    def _fake_load_command_handler(command_id: str):
        assert command_id == "validate-package"
        return {"workflow_pack": "pmx_pipeline"}, _fake_handler

    def _fake_handler(context: dict, params: dict):
        raise ActionResultError(
            "validation failed",
            result={
                "status": "fail",
                "manifest_path": "C:/trial/manifest.json",
                "import_report_exists": False,
                "validation_report_exists": False,
                "host_action_result_path": "C:/trial/validate_package.action_host.json",
                "host_returncode": 1,
                "errors": [
                    "import_report_missing:C:/trial/ue_import_report.local.json",
                    "validation_report_missing:C:/trial/ue_validation_report.local.json",
                ],
            },
            errors=[
                "import_report_missing:C:/trial/ue_import_report.local.json",
                "validation_report_missing:C:/trial/ue_validation_report.local.json",
            ],
        )

    monkeypatch.setattr("aiue_unreal.action_runner.load_command_handler", _fake_load_command_handler)
    monkeypatch.setattr("aiue_unreal.action_runner.ensure_action_allowed", lambda *_args, **_kwargs: None)

    payload, output_path = run_action(
        {
            "command": "validate-package",
            "mode": "cmd_nullrhi",
            "params": {"manifest": "C:/trial/manifest.json"},
            "output_path": str(tmp_path / "validate_package.action.json"),
        },
        workspace,
    )

    assert payload["status"] == "fail"
    assert payload["success"] is False
    assert payload["result"]["manifest_path"] == "C:/trial/manifest.json"
    assert payload["result"]["import_report_exists"] is False
    assert payload["result"]["host_returncode"] == 1
    assert "import_report_missing:C:/trial/ue_import_report.local.json" in payload["errors"]
    assert Path(output_path).exists()
