from __future__ import annotations

from aiue_unreal.probe_runner import probe_capabilities


def run(context: dict, params: dict) -> dict:
    result = probe_capabilities(
        context["workspace"],
        mode=params.get("mode") or context["mode"],
        run_id=params.get("run_id")
    )
    capabilities = result.get("capabilities") or {}
    entries = capabilities.get("capabilities") or []
    return {
        "capabilities_path": result["capabilities_path"],
        "probe_report_path": result["probe_report_path"],
        "probe_index_path": result["probe_index_path"],
        "capability_count": len(entries),
        "capture_policy": capabilities.get("capture_policy"),
        "warnings": [],
        "errors": []
    }
