from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aiue_t2.state_models import (
    DemoPackageRecord,
    DemoPresetRecord,
    DemoRequestRecord,
    DemoSessionRecord,
    ErrorRecord,
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


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def discover_latest_session_manifest_path(manifest_path: Path) -> Path | None:
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
    return discover_latest_session_manifest_path(manifest_path), False


def demo_preset_from_payload(payload: dict[str, Any], *, preset_kind: str) -> DemoPresetRecord:
    return DemoPresetRecord(
        preset_id=str(payload.get("preset_id") or ""),
        preset_kind=preset_kind,
        family=str(payload.get("family") or ""),
        source_gate_id=str(payload.get("source_gate_id") or ""),
        status=str(payload.get("status") or ""),
        requested_asset_path=str(payload.get("requested_animation_asset_path") or payload.get("requested_asset_path") or ""),
        resolved_asset_path=str(
            payload.get("resolved_animation_asset_path")
            or payload.get("resolved_asset_path")
            or payload.get("retargeted_animation_asset_path")
            or ""
        ),
        payload=dict(payload),
    )


def load_demo_session(
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
        slot_names = [
            str(item.get("slot_name") or "")
            for item in list(package_payload.get("slot_bindings") or [])
            if str(item.get("slot_name") or "")
        ]
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
                action_presets=[
                    demo_preset_from_payload(dict(item), preset_kind="action")
                    for item in list(package_payload.get("action_presets") or [])
                ],
                animation_presets=[
                    demo_preset_from_payload(dict(item), preset_kind="animation")
                    for item in list(package_payload.get("animation_presets") or [])
                ],
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


def default_demo_preset_id(
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


def demo_preset_by_id(
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


def request_defaults_from_session_source_reports(demo_session: DemoSessionRecord) -> tuple[dict[str, Any], dict[str, Any]]:
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


def slot_binding_overrides_from_package_payload(package_payload: dict[str, Any]) -> list[dict[str, Any]]:
    overrides: list[dict[str, Any]] = []
    for field_name in ("clothing_binding", "fx_binding"):
        binding = dict(package_payload.get(field_name) or {})
        if binding:
            overrides.append(binding)
    return overrides


def build_request_output_root(demo_session: DemoSessionRecord, package_id: str, request_kind: str, preset_id: str) -> str:
    session_path = Path(demo_session.session_manifest_path).expanduser().resolve()
    base_root = session_path.parent / "requests" / package_id / request_kind / preset_id
    return str(base_root.resolve())


def resolved_animation_asset_for_preset(preset: DemoPresetRecord) -> str:
    return (
        preset.resolved_asset_path
        or str(preset.payload.get("retargeted_animation_asset_path") or "")
        or preset.requested_asset_path
    )


def _preset_text(payload: dict[str, Any], field_name: str) -> str:
    return str(payload.get(field_name) or "")


def _preset_text_list(payload: dict[str, Any], field_name: str) -> list[str]:
    return [str(item) for item in list(payload.get(field_name) or []) if str(item)]


def animation_request_fields_for_preset(
    preset: DemoPresetRecord,
    *,
    animation_profile: dict[str, Any],
) -> dict[str, Any]:
    payload = dict(preset.payload or {})
    requested_animation_asset = preset.requested_asset_path or _preset_text(payload, "requested_animation_asset_path")
    resolved_animation_asset = resolved_animation_asset_for_preset(preset)
    retarget_source_ik_rig_asset_path = _preset_text(payload, "retarget_source_ik_rig_asset_path")
    retarget_target_ik_rig_asset_path = _preset_text(payload, "retarget_target_ik_rig_asset_path")
    retarget_source_mesh_asset_path = _preset_text(payload, "retarget_source_mesh_asset_path")
    retarget_target_mesh_asset_path = _preset_text(payload, "retarget_target_mesh_asset_path")
    retarget_profile_available = bool(
        requested_animation_asset
        and retarget_source_ik_rig_asset_path
        and retarget_target_ik_rig_asset_path
        and retarget_source_mesh_asset_path
    )
    animation_asset_path = (
        requested_animation_asset
        if retarget_profile_available
        else (resolved_animation_asset or requested_animation_asset)
    )
    pose_probe_bone_names = _preset_text_list(payload, "pose_probe_bone_names") or list(
        animation_profile.get("pose_probe_bone_names") or DEFAULT_ANIMATION_REQUEST_PROFILE["pose_probe_bone_names"]
    )
    request_fields = {
        "animation_asset_path": animation_asset_path,
        "animation_sample_time_seconds": float(
            payload.get("animation_sample_time_seconds")
            or animation_profile.get("animation_sample_time_seconds")
            or DEFAULT_ANIMATION_REQUEST_PROFILE["animation_sample_time_seconds"]
        ),
        "animation_settle_seconds": float(
            animation_profile.get("animation_settle_seconds")
            or DEFAULT_ANIMATION_REQUEST_PROFILE["animation_settle_seconds"]
        ),
        "retarget_if_needed": bool(
            retarget_profile_available
            or animation_profile.get("retarget_if_needed", DEFAULT_ANIMATION_REQUEST_PROFILE["retarget_if_needed"])
        ),
        "pose_probe_bone_names": pose_probe_bone_names,
    }
    if retarget_source_ik_rig_asset_path:
        request_fields["retarget_source_ik_rig_asset_path"] = retarget_source_ik_rig_asset_path
    if retarget_target_ik_rig_asset_path:
        request_fields["retarget_target_ik_rig_asset_path"] = retarget_target_ik_rig_asset_path
    if retarget_source_mesh_asset_path:
        request_fields["retarget_source_mesh_asset_path"] = retarget_source_mesh_asset_path
    if retarget_target_mesh_asset_path:
        request_fields["retarget_target_mesh_asset_path"] = retarget_target_mesh_asset_path
    retargeter_asset_path = _preset_text(payload, "retargeter_asset_path")
    if retargeter_asset_path:
        request_fields["retargeter_asset_path"] = retargeter_asset_path
    return request_fields


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

    action_profile, animation_profile = request_defaults_from_session_source_reports(demo_session)
    action_preset = demo_preset_by_id(
        package,
        preset_kind="action",
        preset_id=selected_action_preset_id,
    )
    animation_preset = demo_preset_by_id(
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
        "slot_binding_overrides": slot_binding_overrides_from_package_payload(package_payload),
    }

    if action_preset is not None and not request_errors:
        action_params = {
            **common_payload,
            "output_root": build_request_output_root(
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
        animation_request_fields = animation_request_fields_for_preset(
            animation_preset,
            animation_profile=animation_profile,
        )
        if not str(animation_request_fields.get("animation_asset_path") or ""):
            request_warnings.append("animation_asset_missing")
        else:
            animation_params = {
                **common_payload,
                "output_root": build_request_output_root(
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
                **animation_request_fields,
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
