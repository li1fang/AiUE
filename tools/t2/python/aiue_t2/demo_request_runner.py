from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aiue_core.schema_utils import write_json
from aiue_unreal.host_bridge import run_host_auto_ue_cli

from aiue_t2.state import AppState, load_workbench_state, resolve_manifest_path


REQUEST_KINDS = ("action_preview", "animation_preview")


@dataclass
class DemoRequestSelection:
    app_state: AppState
    request_kind: str
    request_payload: dict[str, Any]
    selected_package_id: str | None
    selected_action_preset_id: str | None
    selected_animation_preset_id: str | None

    def to_dump_dict(self) -> dict[str, Any]:
        return {
            "status": "pass",
            "request_kind": self.request_kind,
            "selected_package_id": self.selected_package_id,
            "selected_action_preset_id": self.selected_action_preset_id,
            "selected_animation_preset_id": self.selected_animation_preset_id,
            "request_payload": self.request_payload,
        }


def _request_kind(request_kind: str | None) -> str:
    resolved = str(request_kind or "action_preview").strip() or "action_preview"
    if resolved not in REQUEST_KINDS:
        raise ValueError(f"Unsupported request kind: {resolved}")
    return resolved


def load_demo_request_selection(
    *,
    repo_root: Path,
    manifest_path: str | Path | None = None,
    latest: bool = False,
    session_manifest_path: str | Path | None = None,
    package_id: str | None = None,
    action_preset_id: str | None = None,
    animation_preset_id: str | None = None,
    request_kind: str | None = None,
) -> DemoRequestSelection:
    resolved_manifest_path = resolve_manifest_path(
        repo_root=repo_root,
        manifest_path=manifest_path,
        latest=latest or not manifest_path,
    )
    app_state = load_workbench_state(
        resolved_manifest_path,
        session_manifest_path=session_manifest_path,
    )
    if app_state.status != "pass":
        error_messages = "; ".join(error.message for error in app_state.errors) or "workbench_state_error"
        raise RuntimeError(error_messages)

    request_payload = app_state.to_dump_payload(
        None if package_id is None and action_preset_id is None and animation_preset_id is None else _view_state_override(
            app_state,
            package_id=package_id,
            action_preset_id=action_preset_id,
            animation_preset_id=animation_preset_id,
        )
    )
    resolved_request_kind = _request_kind(request_kind)
    demo_request = dict(request_payload.get("demo_request") or {})
    requests_by_kind = dict(demo_request.get("requests") or {})
    selected_request_payload = dict(requests_by_kind.get(resolved_request_kind) or {})
    if not selected_request_payload:
        raise RuntimeError(f"demo_request_missing:{resolved_request_kind}")

    return DemoRequestSelection(
        app_state=app_state,
        request_kind=resolved_request_kind,
        request_payload=selected_request_payload,
        selected_package_id=demo_request.get("selected_package_id"),
        selected_action_preset_id=demo_request.get("selected_action_preset_id"),
        selected_animation_preset_id=demo_request.get("selected_animation_preset_id"),
    )


def _view_state_override(
    app_state: AppState,
    *,
    package_id: str | None,
    action_preset_id: str | None,
    animation_preset_id: str | None,
):
    from aiue_t2.state import ViewState

    return ViewState(
        selected_report_gate_id=app_state.default_report_gate_id,
        selected_image_key=app_state.default_image_key,
        selected_package_id=package_id or app_state.default_package_id,
        selected_action_preset_id=action_preset_id or app_state.default_action_preset_id,
        selected_animation_preset_id=animation_preset_id or app_state.default_animation_preset_id,
    )


def default_request_json_path(selection: DemoRequestSelection) -> Path:
    output_root = Path(str((selection.request_payload.get("params") or {}).get("output_root") or "")).expanduser().resolve()
    if not str(output_root):
        raise RuntimeError("demo_request_output_root_missing")
    output_root.mkdir(parents=True, exist_ok=True)
    return output_root / f"{selection.request_kind}_request.json"


def default_result_json_path(selection: DemoRequestSelection, *, dry_run: bool) -> Path:
    output_root = Path(str((selection.request_payload.get("params") or {}).get("output_root") or "")).expanduser().resolve()
    if not str(output_root):
        raise RuntimeError("demo_request_output_root_missing")
    output_root.mkdir(parents=True, exist_ok=True)
    suffix = "dry_run_result" if dry_run else "invoke_result"
    return output_root / f"{selection.request_kind}_{suffix}.json"


def export_demo_request(
    selection: DemoRequestSelection,
    *,
    request_json_path: str | Path | None = None,
) -> Path:
    resolved_path = Path(request_json_path).expanduser().resolve() if request_json_path else default_request_json_path(selection)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        resolved_path,
        {
            "request_kind": selection.request_kind,
            "selected_package_id": selection.selected_package_id,
            "selected_action_preset_id": selection.selected_action_preset_id,
            "selected_animation_preset_id": selection.selected_animation_preset_id,
            "request_payload": selection.request_payload,
        },
    )
    return resolved_path


def invoke_demo_request(
    selection: DemoRequestSelection,
    *,
    workspace_config: str | Path,
    result_json_path: str | Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    resolved_result_path = Path(result_json_path).expanduser().resolve() if result_json_path else default_result_json_path(selection, dry_run=dry_run)
    resolved_result_path.parent.mkdir(parents=True, exist_ok=True)
    request_payload = dict(selection.request_payload)
    params = dict(request_payload.get("params") or {})
    invocation = run_host_auto_ue_cli(
        workspace_or_config=str(Path(workspace_config).expanduser().resolve()),
        mode=str(request_payload.get("mode") or "editor_rendered"),
        command=str(request_payload.get("command") or ""),
        params=params,
        output_path=str(resolved_result_path),
        host_key=str(request_payload.get("host_key") or ""),
        dry_run=dry_run,
    )
    return {
        "status": "pass",
        "request_kind": selection.request_kind,
        "dry_run": bool(dry_run),
        "selected_package_id": selection.selected_package_id,
        "selected_action_preset_id": selection.selected_action_preset_id,
        "selected_animation_preset_id": selection.selected_animation_preset_id,
        "request_payload": request_payload,
        "result_json_path": str(resolved_result_path),
        "host_key": invocation.get("host_key"),
        "payload": invocation.get("payload"),
        "invocation": invocation.get("invocation"),
    }


def selection_to_json(selection: DemoRequestSelection) -> str:
    return json.dumps(selection.to_dump_dict(), ensure_ascii=False, indent=2)
