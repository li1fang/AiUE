from __future__ import annotations

import json
import subprocess
from pathlib import Path

from aiue_core.schema_utils import load_json, load_workspace_config
from aiue_unreal.execution_errors import ActionResultError

DEFAULT_HOST_ROUTES = {
    "import-package": "kernel",
    "build-equipment-registry": "kernel",
    "inspect-host": "kernel",
    "inspect-host-visual": "kernel",
    "inspect-visible-conflict": "demo",
    "inspect-slot-runtime": "kernel",
    "composition-validation": "kernel",
    "validate-package": "kernel",
    "import-level1-curve-bundle": "demo",
    "load-level": "demo",
    "stage-capture": "demo",
    "run-scene-sweep": "demo",
    "action-preview": "demo",
    "animation-preview": "demo",
    "retarget-preflight": "demo",
    "retarget-bootstrap": "demo",
    "retarget-author-chains": "demo",
    "demo-gate": "demo",
}


def _workspace_dict(workspace_or_config) -> dict:
    if isinstance(workspace_or_config, dict):
        return workspace_or_config
    return load_workspace_config(workspace_or_config)


def _resolved_host_key(workspace: dict, command: str | None = None, host_key: str | None = None) -> str:
    requested = str(host_key or "").strip()
    if requested:
        return requested
    routes = dict(DEFAULT_HOST_ROUTES)
    routes.update(workspace.get("default_host_routes") or {})
    resolved = str(routes.get(str(command or "")) or "").strip()
    if resolved:
        return resolved
    if workspace.get("hosts", {}).get("kernel"):
        return "kernel"
    return "default"


def resolve_host_paths(workspace_or_config, command: str | None = None, host_key: str | None = None) -> dict:
    workspace = _workspace_dict(workspace_or_config)
    resolved_host_key = _resolved_host_key(workspace, command=command, host_key=host_key)
    host_entry = dict((workspace.get("hosts") or {}).get(resolved_host_key) or {})
    project_root_value = host_entry.get("project_root") or workspace["paths"]["unreal_project_root"]
    project_root = Path(project_root_value).expanduser().resolve()
    return {
        "workspace": workspace,
        "host_key": resolved_host_key,
        "host_entry": host_entry,
        "project_root": project_root,
        "auto_ue_cli_ps1": project_root / "auto_ue_cli.ps1",
        "probe_ps1": project_root / "probe_ue_capabilities.ps1",
        "capability_root": Path(workspace["paths"]["capability_probe_root"]).expanduser().resolve(),
        "auto_ue_cli_output_root": Path(workspace["paths"]["auto_ue_cli_output_root"]).expanduser().resolve()
    }


def _run_powershell(script_path: Path, arguments: list[str]) -> dict:
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        *arguments
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "command": command
    }


def run_host_probe(workspace_or_config, mode: str = "dual", run_id: str | None = None, host_key: str | None = None) -> dict:
    paths = resolve_host_paths(workspace_or_config, command="probe-capabilities", host_key=host_key)
    arguments = ["-WorkspaceConfig", paths["workspace"]["config_path"], "-Mode", mode]
    if paths.get("host_key"):
        arguments += ["-HostKey", paths["host_key"]]
    if run_id:
        arguments += ["-RunId", run_id]
    invocation = _run_powershell(paths["probe_ps1"], arguments)
    capabilities_path = paths["capability_root"] / "latest_capabilities.json"
    probe_index_path = paths["capability_root"] / "latest_probe_index.json"
    probe_report_path = paths["capability_root"] / "latest_probe_report.json"
    if invocation["returncode"] != 0:
        raise RuntimeError(
            f"Host capability probe failed with exit code {invocation['returncode']}: "
            f"{invocation['stderr'] or invocation['stdout']}"
        )
    return {
        "invocation": invocation,
        "host_key": paths["host_key"],
        "capabilities_path": str(capabilities_path),
        "probe_index_path": str(probe_index_path),
        "probe_report_path": str(probe_report_path),
        "capabilities": load_json(capabilities_path) if capabilities_path.exists() else None,
        "probe_index": load_json(probe_index_path) if probe_index_path.exists() else None,
        "probe_report": load_json(probe_report_path) if probe_report_path.exists() else None
    }


def run_host_auto_ue_cli(
    workspace_or_config,
    mode: str,
    command: str,
    params: dict | None = None,
    output_path: str | None = None,
    allow_destructive: bool = False,
    dry_run: bool = False,
    post_exit_finalize_wait_seconds: int | None = None,
    host_key: str | None = None,
) -> dict:
    paths = resolve_host_paths(workspace_or_config, command=command, host_key=host_key)
    arguments = [
        "run",
        "-WorkspaceConfig",
        paths["workspace"]["config_path"],
        "-Mode",
        mode,
        "-Command",
        command
    ]
    if paths.get("host_key"):
        arguments += ["-HostKey", paths["host_key"]]
    if params:
        arguments += ["-ParamsJson", json.dumps(params, ensure_ascii=False, separators=(",", ":"))]
    if output_path:
        arguments += ["-OutputPath", output_path]
    if post_exit_finalize_wait_seconds is not None:
        arguments += ["-PostExitFinalizeWaitSeconds", str(post_exit_finalize_wait_seconds)]
    if allow_destructive:
        arguments.append("-AllowDestructive")
    if dry_run:
        arguments.append("-DryRun")

    invocation = _run_powershell(paths["auto_ue_cli_ps1"], arguments)
    payload = None
    if output_path:
        payload_path = Path(output_path).expanduser().resolve()
        if payload_path.exists():
            payload = load_json(payload_path)
    if invocation["returncode"] != 0:
        if payload:
            result = dict(payload.get("result") or {})
            result.setdefault("warnings", list(payload.get("warnings", [])))
            result.setdefault("errors", list(payload.get("errors", [])))
            result["host_action_result_path"] = str(Path(output_path).expanduser().resolve()) if output_path else None
            result["host_returncode"] = invocation["returncode"]
            raise ActionResultError(
                "; ".join(str(item) for item in payload.get("errors") or [f"host_auto_ue_cli_exit_{invocation['returncode']}"]),
                result=result,
                warnings=list(payload.get("warnings", [])),
                errors=list(payload.get("errors", [])),
            )
        raise RuntimeError(invocation["stderr"] or invocation["stdout"] or "host auto_ue_cli failed")
    return {
        "invocation": invocation,
        "host_key": paths["host_key"],
        "payload": payload,
        "output_path": str(Path(output_path).expanduser().resolve()) if output_path else None
    }
