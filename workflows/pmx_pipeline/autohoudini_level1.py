from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from toy_yard_view import resolve_toy_yard_motion_view_root


REQUEST_SCHEMA_VERSION = "autohoudini_aiue_level1_consumer_request_v0"
RESULT_SCHEMA_VERSION = "autohoudini_aiue_level1_consumer_result_v0"
REQUEST_OPERATION = "import_level1_curve_bundle"
SUPPORTED_IMPORT_MODE = "curve_float_asset_set"
DEFAULT_REQUEST_RELATIVE_PATH = ("workspace_views", "aiue_level1_consumer_request.json")
PREVIEW_HINT_KEYS = (
    "preview_level_path",
    "target_host_blueprint_asset_path",
    "target_skeleton_asset_path",
    "preview_fixture_id",
    "target_host_fixture_id",
    "target_skeleton_profile_id",
)


def resolve_request_json_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"AutoHoudini Level1 request path does not exist: {candidate}")
    motion_view_root = resolve_toy_yard_motion_view_root(workspace)
    if motion_view_root is None:
        raise FileNotFoundError("No toy-yard motion view root could be resolved for AutoHoudini Level1 request discovery.")
    candidate = motion_view_root.joinpath(*DEFAULT_REQUEST_RELATIVE_PATH)
    if candidate.exists():
        return candidate.resolve()
    raise FileNotFoundError(f"AutoHoudini Level1 request JSON is missing: {candidate}")


def load_level1_request(request_json_path: Path) -> dict[str, Any]:
    payload = json.loads(request_json_path.read_text(encoding="utf-8-sig"))
    if str(payload.get("schema_version") or "") != REQUEST_SCHEMA_VERSION:
        raise ValueError(f"autohoudini_level1_request_schema_mismatch:{payload.get('schema_version') or 'missing'}")
    if str(payload.get("operation") or "") != REQUEST_OPERATION:
        raise ValueError(f"autohoudini_level1_request_operation_mismatch:{payload.get('operation') or 'missing'}")

    for field_name in (
        "toy_yard_motion_view_root",
        "package_manifest_path",
        "summary_path",
        "registry_path",
        "packet_check_path",
        "producer_signal_path",
        "curve_csv_path",
        "ue_manifest_path",
        "target_package_id",
        "curve_asset_root",
    ):
        if not str(payload.get(field_name) or "").strip():
            raise ValueError(f"autohoudini_level1_request_missing_field:{field_name}")
    if not isinstance(payload.get("runtime_ready_only"), bool):
        raise ValueError("autohoudini_level1_request_runtime_ready_only_invalid")
    consumer_context = payload.get("consumer_context")
    if not isinstance(consumer_context, dict):
        raise ValueError("autohoudini_level1_request_consumer_context_missing")
    for field_name in ("counterparty_system", "source_lane", "transport", "current_aiue_support"):
        if not str(consumer_context.get(field_name) or "").strip():
            raise ValueError(f"autohoudini_level1_request_consumer_context_missing_field:{field_name}")
    preview_hints = payload.get("preview_hints")
    if preview_hints is not None:
        if not isinstance(preview_hints, dict):
            raise ValueError("autohoudini_level1_request_preview_hints_invalid")
        for field_name, value in preview_hints.items():
            if field_name not in PREVIEW_HINT_KEYS:
                raise ValueError(f"autohoudini_level1_request_preview_hints_unknown_field:{field_name}")
            if not str(value or "").strip():
                raise ValueError(f"autohoudini_level1_request_preview_hints_empty_field:{field_name}")
    return payload


def _dedupe_strings(*collections: list[str]) -> list[str]:
    merged: list[str] = []
    for collection in collections:
        for item in list(collection or []):
            text = str(item or "")
            if text and text not in merged:
                merged.append(text)
    return merged


def build_import_summary(import_action_payload: dict[str, Any]) -> dict[str, Any]:
    import_result = dict(import_action_payload.get("result") or {})
    bundle_summary = dict(import_result.get("bundle_summary") or {})
    warnings = _dedupe_strings(import_action_payload.get("warnings") or [], import_result.get("warnings") or [])
    errors = _dedupe_strings(import_action_payload.get("errors") or [], import_result.get("errors") or [])
    status = "pass" if str(import_action_payload.get("status") or "") == "pass" and str(import_result.get("status") or "") == "pass" else "fail"
    return {
        "requested": True,
        "status": status,
        "generated_at_utc": str(import_result.get("generated_at_utc") or import_action_payload.get("generated_at_utc") or ""),
        "resolved_import_mode": str(import_result.get("resolved_import_mode") or ""),
        "row_count": int(bundle_summary.get("row_count") or 0),
        "channel_count": int(bundle_summary.get("channel_count") or 0),
        "target_bone": str(bundle_summary.get("target_bone") or ""),
        "imported_asset_count": len(list(import_result.get("imported_curve_assets") or [])),
        "warnings": warnings,
        "errors": errors,
    }


def preview_hints_from_request(request_payload: dict[str, Any]) -> dict[str, str] | None:
    preview_hints: dict[str, str] = {}
    raw_preview_hints = request_payload.get("preview_hints")
    if isinstance(raw_preview_hints, dict):
        for key in PREVIEW_HINT_KEYS:
            value = str(raw_preview_hints.get(key) or "").strip()
            if value:
                preview_hints[key] = value
    for key in (
        "preview_level_path",
        "target_host_blueprint_asset_path",
        "target_skeleton_asset_path",
    ):
        if key in preview_hints:
            continue
        value = str(request_payload.get(key) or "").strip()
        if value:
            preview_hints[key] = value
    return preview_hints or None


def build_not_requested_preview_summary(request_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "requested": False,
        "status": "not_requested",
        "generated_at_utc": None,
        "resolved_import_mode": None,
        "level_loaded": None,
        "host_binding_mode": None,
        "target_bone": None,
        "target_bone_exists": None,
        "curve_pass_count": None,
        "curve_fail_count": None,
        "max_abs_error": None,
        "tolerance": None,
        "warnings": [],
        "errors": [],
    }


def build_external_result(
    *,
    import_action_payload: dict[str, Any],
    import_action_result_path: str,
    request_payload: dict[str, Any],
    request_json_path: Path,
    workspace_config_path: Path,
    combined_result_path: Path,
    host_key: str,
) -> dict[str, Any]:
    import_summary = build_import_summary(import_action_payload)
    preview_summary = build_not_requested_preview_summary(request_payload)
    warnings = list(import_summary.get("warnings") or [])
    errors = list(import_summary.get("errors") or [])
    status = "pass" if import_summary["status"] == "pass" else "fail"
    preview_hints = preview_hints_from_request(request_payload)
    request_snapshot = {
        "target_package_id": str(request_payload.get("target_package_id") or ""),
        "target_curve_asset_name": str(request_payload.get("target_curve_asset_name") or ""),
        "target_bone": str(request_payload.get("target_bone") or ""),
        "unreal_import_mode": str(
            import_summary.get("resolved_import_mode") or request_payload.get("unreal_import_mode") or SUPPORTED_IMPORT_MODE
        ),
    }
    if preview_hints:
        request_snapshot["preview_hints"] = preview_hints
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "operation": REQUEST_OPERATION,
        "status": status,
        "generated_at_utc": str(import_summary.get("generated_at_utc") or import_action_payload.get("generated_at_utc") or ""),
        "request_path": str(request_json_path.resolve()),
        "workspace_config_path": str(workspace_config_path.resolve()),
        "host_key": str(host_key or ""),
        "execution_shell": {
            "producer_system": "autohoudini",
            "consumer_system": "aiue",
            "mode": "import_only",
            "dry_run": False,
            "current_aiue_support": str(
                ((request_payload.get("consumer_context") or {}).get("current_aiue_support")) or "implemented"
            ),
            "transport_tool": "toy_yard_publish_profile",
        },
        "request_snapshot": request_snapshot,
        "result_paths": {
            "combined_result_json": str(combined_result_path.resolve()),
            "import_result_json": str(Path(import_action_result_path).expanduser().resolve()) if import_action_result_path else "",
            "preview_result_json": "",
        },
        "import_summary": import_summary,
        "preview_summary": preview_summary,
        "warnings": warnings,
        "errors": errors,
        "notes": [
            "Mirrored by AiUE for the tightened AH1 AutoHoudini seam.",
            "preview_hints remain hint-only and do not gate import-only success.",
        ],
    }
