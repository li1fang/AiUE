from __future__ import annotations

import importlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, write_json
from aiue_unreal.command_catalog import get_command_metadata
from aiue_unreal.guards import GuardError, ensure_action_allowed
from aiue_unreal.mode_runner import normalize_mode


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_params_json(params_json: str | None) -> dict:
    if not params_json:
        return {}
    text = str(params_json).strip()
    if not text:
        return {}
    return json.loads(text)


def load_action_spec(path: str | None) -> dict | None:
    if not path:
        return None
    return load_json(path)


def normalize_action_spec(
    action_spec: dict | None,
    command: str | None,
    mode: str | None,
    params: dict | None,
    allow_destructive: bool,
    dry_run: bool,
    output_path: str | None
) -> dict:
    payload = dict(action_spec or {})
    if command:
        payload["command"] = command
    payload["mode"] = normalize_mode(payload.get("mode") or mode or "cmd_nullrhi")
    merged_params = dict(payload.get("params") or {})
    if params:
        merged_params.update(params)
    payload["params"] = merged_params
    payload["allow_destructive"] = bool(payload.get("allow_destructive") or allow_destructive)
    payload["dry_run"] = bool(payload.get("dry_run") or dry_run)
    if output_path:
        payload["output_path"] = output_path
    return payload


def default_action_output_path(workspace: dict, command_id: str, run_id: str, mode: str) -> Path:
    root = Path(workspace["paths"].get("auto_ue_cli_output_root") or Path(workspace["project_root"]) / "Saved" / "aiue" / "actions")
    return root / mode / run_id / f"{command_id}.json"


def load_command_handler(command_id: str):
    metadata = get_command_metadata(command_id)
    module = importlib.import_module(f"aiue_unreal.commands.{metadata['module']}")
    return metadata, module.run


def run_action(action_spec: dict, workspace: dict) -> tuple[dict, str]:
    run_id = uuid.uuid4().hex[:12]
    metadata, handler = load_command_handler(action_spec["command"])
    ensure_action_allowed(action_spec, metadata)
    mode = normalize_mode(action_spec.get("mode"))
    output_path = Path(action_spec.get("output_path") or default_action_output_path(workspace, action_spec["command"], run_id, mode)).expanduser().resolve()
    delegate_output_path = output_path.with_name(f"{output_path.stem}_host.json")
    context = {
        "workspace": workspace,
        "mode": mode,
        "run_id": run_id,
        "output_path": str(output_path),
        "delegate_output_path": str(delegate_output_path),
        "action_spec": action_spec,
        "command_metadata": metadata
    }

    if action_spec.get("dry_run"):
        payload = with_report_envelope(
            {
                "generated_at_utc": now_utc(),
                "run_id": run_id,
                "command": action_spec["command"],
                "mode": mode,
                "status": "dry_run",
                "success": True,
                "warnings": [],
                "errors": [],
                "result": {"action_spec": action_spec},
            },
            "aiue_action_result",
            workflow_pack=metadata.get("workflow_pack", "core"),
            compatibility=make_compatibility_block("aiue_action_result", notes=["dry_run_payload"]),
        )
        write_json(output_path, payload)
        return payload, str(output_path)

    try:
        result = handler(context, action_spec.get("params") or {})
        payload = with_report_envelope(
            {
                "generated_at_utc": now_utc(),
                "run_id": run_id,
                "command": action_spec["command"],
                "mode": mode,
                "status": "pass",
                "success": True,
                "warnings": list(result.get("warnings", [])),
                "errors": list(result.get("errors", [])),
                "result": result,
            },
            "aiue_action_result",
            workflow_pack=metadata.get("workflow_pack", "core"),
        )
    except GuardError as exc:
        payload = with_report_envelope(
            {
                "generated_at_utc": now_utc(),
                "run_id": run_id,
                "command": action_spec["command"],
                "mode": mode,
                "status": "blocked",
                "success": False,
                "warnings": [],
                "errors": [str(exc)],
                "result": {},
            },
            "aiue_action_result",
            workflow_pack=metadata.get("workflow_pack", "core"),
            compatibility=make_compatibility_block("aiue_action_result", notes=["guard_blocked"]),
        )
    except Exception as exc:
        payload = with_report_envelope(
            {
                "generated_at_utc": now_utc(),
                "run_id": run_id,
                "command": action_spec["command"],
                "mode": mode,
                "status": "fail",
                "success": False,
                "warnings": [],
                "errors": [str(exc)],
                "result": {},
            },
            "aiue_action_result",
            workflow_pack=metadata.get("workflow_pack", "core"),
        )

    write_json(output_path, payload)
    return payload, str(output_path)
