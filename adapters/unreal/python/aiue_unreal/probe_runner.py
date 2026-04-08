from __future__ import annotations

from aiue_unreal.host_bridge import run_host_probe


def probe_capabilities(workspace_or_config, mode: str = "dual", run_id: str | None = None) -> dict:
    return run_host_probe(workspace_or_config, mode=mode, run_id=run_id)
