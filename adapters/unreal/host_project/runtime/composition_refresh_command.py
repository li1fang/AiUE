from __future__ import annotations

from .common import *
from .composition_registry_command import build_equipment_registry


def refresh_assets(request: dict) -> dict:
    summary_path = Path(request["summary"]).expanduser().resolve()
    registry_output_path = Path(request["registry_output"]).expanduser().resolve() if request.get("registry_output") else None
    assets_output_path = Path(request["assets_output"]).expanduser().resolve() if request.get("assets_output") else None

    if not summary_path.exists():
        return {
            "status": "fail",
            "summary_path": str(summary_path),
            "warnings": [],
            "errors": [f"summary_missing:{summary_path}"],
        }

    summary_payload = read_json(summary_path)
    registry_path = Path(request.get("registry_json") or summary_path.with_name("ue_equipment_registry.json")).expanduser().resolve()
    if not registry_path.exists():
        return {
            "status": "fail",
            "summary_path": str(summary_path),
            "registry_json_path": str(registry_path),
            "warnings": [],
            "errors": [f"registry_json_missing:{registry_path}"],
        }

    registry_payload = read_json(registry_path)
    if registry_output_path:
        write_json(registry_output_path, registry_payload)

    registry_request = dict(request)
    registry_request["registry_json"] = str(registry_path)
    if assets_output_path:
        registry_request["report_path"] = str(assets_output_path)

    try:
        registry_result = build_equipment_registry(registry_request)
    except Exception as exc:
        return {
            "status": "fail",
            "generated_at_utc": now_utc(),
            "summary_path": str(summary_path),
            "registry_json_path": str(registry_path),
            "registry_output_path": str(registry_output_path) if registry_output_path else None,
            "assets_output_path": str(assets_output_path) if assets_output_path else None,
            "source_suite_name": summary_payload.get("suite_name") or registry_payload.get("suite_name"),
            "source_summary_counts": dict(summary_payload.get("counts") or {}),
            "source_registry_counts": dict(registry_payload.get("counts") or {}),
            "warnings": [],
            "errors": [f"build_equipment_registry_failed:{exc}"],
        }

    return {
        **registry_result,
        "status": "pass" if not registry_result.get("errors") else "fail",
        "summary_path": str(summary_path),
        "registry_json_path": str(registry_path),
        "registry_output_path": str(registry_output_path) if registry_output_path else None,
        "assets_output_path": str(assets_output_path) if assets_output_path else registry_result.get("report_path"),
        "source_suite_name": summary_payload.get("suite_name") or registry_payload.get("suite_name"),
        "source_summary_counts": dict(summary_payload.get("counts") or {}),
        "source_registry_counts": dict(registry_payload.get("counts") or {}),
    }


__all__ = ["refresh_assets"]
