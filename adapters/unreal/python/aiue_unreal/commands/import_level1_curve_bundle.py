from __future__ import annotations

import json
from pathlib import Path

from aiue_unreal.execution_errors import ActionResultError
from aiue_unreal.host_bridge import resolve_host_paths, run_host_auto_ue_cli


REQUEST_SCHEMA_VERSION = "autohoudini_aiue_level1_consumer_request_v0"
REQUEST_OPERATION = "import_level1_curve_bundle"


def _load_request_json(request_json_path: Path) -> dict:
    try:
        return json.loads(request_json_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise ActionResultError(
            "autohoudini_level1_request_missing",
            result={
                "status": "fail",
                "request_json_path": str(request_json_path),
                "warnings": [],
                "errors": [f"autohoudini_level1_request_missing:{request_json_path}"],
            },
            errors=[f"autohoudini_level1_request_missing:{request_json_path}"],
        ) from None
    except Exception as exc:
        raise ActionResultError(
            "autohoudini_level1_request_invalid_json",
            result={
                "status": "fail",
                "request_json_path": str(request_json_path),
                "warnings": [],
                "errors": [f"autohoudini_level1_request_invalid_json:{exc}"],
            },
            errors=[f"autohoudini_level1_request_invalid_json:{exc}"],
        ) from exc


def _validate_request_payload(request_payload: dict, request_json_path: Path) -> dict:
    errors: list[str] = []
    if str(request_payload.get("schema_version") or "") != REQUEST_SCHEMA_VERSION:
        errors.append(
            f"autohoudini_level1_request_schema_mismatch:{request_payload.get('schema_version') or 'missing'}"
        )
    if str(request_payload.get("operation") or "") != REQUEST_OPERATION:
        errors.append(
            f"autohoudini_level1_request_operation_mismatch:{request_payload.get('operation') or 'missing'}"
        )

    for field_name in (
        "curve_csv_path",
        "ue_manifest_path",
        "target_package_id",
        "curve_asset_root",
    ):
        if not str(request_payload.get(field_name) or "").strip():
            errors.append(f"autohoudini_level1_request_missing_field:{field_name}")

    if errors:
        raise ActionResultError(
            "autohoudini_level1_request_invalid",
            result={
                "status": "fail",
                "request_json_path": str(request_json_path),
                "warnings": [],
                "errors": errors,
            },
            errors=errors,
        )
    return request_payload


def run(context: dict, params: dict) -> dict:
    request_json_value = str(params.get("request_json") or params.get("request_path") or "").strip()
    if not request_json_value:
        raise ActionResultError(
            "autohoudini_level1_request_path_missing",
            result={
                "status": "fail",
                "warnings": [],
                "errors": ["autohoudini_level1_request_path_missing"],
            },
            errors=["autohoudini_level1_request_path_missing"],
        )

    request_json_path = Path(request_json_value).expanduser().resolve()
    request_payload = _validate_request_payload(_load_request_json(request_json_path), request_json_path)

    requested_host_key = str(params.get("host_key") or request_payload.get("host_key") or "").strip() or None
    resolved_host_key = resolve_host_paths(
        context["workspace"],
        command="import-level1-curve-bundle",
        host_key=requested_host_key,
    )["host_key"]
    temp_root = Path(
        str(
            params.get("temp_root")
            or (Path(context["output_path"]).expanduser().resolve().parent / "autohoudini_level1_import_temp")
        )
    ).expanduser().resolve()

    prepared_params = {
        "request_json": str(request_json_path),
        "resolved_host_key": resolved_host_key,
        "temp_root": str(temp_root),
    }

    try:
        invocation = run_host_auto_ue_cli(
            workspace_or_config=context["workspace"],
            mode=context["mode"],
            command="import-level1-curve-bundle",
            params=prepared_params,
            output_path=context["delegate_output_path"],
            allow_destructive=bool(context["action_spec"].get("allow_destructive")),
            dry_run=bool(context["action_spec"].get("dry_run")),
            post_exit_finalize_wait_seconds=params.get("post_exit_finalize_wait_seconds"),
            host_key=resolved_host_key,
        )
    except ActionResultError as exc:
        exc.result["request_json_path"] = str(request_json_path)
        exc.result["host_key"] = resolved_host_key
        exc.result["temp_root"] = str(temp_root)
        raise

    payload = invocation.get("payload") or {}
    result = dict(payload.get("result") or {})
    result.setdefault("warnings", payload.get("warnings", []))
    result.setdefault("errors", payload.get("errors", []))
    result["request_json_path"] = str(request_json_path)
    result["host_key"] = resolved_host_key
    result["temp_root"] = str(temp_root)
    result["host_action_result_path"] = invocation.get("output_path")
    result["host_returncode"] = invocation["invocation"]["returncode"]
    return result
