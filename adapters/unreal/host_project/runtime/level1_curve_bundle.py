from __future__ import annotations

import csv
import traceback
from pathlib import Path

from .common import *


REQUEST_SCHEMA_VERSION = "autohoudini_aiue_level1_consumer_request_v0"
REQUEST_OPERATION = "import_level1_curve_bundle"
SUPPORTED_IMPORT_MODE = "curve_float_asset_set"


def _resolve_input_path(value: str, base_dir: Path) -> Path:
    candidate = Path(str(value or "")).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_dir / candidate).resolve()


def _load_request_payload(request: dict) -> tuple[Path | None, dict, list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    request_json_path = Path(str(request.get("request_json") or request.get("request_path") or "")).expanduser().resolve()
    if not request_json_path.exists():
        errors.append(f"autohoudini_level1_request_missing:{request_json_path}")
        return None, {}, warnings, errors
    try:
        payload = read_json(request_json_path)
    except Exception as exc:
        errors.append(f"autohoudini_level1_request_invalid_json:{exc}")
        return request_json_path, {}, warnings, errors

    if str(payload.get("schema_version") or "") != REQUEST_SCHEMA_VERSION:
        errors.append(f"autohoudini_level1_request_schema_mismatch:{payload.get('schema_version') or 'missing'}")
    if str(payload.get("operation") or "") != REQUEST_OPERATION:
        errors.append(f"autohoudini_level1_request_operation_mismatch:{payload.get('operation') or 'missing'}")
    for field_name in ("curve_csv_path", "ue_manifest_path", "target_package_id", "curve_asset_root"):
        if not str(payload.get(field_name) or "").strip():
            errors.append(f"autohoudini_level1_request_missing_field:{field_name}")
    return request_json_path, payload, warnings, errors


def _load_curve_bundle(request_payload: dict, request_json_path: Path) -> tuple[dict, Path, Path, list[dict], list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    request_dir = request_json_path.parent
    ue_manifest_path = _resolve_input_path(str(request_payload.get("ue_manifest_path") or ""), request_dir)
    curve_csv_path = _resolve_input_path(str(request_payload.get("curve_csv_path") or ""), request_dir)
    if not ue_manifest_path.exists():
        errors.append(f"ue_manifest_missing:{ue_manifest_path}")
        return {}, ue_manifest_path, curve_csv_path, [], warnings, errors
    if not curve_csv_path.exists():
        errors.append(f"curve_csv_missing:{curve_csv_path}")
        return {}, ue_manifest_path, curve_csv_path, [], warnings, errors

    try:
        ue_manifest = read_json(ue_manifest_path)
    except Exception as exc:
        errors.append(f"ue_manifest_invalid_json:{exc}")
        return {}, ue_manifest_path, curve_csv_path, [], warnings, errors

    channels = [str(item.get("name") or "").strip() for item in list(ue_manifest.get("channels") or []) if str(item.get("name") or "").strip()]
    if not channels:
        errors.append("ue_manifest_channels_missing")
        return ue_manifest, ue_manifest_path, curve_csv_path, [], warnings, errors

    manifest_curve_csv = str(ue_manifest.get("curve_csv") or "").strip()
    if manifest_curve_csv:
        manifest_curve_csv_path = _resolve_input_path(manifest_curve_csv, ue_manifest_path.parent)
        if manifest_curve_csv_path != curve_csv_path:
            warnings.append(f"curve_csv_path_differs_from_manifest:{manifest_curve_csv_path}:{curve_csv_path}")

    rows: list[dict] = []
    try:
        with curve_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = [str(header or "").strip() for header in (reader.fieldnames or [])]
            if "time_s" not in headers:
                errors.append("curve_csv_missing_time_s")
                return ue_manifest, ue_manifest_path, curve_csv_path, [], warnings, errors
            missing_channels = [channel for channel in channels if channel not in headers]
            if missing_channels:
                errors.append(f"curve_csv_missing_channels:{','.join(missing_channels)}")
                return ue_manifest, ue_manifest_path, curve_csv_path, [], warnings, errors

            for row_index, row in enumerate(reader, start=2):
                record = {
                    "row_index": row_index,
                    "time_s": float(str(row.get("time_s") or "").strip()),
                    "values": {},
                }
                for channel in channels:
                    record["values"][channel] = float(str(row.get(channel) or "").strip())
                rows.append(record)
    except Exception as exc:
        errors.append(f"curve_csv_parse_failed:{exc}")
        return ue_manifest, ue_manifest_path, curve_csv_path, [], warnings, errors

    if not rows:
        errors.append("curve_csv_no_rows")
    return ue_manifest, ue_manifest_path, curve_csv_path, rows, warnings, errors


def _resolve_import_mode(request_payload: dict) -> tuple[str, list[str]]:
    warnings: list[str] = []
    requested_mode = str(request_payload.get("unreal_import_mode") or "").strip()
    if requested_mode and requested_mode != SUPPORTED_IMPORT_MODE:
        warnings.append(f"requested_unreal_import_mode_overridden:{requested_mode}:{SUPPORTED_IMPORT_MODE}")
    elif not requested_mode:
        warnings.append(f"requested_unreal_import_mode_missing_defaulted:{SUPPORTED_IMPORT_MODE}")
    return SUPPORTED_IMPORT_MODE, warnings


def _normalize_enum_token(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _resolve_enum_member(enum_type, *candidates: str) -> tuple[object, str]:
    members = {}
    for name in dir(enum_type):
        if name.startswith("_"):
            continue
        members[_normalize_enum_token(name)] = (getattr(enum_type, name), name)
    for candidate in candidates:
        key = _normalize_enum_token(candidate)
        if key in members:
            return members[key]
    raise RuntimeError(
        f"enum_member_not_found:{getattr(enum_type, '__name__', type(enum_type).__name__)}:{','.join(candidates)}"
    )


def _build_csv_curve_factory() -> tuple[object | None, dict, list[str]]:
    warnings: list[str] = []
    if not hasattr(unreal, "CSVImportFactory"):
        return None, {}, ["csv_import_factory_unavailable"]
    if not hasattr(unreal, "CSVImportSettings"):
        return None, {}, ["csv_import_settings_unavailable"]
    if not hasattr(unreal, "CSVImportType"):
        return None, {}, ["csv_import_type_unavailable"]
    if not hasattr(unreal, "RichCurveInterpMode"):
        return None, {}, ["rich_curve_interp_mode_unavailable"]

    factory = unreal.CSVImportFactory()
    settings = unreal.CSVImportSettings()
    import_type, import_type_name = _resolve_enum_member(
        unreal.CSVImportType,
        "ECSV_CurveFloat",
        "ECSV_CURVE_FLOAT",
        "CurveFloat",
        "CURVE_FLOAT",
    )
    interp_mode, interp_mode_name = _resolve_enum_member(
        unreal.RichCurveInterpMode,
        "RCIM_Linear",
        "RCIM_LINEAR",
        "Linear",
    )
    set_if_present(settings, "import_type", import_type)
    set_if_present(settings, "import_curve_interp_mode", interp_mode)
    set_if_present(factory, "automated_import_settings", settings)
    return factory, {
        "import_type_name": import_type_name,
        "interp_mode_name": interp_mode_name,
    }, warnings


def _write_channel_import_csv(temp_dir: Path, channel_name: str, channel_index: int, rows: list[dict]) -> Path:
    temp_dir.mkdir(parents=True, exist_ok=True)
    csv_path = temp_dir / f"{channel_index:02d}_{sanitize_segment(channel_name)}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        for row in rows:
            writer.writerow([f"{float(row['time_s']):.9f}", f"{float(row['values'][channel_name]):.9f}"])
    return csv_path


def _first_curve_object_path(imported_object_paths: list[str], fallback_asset_path: str) -> str:
    for object_path in imported_object_paths:
        loaded_asset = unreal.EditorAssetLibrary.load_asset(object_path)
        if loaded_asset and loaded_asset.get_class().get_name() == "CurveFloat":
            return str(object_path)
    fallback_object_path = object_path_from_asset_path(fallback_asset_path)
    if unreal.EditorAssetLibrary.does_asset_exist(fallback_object_path):
        return fallback_object_path
    return ""


def _import_curve_channel(
    package_path: str,
    channel_name: str,
    channel_index: int,
    rows: list[dict],
    temp_csv_dir: Path,
) -> tuple[dict | None, list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    asset_name = f"CF_{channel_index:02d}_{sanitize_segment(channel_name)}"
    asset_path = f"{package_path}/{asset_name}"
    curve_csv_path = _write_channel_import_csv(temp_csv_dir, channel_name, channel_index, rows)
    factory, factory_info, factory_errors = _build_csv_curve_factory()
    if factory_errors:
        return None, warnings, factory_errors

    task = unreal.AssetImportTask()
    set_if_present(task, "filename", str(curve_csv_path))
    set_if_present(task, "destination_path", package_path)
    set_if_present(task, "destination_name", asset_name)
    set_if_present(task, "replace_existing", True)
    set_if_present(task, "replace_existing_settings", True)
    set_if_present(task, "automated", True)
    set_if_present(task, "save", True)
    set_if_present(task, "factory", factory)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    imported_object_paths = list(task.get_editor_property("imported_object_paths") or [])
    loaded_object_path = _first_curve_object_path(imported_object_paths, asset_path)
    if not loaded_object_path:
        errors.append(f"curve_import_missing_output:{channel_name}:{asset_path}")
        return None, warnings, errors

    curve_asset = unreal.EditorAssetLibrary.load_asset(loaded_object_path)
    if not curve_asset:
        errors.append(f"curve_import_load_failed:{loaded_object_path}")
        return None, warnings, errors
    if curve_asset.get_class().get_name() != "CurveFloat":
        errors.append(f"curve_import_wrong_class:{loaded_object_path}:{curve_asset.get_class().get_name()}")
        return None, warnings, errors

    try:
        unreal.EditorAssetLibrary.save_loaded_asset(curve_asset, False)
    except Exception as exc:
        warnings.append(f"curve_asset_save_failed:{asset_path}:{exc}")

    sample_eval_last = None
    if hasattr(curve_asset, "get_float_value"):
        try:
            sample_eval_last = float(curve_asset.get_float_value(float(rows[-1]["time_s"])))
        except Exception:
            sample_eval_last = None

    return {
        "channel_name": channel_name,
        "asset_name": asset_name,
        "asset_path": asset_path,
        "object_path": object_path_from_asset_path(asset_path),
        "loaded_object_path": loaded_object_path,
        "loaded_asset_path": asset_path_from_object_path(loaded_object_path),
        "key_count": len(rows),
        "temp_curve_csv_path": str(curve_csv_path.resolve()),
        "factory_info": factory_info,
        "imported_object_paths": imported_object_paths,
        "sample_eval_last": sample_eval_last,
    }, warnings, errors


def import_level1_curve_bundle(request: dict) -> dict:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        request_json_path, request_payload, request_warnings, request_errors = _load_request_payload(request)
        warnings.extend(request_warnings)
        errors.extend(request_errors)
        if request_json_path is None or errors:
            return {
                "status": "fail",
                "generated_at_utc": now_utc(),
                "resolved_import_mode": SUPPORTED_IMPORT_MODE,
                "request_snapshot": {},
                "bundle_summary": {},
                "imported_curve_assets": [],
                "host_key": str(request.get("resolved_host_key") or ""),
                "warnings": warnings,
                "errors": errors,
            }

        ue_manifest, ue_manifest_path, curve_csv_path, rows, bundle_warnings, bundle_errors = _load_curve_bundle(
            request_payload,
            request_json_path,
        )
        warnings.extend(bundle_warnings)
        errors.extend(bundle_errors)
        resolved_import_mode, mode_warnings = _resolve_import_mode(request_payload)
        warnings.extend(mode_warnings)

        request_snapshot = {
            "operation": str(request_payload.get("operation") or ""),
            "target_package_id": str(request_payload.get("target_package_id") or ""),
            "target_curve_asset_name": str(request_payload.get("target_curve_asset_name") or ""),
            "curve_asset_root": str(request_payload.get("curve_asset_root") or ""),
            "requested_unreal_import_mode": str(request_payload.get("unreal_import_mode") or ""),
            "target_bone": str(request_payload.get("target_bone") or ""),
            "target_host_blueprint_asset_path": str(request_payload.get("target_host_blueprint_asset_path") or ""),
            "target_skeleton_asset_path": str(request_payload.get("target_skeleton_asset_path") or ""),
            "preview_level_path": str(request_payload.get("preview_level_path") or ""),
        }
        if errors:
            return {
                "status": "fail",
                "generated_at_utc": now_utc(),
                "request_json_path": str(request_json_path),
                "ue_manifest_path": str(ue_manifest_path),
                "curve_csv_path": str(curve_csv_path),
                "resolved_import_mode": resolved_import_mode,
                "request_snapshot": request_snapshot,
                "bundle_summary": {},
                "imported_curve_assets": [],
                "host_key": str(request.get("resolved_host_key") or ""),
                "warnings": warnings,
                "errors": errors,
            }

        package_id = sanitize_segment(str(request_payload.get("target_package_id") or "package"))
        curve_asset_root = str(request_payload.get("curve_asset_root") or "/Game/AutoHoudini/Curves").rstrip("/")
        package_path = f"{curve_asset_root}/{package_id}"
        ensure_directory(curve_asset_root)
        ensure_directory(package_path)
        temp_root = Path(str(request.get("temp_root") or (request_json_path.parent / "_aiue_level1_curve_import"))).expanduser().resolve()
        temp_csv_dir = temp_root / package_id

        channels = [str(item.get("name") or "").strip() for item in list(ue_manifest.get("channels") or []) if str(item.get("name") or "").strip()]
        imported_curve_assets: list[dict] = []
        for channel_index, channel_name in enumerate(channels, start=1):
            curve_result, curve_warnings, curve_errors = _import_curve_channel(
                package_path,
                channel_name,
                channel_index,
                rows,
                temp_csv_dir,
            )
            warnings.extend(curve_warnings)
            errors.extend(curve_errors)
            if curve_result:
                imported_curve_assets.append(curve_result)

        try:
            save_directory(package_path)
        except Exception as exc:
            warnings.append(f"save_directory_failed:{package_path}:{exc}")

        return {
            "status": "pass" if not errors else "fail",
            "generated_at_utc": now_utc(),
            "request_json_path": str(request_json_path),
            "ue_manifest_path": str(ue_manifest_path),
            "curve_csv_path": str(curve_csv_path),
            "resolved_import_mode": resolved_import_mode,
            "request_snapshot": request_snapshot,
            "bundle_summary": {
                "package_path": package_path,
                "row_count": len(rows),
                "channel_count": len(channels),
                "sample_rate_hz": ue_manifest.get("sample_rate_hz"),
                "target_bone": ue_manifest.get("target_bone") or request_payload.get("target_bone"),
                "time_range_s": {
                    "start": float(rows[0]["time_s"]) if rows else 0.0,
                    "end": float(rows[-1]["time_s"]) if rows else 0.0,
                },
            },
            "imported_curve_assets": imported_curve_assets,
            "host_key": str(request.get("resolved_host_key") or ""),
            "warnings": warnings,
            "errors": errors,
        }
    except Exception as exc:
        return {
            "status": "fail",
            "generated_at_utc": now_utc(),
            "resolved_import_mode": SUPPORTED_IMPORT_MODE,
            "request_snapshot": {},
            "bundle_summary": {},
            "imported_curve_assets": [],
            "host_key": str(request.get("resolved_host_key") or ""),
            "warnings": warnings,
            "errors": [f"autohoudini_level1_import_failed:{exc}", traceback.format_exc()],
        }
