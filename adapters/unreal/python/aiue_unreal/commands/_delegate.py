from __future__ import annotations

from aiue_unreal.host_bridge import run_host_auto_ue_cli


def delegate_to_host_command(context: dict, command_id: str, params: dict) -> dict:
    invocation = run_host_auto_ue_cli(
        workspace_or_config=context["workspace"],
        mode=context["mode"],
        command=command_id,
        params=params,
        output_path=context["delegate_output_path"],
        allow_destructive=bool(context["action_spec"].get("allow_destructive")),
        dry_run=bool(context["action_spec"].get("dry_run")),
        post_exit_finalize_wait_seconds=params.get("post_exit_finalize_wait_seconds")
    )
    payload = invocation.get("payload") or {}
    result = dict(payload.get("result") or {})
    result.setdefault("warnings", payload.get("warnings", []))
    result.setdefault("errors", payload.get("errors", []))
    result["host_action_result_path"] = invocation.get("output_path")
    result["host_returncode"] = invocation["invocation"]["returncode"]
    return result
