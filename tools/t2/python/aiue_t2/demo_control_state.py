from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiue_core.schema_utils import load_json, write_json


CONTROL_STATE_FILENAME = "playable_demo_e2_control_state.json"
REQUEST_KINDS = ("action_preview", "animation_preview")
MIN_ACTION_DISTANCE_DELTA = 40.0
MIN_ACTION_YAW_DELTA = 10.0


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def control_state_path_from_session_manifest(session_manifest_path: str | Path | None) -> Path | None:
    if not session_manifest_path:
        return None
    resolved_session_path = Path(session_manifest_path).expanduser().resolve()
    return resolved_session_path.parent / CONTROL_STATE_FILENAME


def load_demo_control_state(session_manifest_path: str | Path | None) -> dict[str, Any]:
    resolved_path = control_state_path_from_session_manifest(session_manifest_path)
    if resolved_path is None:
        return _missing_control_state_payload(None)
    if not resolved_path.exists():
        return _missing_control_state_payload(resolved_path)
    try:
        payload = load_json(resolved_path)
    except Exception as exc:
        return {
            **_missing_control_state_payload(resolved_path),
            "status": "error",
            "errors": [f"control_state_invalid_json:{exc}"],
        }
    return _normalize_control_state_payload(payload, resolved_path)


def write_demo_control_run(
    *,
    session_manifest_path: str | Path | None,
    session_id: str,
    selected_package_id: str | None,
    selected_action_preset_id: str | None,
    selected_animation_preset_id: str | None,
    request_kind: str,
    operation: str,
    invocation: dict[str, Any],
) -> dict[str, Any]:
    resolved_path = control_state_path_from_session_manifest(session_manifest_path)
    if resolved_path is None:
        raise RuntimeError("demo_control_state_session_manifest_missing")
    existing = load_demo_control_state(session_manifest_path)
    last_runs_by_package = dict(existing.get("last_runs_by_package") or {})
    package_key = str(selected_package_id or "")
    if not package_key:
        raise RuntimeError("demo_control_state_package_missing")
    package_runs = dict(last_runs_by_package.get(package_key) or {})
    package_runs[str(request_kind or "")] = build_control_run_summary(
        request_kind=request_kind,
        operation=operation,
        selected_package_id=selected_package_id,
        selected_action_preset_id=selected_action_preset_id,
        selected_animation_preset_id=selected_animation_preset_id,
        invocation=invocation,
    )
    last_runs_by_package[package_key] = package_runs
    payload = {
        "status": "pass",
        "session_id": str(session_id or ""),
        "generated_at_utc": now_utc(),
        "selected_package_id": selected_package_id,
        "selected_action_preset_id": selected_action_preset_id,
        "selected_animation_preset_id": selected_animation_preset_id,
        "last_runs_by_package": last_runs_by_package,
    }
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(resolved_path, payload)
    return _normalize_control_state_payload(payload, resolved_path)


def build_control_run_summary(
    *,
    request_kind: str,
    operation: str,
    selected_package_id: str | None,
    selected_action_preset_id: str | None,
    selected_animation_preset_id: str | None,
    invocation: dict[str, Any],
) -> dict[str, Any]:
    resolved_request_kind = str(request_kind or "").strip()
    if resolved_request_kind not in REQUEST_KINDS:
        raise ValueError(f"Unsupported demo control request kind: {resolved_request_kind}")
    host_payload = _host_payload_from_invocation(invocation)
    credibility_summary = build_credibility_summary(
        request_kind=resolved_request_kind,
        host_payload=host_payload,
    )
    result_payload = dict(host_payload.get("result") or {})
    result_status = str(result_payload.get("status") or host_payload.get("status") or "")
    return {
        "request_kind": resolved_request_kind,
        "operation": str(operation or ""),
        "request_json_path": str(invocation.get("request_json_path") or ""),
        "result_json_path": str(invocation.get("result_json_path") or ""),
        "result_status": result_status,
        "host_key": str(invocation.get("host_key") or host_payload.get("host_key") or ""),
        "generated_at_utc": str(host_payload.get("generated_at_utc") or now_utc()),
        "selected_package_id": selected_package_id,
        "selected_action_preset_id": selected_action_preset_id,
        "selected_animation_preset_id": selected_animation_preset_id,
        "key_image_paths": _key_image_paths_from_host_payload(host_payload),
        "credibility_summary": credibility_summary,
    }


def build_credibility_summary(*, request_kind: str, host_payload: dict[str, Any]) -> dict[str, Any]:
    result_payload = dict(host_payload.get("result") or {})
    shots = [dict(item) for item in list(result_payload.get("shots") or [])]
    result_status = str(result_payload.get("status") or host_payload.get("status") or "")
    before_image_present = any(_image_exists(_phase_image_path(dict(shot.get("before") or {}))) for shot in shots)
    after_image_present = any(_image_exists(_phase_image_path(dict(shot.get("after") or {}))) for shot in shots)
    subject_visible = any(_shot_subject_visible(shot) for shot in shots)

    transform_delta = dict(result_payload.get("transform_delta") or {})
    distance_delta = float(transform_delta.get("distance_delta") or 0.0)
    yaw_delta = float(transform_delta.get("yaw_delta") or 0.0)
    native_pose = dict(result_payload.get("native_animation_pose_evaluation") or {})
    pose_probe_delta = dict(result_payload.get("pose_probe_delta") or {})
    moving_bone_count = int(pose_probe_delta.get("moving_bone_count") or 0)
    pose_changed = bool(native_pose.get("pose_changed"))

    action_motion_verified = bool(
        request_kind == "action_preview"
        and result_status == "pass"
        and before_image_present
        and after_image_present
        and subject_visible
        and (distance_delta >= MIN_ACTION_DISTANCE_DELTA or abs(yaw_delta) >= MIN_ACTION_YAW_DELTA)
    )
    animation_pose_verified = bool(
        request_kind == "animation_preview"
        and result_status == "pass"
        and before_image_present
        and after_image_present
        and subject_visible
        and (pose_changed or moving_bone_count > 0)
    )

    warning_flags: list[str] = []
    if result_status != "pass":
        warning_flags.append("result_status_not_pass")
    if not before_image_present:
        warning_flags.append("before_image_missing")
    if not after_image_present:
        warning_flags.append("after_image_missing")
    if not subject_visible:
        warning_flags.append("subject_not_visible")
    if request_kind == "action_preview" and not action_motion_verified:
        warning_flags.append("action_motion_not_verified")
    if request_kind == "animation_preview" and not animation_pose_verified:
        warning_flags.append("animation_pose_not_verified")
    if not _any_weapon_visible(shots):
        warning_flags.append("weapon_not_visible")
    if not _any_tracked_slot_visible(shots, "fx"):
        warning_flags.append("fx_not_visible")

    return {
        "subject_visible": subject_visible,
        "before_image_present": before_image_present,
        "after_image_present": after_image_present,
        "action_motion_verified": action_motion_verified,
        "animation_pose_verified": animation_pose_verified,
        "warning_flags": warning_flags,
        "transform_delta": {
            "distance_delta": distance_delta,
            "yaw_delta": yaw_delta,
        },
        "native_animation_pose_evaluation": {
            "pose_changed": pose_changed,
            "changed_bone_count": int(native_pose.get("changed_bone_count") or 0),
        },
        "pose_probe_delta": {
            "moving_bone_count": moving_bone_count,
            "max_location_delta": float(pose_probe_delta.get("max_location_delta") or 0.0),
        },
    }


def _missing_control_state_payload(control_state_path: Path | None) -> dict[str, Any]:
    return {
        "status": "missing",
        "control_state_path": str(control_state_path) if control_state_path else "",
        "session_id": "",
        "generated_at_utc": "",
        "selected_package_id": None,
        "selected_action_preset_id": None,
        "selected_animation_preset_id": None,
        "package_run_counts": {},
        "last_runs_by_package": {},
        "errors": [],
    }


def _normalize_control_state_payload(payload: dict[str, Any], control_state_path: Path) -> dict[str, Any]:
    last_runs_by_package = _normalize_last_runs_by_package(dict(payload.get("last_runs_by_package") or {}))
    package_run_counts = {package_id: len(package_runs) for package_id, package_runs in last_runs_by_package.items()}
    return {
        "status": str(payload.get("status") or ("pass" if last_runs_by_package else "missing")),
        "control_state_path": str(control_state_path),
        "session_id": str(payload.get("session_id") or ""),
        "generated_at_utc": str(payload.get("generated_at_utc") or ""),
        "selected_package_id": payload.get("selected_package_id"),
        "selected_action_preset_id": payload.get("selected_action_preset_id"),
        "selected_animation_preset_id": payload.get("selected_animation_preset_id"),
        "package_run_counts": package_run_counts,
        "last_runs_by_package": last_runs_by_package,
        "errors": [str(item) for item in list(payload.get("errors") or [])],
    }


def _normalize_last_runs_by_package(last_runs_by_package: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    normalized: dict[str, dict[str, dict[str, Any]]] = {}
    for package_id, package_runs in last_runs_by_package.items():
        resolved_package_id = str(package_id or "").strip()
        if not resolved_package_id:
            continue
        normalized_runs: dict[str, dict[str, Any]] = {}
        for request_kind, run_payload in dict(package_runs or {}).items():
            resolved_request_kind = str(request_kind or "").strip()
            if not resolved_request_kind:
                continue
            normalized_runs[resolved_request_kind] = _normalize_run_payload(dict(run_payload or {}))
        normalized[resolved_package_id] = normalized_runs
    return normalized


def _normalize_run_payload(run_payload: dict[str, Any]) -> dict[str, Any]:
    credibility_summary = dict(run_payload.get("credibility_summary") or {})
    return {
        "request_kind": str(run_payload.get("request_kind") or ""),
        "operation": str(run_payload.get("operation") or ""),
        "request_json_path": str(run_payload.get("request_json_path") or ""),
        "result_json_path": str(run_payload.get("result_json_path") or ""),
        "result_status": str(run_payload.get("result_status") or ""),
        "host_key": str(run_payload.get("host_key") or ""),
        "generated_at_utc": str(run_payload.get("generated_at_utc") or ""),
        "selected_package_id": run_payload.get("selected_package_id"),
        "selected_action_preset_id": run_payload.get("selected_action_preset_id"),
        "selected_animation_preset_id": run_payload.get("selected_animation_preset_id"),
        "key_image_paths": dict(run_payload.get("key_image_paths") or {}),
        "credibility_summary": {
            "subject_visible": bool(credibility_summary.get("subject_visible")),
            "before_image_present": bool(credibility_summary.get("before_image_present")),
            "after_image_present": bool(credibility_summary.get("after_image_present")),
            "action_motion_verified": bool(credibility_summary.get("action_motion_verified")),
            "animation_pose_verified": bool(credibility_summary.get("animation_pose_verified")),
            "warning_flags": [str(item) for item in list(credibility_summary.get("warning_flags") or [])],
            "transform_delta": dict(credibility_summary.get("transform_delta") or {}),
            "native_animation_pose_evaluation": dict(credibility_summary.get("native_animation_pose_evaluation") or {}),
            "pose_probe_delta": dict(credibility_summary.get("pose_probe_delta") or {}),
        },
    }


def _host_payload_from_invocation(invocation: dict[str, Any]) -> dict[str, Any]:
    host_payload = dict(invocation.get("payload") or {})
    if host_payload:
        return host_payload
    result_json_path = str(invocation.get("result_json_path") or "")
    if result_json_path and Path(result_json_path).exists():
        try:
            return load_json(Path(result_json_path))
        except Exception:
            return {}
    return {}


def _phase_image_path(phase_payload: dict[str, Any]) -> str:
    return str(phase_payload.get("image_path") or "")


def _image_exists(path: str) -> bool:
    return bool(path) and Path(path).exists()


def _phase_subject_visible(phase_payload: dict[str, Any]) -> bool:
    quality_gate = dict(phase_payload.get("quality_gate") or {})
    if "subject_visible" in quality_gate:
        return bool(quality_gate.get("subject_visible"))
    return bool(phase_payload.get("line_of_sight_clear")) and float(phase_payload.get("subject_screen_coverage") or 0.0) > 0.0


def _shot_subject_visible(shot_payload: dict[str, Any]) -> bool:
    before = dict(shot_payload.get("before") or {})
    after = dict(shot_payload.get("after") or {})
    return _phase_subject_visible(before) and _phase_subject_visible(after)


def _any_weapon_visible(shots: list[dict[str, Any]]) -> bool:
    for shot in shots:
        for phase_key in ("before", "after"):
            phase_payload = dict(shot.get(phase_key) or {})
            if float(phase_payload.get("weapon_screen_coverage") or 0.0) > 0.0:
                return True
    return False


def _any_tracked_slot_visible(shots: list[dict[str, Any]], slot_name: str) -> bool:
    for shot in shots:
        for phase_key in ("before", "after"):
            phase_payload = dict(shot.get(phase_key) or {})
            coverage_payload = dict((phase_payload.get("tracked_slot_coverages") or {}).get(slot_name) or {})
            if float(coverage_payload.get("coverage_ratio") or 0.0) > 0.0:
                return True
    return False


def _key_image_paths_from_host_payload(host_payload: dict[str, Any]) -> dict[str, Any]:
    result_payload = dict(host_payload.get("result") or {})
    before_paths: list[str] = []
    after_paths: list[str] = []
    for shot in list(result_payload.get("shots") or []):
        before_path = _phase_image_path(dict(shot.get("before") or {}))
        after_path = _phase_image_path(dict(shot.get("after") or {}))
        if before_path:
            before_paths.append(before_path)
        if after_path:
            after_paths.append(after_path)
    return {
        "before": before_paths,
        "after": after_paths,
        "primary_before": before_paths[0] if before_paths else "",
        "primary_after": after_paths[0] if after_paths else "",
    }
