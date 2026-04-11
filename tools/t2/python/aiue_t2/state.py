from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aiue_t2.state_models import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    AppState,
    DemoPackageRecord,
    DemoPresetRecord,
    DemoRequestRecord,
    DemoSessionRecord,
    ErrorRecord,
    GovernanceBalanceRecord,
    PreviewImageRecord,
    ReportRecord,
    ViewState,
    build_default_view_state,
    report_payload_to_text,
    view_state_to_dict,
)


DEFAULT_E2_SESSION_NAME = "playable_demo_e2_session.json"
DEFAULT_ACTION_REQUEST_PROFILE = {
    "capture_width": 1280,
    "capture_height": 720,
    "capture_delay_seconds": 0.2,
    "subject_min_screen_coverage": 0.015,
    "weapon_min_screen_coverage": 0.001,
    "scene_capture_source": "SCS_FINAL_COLOR_HDR",
    "scene_capture_warmup_count": 4,
    "scene_capture_warmup_delay_seconds": 0.08,
    "min_distance_delta": 40.0,
    "min_yaw_delta": 10.0,
    "tracked_slots": ["clothing", "fx"],
}
DEFAULT_ANIMATION_REQUEST_PROFILE = {
    "capture_width": 1280,
    "capture_height": 720,
    "capture_delay_seconds": 0.2,
    "subject_min_screen_coverage": 0.015,
    "weapon_min_screen_coverage": 0.001,
    "animation_sample_time_seconds": 0.25,
    "animation_settle_seconds": 0.1,
    "retarget_if_needed": False,
    "pose_probe_bone_names": [],
}


def resolve_manifest_path(*, repo_root: Path, manifest_path: str | Path | None = None, latest: bool = False) -> Path:
    if manifest_path:
        return Path(manifest_path).expanduser().resolve()
    if latest or not manifest_path:
        return (repo_root / "Saved" / "tooling" / "t1" / "latest" / "manifest.json").resolve()
    raise ValueError("Unable to resolve a manifest path.")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _error_app_state(*, manifest_path: Path, code: str, message: str) -> AppState:
    error = ErrorRecord(code=code, message=message, path=str(manifest_path))
    return AppState(
        status="error",
        manifest_path=str(manifest_path),
        pack_root=str(manifest_path.parent),
        generated_at_utc="",
        summary_counts={
            "reports": 0,
            "active_line_reports": 0,
            "platform_line_reports": 0,
            "governance_line_reports": 0,
            "historical_other_reports": 0,
            "passing_reports": 0,
        },
        report_categories={key: [] for key in CATEGORY_ORDER},
        reports_by_gate_id={},
        preview_images=[],
        r3_metrics=[],
        quality_summaries={"q5c_lite": {"status": "missing", "packages": [], "diagnostic_class_counts": {}}},
        slot_debugger={"package_count": 0, "packages": []},
        governance_balance=GovernanceBalanceRecord(status="missing"),
        demo_session=DemoSessionRecord(
            status="missing",
            session_manifest_path="",
            session_id="",
            session_type="",
            host_key="",
            mode="",
            level_path="",
            default_package_id=None,
        ),
        demo_request=DemoRequestRecord(
            status="missing",
            selected_package_id=None,
            selected_action_preset_id=None,
            selected_animation_preset_id=None,
        ),
        errors=[error],
        default_report_gate_id=None,
        default_image_key=None,
        default_package_id=None,
        default_action_preset_id=None,
        default_animation_preset_id=None,
    )


def _artifact_path(pack_root: Path, relative_path: str) -> Path:
    return (pack_root / Path(relative_path)).resolve()


def _coerce_summary_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts = dict(payload.get("counts") or {})
    return {
        "reports": int(counts.get("reports") or 0),
        "active_line_reports": int(counts.get("active_line_reports") or 0),
        "platform_line_reports": int(counts.get("platform_line_reports") or 0),
        "governance_line_reports": int(counts.get("governance_line_reports") or 0),
        "historical_other_reports": int(counts.get("historical_other_reports") or 0),
        "passing_reports": int(counts.get("passing_reports") or 0),
    }


def _load_report_categories(
    *,
    manifest: dict[str, Any],
    pack_root: Path,
    errors: list[ErrorRecord],
) -> tuple[dict[str, list[ReportRecord]], dict[str, ReportRecord]]:
    report_artifacts = list((manifest.get("artifacts") or {}).get("reports") or [])
    artifact_paths_by_gate_id = {
        str(item.get("gate_id") or ""): _artifact_path(pack_root, str(item.get("relative_path") or ""))
        for item in report_artifacts
        if str(item.get("gate_id") or "") and str(item.get("relative_path") or "")
    }
    categories_payload = dict((manifest.get("report_index") or {}).get("categories") or {})
    report_categories: dict[str, list[ReportRecord]] = {key: [] for key in CATEGORY_ORDER}
    reports_by_gate_id: dict[str, ReportRecord] = {}

    for category in CATEGORY_ORDER:
        for entry in list(categories_payload.get(category) or []):
            gate_id = str(entry.get("gate_id") or "")
            artifact_path = artifact_paths_by_gate_id.get(gate_id)
            report_payload: dict[str, Any] = {}
            if artifact_path is None or not artifact_path.exists():
                missing_path = artifact_path or Path(str(entry.get("report_path") or ""))
                errors.append(
                    ErrorRecord(
                        code="artifact_missing",
                        message=f"Missing report artifact for gate '{gate_id or entry.get('name') or 'unknown'}'.",
                        path=str(missing_path),
                    )
                )
            else:
                try:
                    report_payload = _load_json(artifact_path)
                except json.JSONDecodeError as exc:
                    errors.append(
                        ErrorRecord(
                            code="artifact_missing",
                            message=f"Unreadable report artifact JSON for gate '{gate_id or entry.get('name') or 'unknown'}': {exc}",
                            path=str(artifact_path),
                        )
                    )
            record = ReportRecord(
                gate_id=gate_id,
                name=str(entry.get("name") or gate_id or "report"),
                category=category,
                status=str(entry.get("status") or report_payload.get("status") or "unknown"),
                generated_at_utc=str(entry.get("generated_at_utc") or report_payload.get("generated_at_utc") or ""),
                report_artifact_path=str(artifact_path or ""),
                report_source_path=str(entry.get("report_path") or ""),
                report_payload=report_payload,
            )
            report_categories[category].append(record)
            if gate_id:
                reports_by_gate_id[gate_id] = record

    return report_categories, reports_by_gate_id


def _load_preview_images(
    *,
    manifest: dict[str, Any],
    pack_root: Path,
    errors: list[ErrorRecord],
) -> list[PreviewImageRecord]:
    preview_images = []
    for entry in list((manifest.get("artifacts") or {}).get("preview_images") or []):
        image_path = _artifact_path(pack_root, str(entry.get("relative_path") or ""))
        if not image_path.exists():
            errors.append(
                ErrorRecord(
                    code="artifact_missing",
                    message=f"Missing preview image '{entry.get('title') or entry.get('key') or 'image'}'.",
                    path=str(image_path),
                )
            )
        preview_images.append(
            PreviewImageRecord(
                key=str(entry.get("key") or ""),
                title=str(entry.get("title") or entry.get("key") or "image"),
                section=str(entry.get("section") or ""),
                image_path=str(image_path),
                source_path=str(entry.get("source_path") or ""),
            )
        )
    return preview_images


def _extract_r3_metrics(reports_by_gate_id: dict[str, ReportRecord]) -> list[dict[str, Any]]:
    record = reports_by_gate_id.get("live_fx_visual_quality_r3")
    if not record or not record.report_payload:
        return []
    metrics_rows: list[dict[str, Any]] = []
    for package in list(record.report_payload.get("per_package_results") or []):
        package_id = str(package.get("package_id") or "")
        for shot in list(package.get("shot_results") or []):
            crop_metrics = dict(shot.get("crop_metrics") or {})
            full_metrics = dict(shot.get("full_frame_metrics") or {})
            metrics_rows.append(
                {
                    "package_id": package_id,
                    "shot_id": str(shot.get("shot_id") or ""),
                    "status": str(shot.get("status") or ""),
                    "crop_histogram_l1": float(crop_metrics.get("histogram_l1") or 0.0),
                    "crop_mean_abs_pixel_delta": float(crop_metrics.get("mean_abs_pixel_delta") or 0.0),
                    "full_histogram_l1": float(full_metrics.get("histogram_l1") or 0.0),
                    "full_mean_abs_pixel_delta": float(full_metrics.get("mean_abs_pixel_delta") or 0.0),
                }
            )
    return metrics_rows


def _load_quality_summaries(
    *,
    manifest: dict[str, Any],
    pack_root: Path,
) -> dict[str, Any]:
    payload = dict(manifest.get("quality_summaries") or {})
    q5c_summary = dict(payload.get("q5c_lite") or {})
    if not q5c_summary:
        return {"q5c_lite": {"status": "missing", "packages": [], "diagnostic_class_counts": {}}}

    normalized_packages = []
    for package in list(q5c_summary.get("packages") or []):
        normalized_package = dict(package)
        artifact_rel = str(package.get("artifact_image_relative_path") or "")
        normalized_package["artifact_image_path"] = str(_artifact_path(pack_root, artifact_rel)) if artifact_rel else ""
        normalized_packages.append(normalized_package)
    return {
        "q5c_lite": {
            **q5c_summary,
            "packages": normalized_packages,
        }
    }


def _extract_governance_balance(reports_by_gate_id: dict[str, ReportRecord]) -> GovernanceBalanceRecord:
    record = reports_by_gate_id.get("dynamic_balance_governance_progress")
    if not record or not record.report_payload:
        return GovernanceBalanceRecord(status="missing")
    report_payload = dict(record.report_payload or {})
    pressure_summary = dict(report_payload.get("pressure_summary") or {})
    recommendation = dict(report_payload.get("recommendation") or {})
    discussion_signal = dict(report_payload.get("discussion_signal") or {})
    repo_state = dict(report_payload.get("repo_state") or {})
    hotspots = [str(item.get("relative_path") or "") for item in list(repo_state.get("hotspots") or []) if str(item.get("relative_path") or "")]
    return GovernanceBalanceRecord(
        status=str(report_payload.get("status") or "unknown"),
        recommended_next_round_kind=str(recommendation.get("next_round_kind") or "") or None,
        discussion_reason=str(discussion_signal.get("reason") or "") or None,
        stability_pressure=str((pressure_summary.get("stability_pressure") or {}).get("level") or "unknown"),
        governance_pressure=str((pressure_summary.get("governance_pressure") or {}).get("level") or "unknown"),
        progress_pressure=str((pressure_summary.get("progress_pressure") or {}).get("level") or "unknown"),
        hotspot_paths=hotspots,
        report_gate_id=record.gate_id,
        report_source_path=record.report_source_path,
    )


def _default_report_gate_id(report_categories: dict[str, list[ReportRecord]]) -> str | None:
    for category in CATEGORY_ORDER:
        records = list(report_categories.get(category) or [])
        if records:
            return records[0].gate_id or records[0].name
    return None


def _discover_latest_session_manifest_path(manifest_path: Path) -> Path | None:
    for ancestor in manifest_path.parents:
        candidate = (ancestor / "Saved" / "demo" / "e2" / "latest" / DEFAULT_E2_SESSION_NAME).resolve()
        if candidate.exists():
            return candidate
    return None


def resolve_session_manifest_path(
    *,
    manifest_path: Path,
    session_manifest_path: str | Path | None = None,
) -> tuple[Path | None, bool]:
    if session_manifest_path:
        return Path(session_manifest_path).expanduser().resolve(), True
    return _discover_latest_session_manifest_path(manifest_path), False


def _demo_preset_from_payload(payload: dict[str, Any], *, preset_kind: str) -> DemoPresetRecord:
    return DemoPresetRecord(
        preset_id=str(payload.get("preset_id") or ""),
        preset_kind=preset_kind,
        family=str(payload.get("family") or ""),
        source_gate_id=str(payload.get("source_gate_id") or ""),
        status=str(payload.get("status") or ""),
        requested_asset_path=str(payload.get("requested_animation_asset_path") or payload.get("requested_asset_path") or ""),
        resolved_asset_path=str(payload.get("resolved_animation_asset_path") or payload.get("resolved_asset_path") or payload.get("retargeted_animation_asset_path") or ""),
        payload=dict(payload),
    )


def _load_demo_session(
    *,
    manifest_path: Path,
    session_manifest_path: str | Path | None,
    errors: list[ErrorRecord],
) -> DemoSessionRecord:
    resolved_session_path, explicit_session = resolve_session_manifest_path(
        manifest_path=manifest_path,
        session_manifest_path=session_manifest_path,
    )
    if resolved_session_path is None:
        return DemoSessionRecord(
            status="missing",
            session_manifest_path="",
            session_id="",
            session_type="",
            host_key="",
            mode="",
            level_path="",
            default_package_id=None,
        )
    if not resolved_session_path.exists():
        if explicit_session:
            errors.append(
                ErrorRecord(
                    code="manifest_missing",
                    message="The requested E2 session manifest does not exist.",
                    path=str(resolved_session_path),
                )
            )
        return DemoSessionRecord(
            status="missing" if not explicit_session else "error",
            session_manifest_path=str(resolved_session_path),
            session_id="",
            session_type="",
            host_key="",
            mode="",
            level_path="",
            default_package_id=None,
        )
    try:
        payload = _load_json(resolved_session_path)
    except json.JSONDecodeError as exc:
        errors.append(
            ErrorRecord(
                code="manifest_invalid_json",
                message=f"Failed to parse E2 session manifest JSON: {exc}",
                path=str(resolved_session_path),
            )
        )
        return DemoSessionRecord(
            status="error",
            session_manifest_path=str(resolved_session_path),
            session_id="",
            session_type="",
            host_key="",
            mode="",
            level_path="",
            default_package_id=None,
        )

    packages: list[DemoPackageRecord] = []
    for package_payload in list(payload.get("packages") or []):
        slot_names = [str(item.get("slot_name") or "") for item in list(package_payload.get("slot_bindings") or []) if str(item.get("slot_name") or "")]
        evidence = dict(package_payload.get("evidence") or {})
        packages.append(
            DemoPackageRecord(
                package_id=str(package_payload.get("package_id") or ""),
                sample_id=str(package_payload.get("sample_id") or ""),
                host_blueprint_asset=str(package_payload.get("host_blueprint_asset") or ""),
                hero_shot_id=str(package_payload.get("hero_shot_id") or ""),
                slot_names=slot_names,
                hero_before_image_path=str(evidence.get("hero_before_image_path") or ""),
                hero_after_image_path=str(evidence.get("hero_after_image_path") or ""),
                action_presets=[_demo_preset_from_payload(dict(item), preset_kind="action") for item in list(package_payload.get("action_presets") or [])],
                animation_presets=[_demo_preset_from_payload(dict(item), preset_kind="animation") for item in list(package_payload.get("animation_presets") or [])],
                payload=dict(package_payload),
            )
        )

    default_package_id = str(payload.get("default_package_id") or "")
    if not default_package_id and packages:
        default_package_id = packages[0].package_id
    return DemoSessionRecord(
        status="pass",
        session_manifest_path=str(resolved_session_path),
        session_id=str(payload.get("session_id") or ""),
        session_type=str(payload.get("session_type") or ""),
        host_key=str(payload.get("host_key") or ""),
        mode=str(payload.get("mode") or ""),
        level_path=str(payload.get("level_path") or ""),
        default_package_id=default_package_id or None,
        packages=packages,
        switch_order=[str(item) for item in list(payload.get("switch_order") or [])],
        source_reports={str(key): str(value) for key, value in dict(payload.get("source_reports") or {}).items()},
    )


def _default_demo_preset_id(
    demo_session: DemoSessionRecord,
    *,
    package_id: str | None,
    preset_kind: str,
) -> str | None:
    package = demo_session.package_by_id(package_id)
    if package is None:
        return None
    presets = package.action_presets if preset_kind == "action" else package.animation_presets
    if not presets:
        return None
    return presets[0].preset_id or None


def _demo_preset_by_id(
    package: DemoPackageRecord | None,
    *,
    preset_kind: str,
    preset_id: str | None,
) -> DemoPresetRecord | None:
    if package is None:
        return None
    presets = package.action_presets if preset_kind == "action" else package.animation_presets
    if preset_id:
        exact_match = next((preset for preset in presets if preset.preset_id == preset_id), None)
        if exact_match is not None:
            return exact_match
    return presets[0] if presets else None


def _read_json_if_exists(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    candidate = Path(path).expanduser().resolve()
    if not candidate.exists():
        return {}
    try:
        return _load_json(candidate)
    except Exception:
        return {}


def _request_defaults_from_session_source_reports(demo_session: DemoSessionRecord) -> tuple[dict[str, Any], dict[str, Any]]:
    e1_report = _read_json_if_exists(demo_session.source_reports.get("e1_report_path"))
    d8_report = _read_json_if_exists(demo_session.source_reports.get("d8_report_path"))
    action_profile = {
        **DEFAULT_ACTION_REQUEST_PROFILE,
        **dict(e1_report.get("fixed_execution_profile") or {}),
    }
    animation_profile = {
        **DEFAULT_ANIMATION_REQUEST_PROFILE,
        **dict(d8_report.get("fixed_execution_profile") or {}),
    }
    return action_profile, animation_profile


def _slot_binding_overrides_from_package_payload(package_payload: dict[str, Any]) -> list[dict[str, Any]]:
    overrides: list[dict[str, Any]] = []
    for field_name in ("clothing_binding", "fx_binding"):
        binding = dict(package_payload.get(field_name) or {})
        if binding:
            overrides.append(binding)
    return overrides


def _build_request_output_root(demo_session: DemoSessionRecord, package_id: str, request_kind: str, preset_id: str) -> str:
    session_path = Path(demo_session.session_manifest_path).expanduser().resolve()
    base_root = session_path.parent / "requests" / package_id / request_kind / preset_id
    return str(base_root.resolve())


def _resolved_animation_asset_for_preset(preset: DemoPresetRecord) -> str:
    return (
        preset.resolved_asset_path
        or str(preset.payload.get("retargeted_animation_asset_path") or "")
        or preset.requested_asset_path
    )


def build_demo_request(
    *,
    demo_session: DemoSessionRecord,
    selected_package_id: str | None,
    selected_action_preset_id: str | None,
    selected_animation_preset_id: str | None,
) -> DemoRequestRecord:
    if demo_session.status != "pass":
        return DemoRequestRecord(
            status="missing",
            selected_package_id=selected_package_id,
            selected_action_preset_id=selected_action_preset_id,
            selected_animation_preset_id=selected_animation_preset_id,
            errors=["demo_session_missing"],
        )

    package = demo_session.package_by_id(selected_package_id or demo_session.default_package_id)
    if package is None:
        return DemoRequestRecord(
            status="error",
            selected_package_id=selected_package_id,
            selected_action_preset_id=selected_action_preset_id,
            selected_animation_preset_id=selected_animation_preset_id,
            errors=["demo_package_missing"],
        )

    action_profile, animation_profile = _request_defaults_from_session_source_reports(demo_session)
    action_preset = _demo_preset_by_id(
        package,
        preset_kind="action",
        preset_id=selected_action_preset_id,
    )
    animation_preset = _demo_preset_by_id(
        package,
        preset_kind="animation",
        preset_id=selected_animation_preset_id,
    )

    package_payload = dict(package.payload or {})
    level_path = str(package_payload.get("level_path") or demo_session.level_path or "")
    hero_shot_id = str(package_payload.get("hero_shot_id") or package.hero_shot_id or "")
    hero_shot_plan = dict(package_payload.get("hero_shot_plan") or {})
    request_warnings: list[str] = []
    request_errors: list[str] = []
    requests: dict[str, dict[str, Any]] = {}

    if not hero_shot_id or not hero_shot_plan:
        request_errors.append("hero_shot_plan_missing")

    common_payload = {
        "package_id": package.package_id,
        "sample_id": package.sample_id,
        "host_blueprint_asset_path": package.host_blueprint_asset,
        "level_path": level_path,
        "location": dict(package_payload.get("spawn_location") or {}),
        "rotation": dict(package_payload.get("spawn_rotation") or {}),
        "shot_order": [hero_shot_id] if hero_shot_id else [],
        "shot_plans": [hero_shot_plan] if hero_shot_plan else [],
        "slot_binding_overrides": _slot_binding_overrides_from_package_payload(package_payload),
    }

    if action_preset is not None and not request_errors:
        action_params = {
            **common_payload,
            "output_root": _build_request_output_root(
                demo_session,
                package.package_id,
                "action_preview",
                action_preset.preset_id or "action",
            ),
            "capture_width": int(action_profile.get("capture_width") or DEFAULT_ACTION_REQUEST_PROFILE["capture_width"]),
            "capture_height": int(action_profile.get("capture_height") or DEFAULT_ACTION_REQUEST_PROFILE["capture_height"]),
            "capture_delay_seconds": float(action_profile.get("capture_delay_seconds") or DEFAULT_ACTION_REQUEST_PROFILE["capture_delay_seconds"]),
            "subject_min_screen_coverage": float(action_profile.get("subject_min_screen_coverage") or DEFAULT_ACTION_REQUEST_PROFILE["subject_min_screen_coverage"]),
            "weapon_min_screen_coverage": float(action_profile.get("weapon_min_screen_coverage") or DEFAULT_ACTION_REQUEST_PROFILE["weapon_min_screen_coverage"]),
            "scene_capture_source": str(action_profile.get("scene_capture_source") or DEFAULT_ACTION_REQUEST_PROFILE["scene_capture_source"]),
            "scene_capture_warmup_count": int(action_profile.get("scene_capture_warmup_count") or DEFAULT_ACTION_REQUEST_PROFILE["scene_capture_warmup_count"]),
            "scene_capture_warmup_delay_seconds": float(action_profile.get("scene_capture_warmup_delay_seconds") or DEFAULT_ACTION_REQUEST_PROFILE["scene_capture_warmup_delay_seconds"]),
            "tracked_slots": list(action_profile.get("tracked_slots") or DEFAULT_ACTION_REQUEST_PROFILE["tracked_slots"]),
            "min_distance_delta": float(action_profile.get("min_distance_delta") or DEFAULT_ACTION_REQUEST_PROFILE["min_distance_delta"]),
            "min_yaw_delta": float(action_profile.get("min_yaw_delta") or DEFAULT_ACTION_REQUEST_PROFILE["min_yaw_delta"]),
            "action_kind": str(action_preset.payload.get("action_kind") or "root_translate_and_turn"),
            "action_distance": float(action_preset.payload.get("action_distance") or action_preset.payload.get("expected_distance_delta") or 85.0),
            "action_yaw_delta": float(action_preset.payload.get("action_yaw_delta") or action_preset.payload.get("expected_yaw_delta") or 24.0),
            "action_settle_seconds": float(action_preset.payload.get("action_settle_seconds") or 0.2),
        }
        fx_binding = dict(package_payload.get("fx_binding") or {})
        if fx_binding:
            action_params["prime_niagara_before_capture"] = True
            action_params["niagara_desired_age_seconds"] = float(fx_binding.get("niagara_desired_age_seconds") or 0.08)
            action_params["niagara_seek_delta_seconds"] = float(fx_binding.get("niagara_seek_delta_seconds") or (1.0 / 60.0))
            action_params["niagara_advance_step_count"] = int(fx_binding.get("niagara_advance_step_count") or 4)
            action_params["niagara_advance_step_delta_seconds"] = float(fx_binding.get("niagara_advance_step_delta_seconds") or (1.0 / 60.0))
            action_params["niagara_flush_world"] = True
        requests["action_preview"] = {
            "host_key": demo_session.host_key or "demo",
            "mode": demo_session.mode or "editor_rendered",
            "command": "action-preview",
            "params": action_params,
        }

    if animation_preset is not None and not request_errors:
        resolved_animation_asset = _resolved_animation_asset_for_preset(animation_preset)
        if not resolved_animation_asset:
            request_warnings.append("animation_asset_missing")
        else:
            animation_params = {
                **common_payload,
                "output_root": _build_request_output_root(
                    demo_session,
                    package.package_id,
                    "animation_preview",
                    animation_preset.preset_id or "animation",
                ),
                "capture_width": int(animation_profile.get("capture_width") or DEFAULT_ANIMATION_REQUEST_PROFILE["capture_width"]),
                "capture_height": int(animation_profile.get("capture_height") or DEFAULT_ANIMATION_REQUEST_PROFILE["capture_height"]),
                "capture_delay_seconds": float(animation_profile.get("capture_delay_seconds") or DEFAULT_ANIMATION_REQUEST_PROFILE["capture_delay_seconds"]),
                "subject_min_screen_coverage": float(animation_profile.get("subject_min_screen_coverage") or DEFAULT_ANIMATION_REQUEST_PROFILE["subject_min_screen_coverage"]),
                "weapon_min_screen_coverage": float(animation_profile.get("weapon_min_screen_coverage") or DEFAULT_ANIMATION_REQUEST_PROFILE["weapon_min_screen_coverage"]),
                "animation_asset_path": resolved_animation_asset,
                "animation_sample_time_seconds": float(animation_profile.get("animation_sample_time_seconds") or DEFAULT_ANIMATION_REQUEST_PROFILE["animation_sample_time_seconds"]),
                "animation_settle_seconds": float(animation_profile.get("animation_settle_seconds") or DEFAULT_ANIMATION_REQUEST_PROFILE["animation_settle_seconds"]),
                "retarget_if_needed": bool(animation_profile.get("retarget_if_needed", DEFAULT_ANIMATION_REQUEST_PROFILE["retarget_if_needed"])),
                "pose_probe_bone_names": list(animation_profile.get("pose_probe_bone_names") or DEFAULT_ANIMATION_REQUEST_PROFILE["pose_probe_bone_names"]),
            }
            requests["animation_preview"] = {
                "host_key": demo_session.host_key or "demo",
                "mode": demo_session.mode or "editor_rendered",
                "command": "animation-preview",
                "params": animation_params,
            }

    if not requests and not request_errors:
        request_errors.append("no_requestable_preset_available")

    status = "pass" if not request_errors else "error"
    return DemoRequestRecord(
        status=status,
        selected_package_id=package.package_id,
        selected_action_preset_id=action_preset.preset_id if action_preset is not None else None,
        selected_animation_preset_id=animation_preset.preset_id if animation_preset is not None else None,
        requests=requests,
        warnings=request_warnings,
        errors=request_errors,
    )


def load_workbench_state(
    manifest_path: str | Path,
    *,
    session_manifest_path: str | Path | None = None,
) -> AppState:
    resolved_manifest_path = Path(manifest_path).expanduser().resolve()
    if not resolved_manifest_path.exists():
        return _error_app_state(
            manifest_path=resolved_manifest_path,
            code="manifest_missing",
            message="The requested T1 manifest does not exist.",
        )
    try:
        manifest = _load_json(resolved_manifest_path)
    except json.JSONDecodeError as exc:
        return _error_app_state(
            manifest_path=resolved_manifest_path,
            code="manifest_invalid_json",
            message=f"Failed to parse manifest JSON: {exc}",
        )

    pack_root = resolved_manifest_path.parent
    errors: list[ErrorRecord] = []
    report_categories, reports_by_gate_id = _load_report_categories(
        manifest=manifest,
        pack_root=pack_root,
        errors=errors,
    )
    preview_images = _load_preview_images(
        manifest=manifest,
        pack_root=pack_root,
        errors=errors,
    )
    quality_summaries = _load_quality_summaries(
        manifest=manifest,
        pack_root=pack_root,
    )
    slot_debugger = dict(manifest.get("slot_debugger") or {})
    demo_session = _load_demo_session(
        manifest_path=resolved_manifest_path,
        session_manifest_path=session_manifest_path,
        errors=errors,
    )
    summary_counts = _coerce_summary_counts(dict(manifest.get("report_index") or {}))
    default_report_gate_id = _default_report_gate_id(report_categories)
    default_image_key = preview_images[0].key if preview_images else None
    slot_packages = list(slot_debugger.get("packages") or [])
    governance_balance = _extract_governance_balance(reports_by_gate_id)
    default_package_id = demo_session.default_package_id or (str(slot_packages[0].get("package_id") or "") if slot_packages else None)
    default_action_preset_id = _default_demo_preset_id(
        demo_session,
        package_id=default_package_id,
        preset_kind="action",
    )
    default_animation_preset_id = _default_demo_preset_id(
        demo_session,
        package_id=default_package_id,
        preset_kind="animation",
    )
    demo_request = build_demo_request(
        demo_session=demo_session,
        selected_package_id=default_package_id,
        selected_action_preset_id=default_action_preset_id,
        selected_animation_preset_id=default_animation_preset_id,
    )
    return AppState(
        status="pass" if not errors else "error",
        manifest_path=str(resolved_manifest_path),
        pack_root=str(pack_root),
        generated_at_utc=str(manifest.get("generated_at_utc") or ""),
        summary_counts=summary_counts,
        report_categories=report_categories,
        reports_by_gate_id=reports_by_gate_id,
        preview_images=preview_images,
        r3_metrics=_extract_r3_metrics(reports_by_gate_id),
        quality_summaries=quality_summaries,
        slot_debugger=slot_debugger,
        governance_balance=governance_balance,
        demo_session=demo_session,
        demo_request=demo_request,
        errors=errors,
        default_report_gate_id=default_report_gate_id,
        default_image_key=default_image_key,
        default_package_id=default_package_id,
        default_action_preset_id=default_action_preset_id,
        default_animation_preset_id=default_animation_preset_id,
    )
