from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiue_core.schema_utils import load_json, write_json
from aiue_t2.demo_control_state import build_control_run_summary


REPLAY_STATE_FILENAME = "playable_demo_e2_review_replay_state.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def replay_state_path_from_session_manifest(session_manifest_path: str | Path | None) -> Path | None:
    if not session_manifest_path:
        return None
    resolved_session_path = Path(session_manifest_path).expanduser().resolve()
    return resolved_session_path.parent / REPLAY_STATE_FILENAME


def load_demo_review_replay_state(session_manifest_path: str | Path | None) -> dict[str, Any]:
    resolved_path = replay_state_path_from_session_manifest(session_manifest_path)
    if resolved_path is None:
        return _missing_replay_state_payload(None)
    if not resolved_path.exists():
        return _missing_replay_state_payload(resolved_path)
    try:
        payload = load_json(resolved_path)
    except Exception as exc:
        return {
            **_missing_replay_state_payload(resolved_path),
            "status": "error",
            "errors": [f"review_replay_state_invalid_json:{exc}"],
        }
    return _normalize_replay_state_payload(payload, resolved_path)


def write_demo_review_replay_run(
    *,
    session_manifest_path: str | Path | None,
    source_review_state_path: str | None,
    session_id: str,
    selected_package_id: str | None,
    selected_action_preset_id: str | None,
    selected_animation_preset_id: str | None,
    request_kind: str,
    invocation: dict[str, Any],
) -> dict[str, Any]:
    resolved_path = replay_state_path_from_session_manifest(session_manifest_path)
    if resolved_path is None:
        raise RuntimeError("demo_review_replay_state_session_manifest_missing")
    existing = load_demo_review_replay_state(session_manifest_path)
    last_replays_by_package = dict(existing.get("last_replays_by_package") or {})
    package_key = str(selected_package_id or "")
    if not package_key:
        raise RuntimeError("demo_review_replay_state_package_missing")
    package_runs = dict(last_replays_by_package.get(package_key) or {})
    package_runs[str(request_kind or "")] = build_control_run_summary(
        request_kind=request_kind,
        operation="review_replay",
        selected_package_id=selected_package_id,
        selected_action_preset_id=selected_action_preset_id,
        selected_animation_preset_id=selected_animation_preset_id,
        invocation=invocation,
    )
    last_replays_by_package[package_key] = package_runs
    payload = {
        "status": "pass",
        "session_id": str(session_id or ""),
        "generated_at_utc": now_utc(),
        "selected_package_id": selected_package_id,
        "selected_action_preset_id": selected_action_preset_id,
        "selected_animation_preset_id": selected_animation_preset_id,
        "last_replay_kind": str(request_kind or ""),
        "source_review_state_path": str(source_review_state_path or ""),
        "last_replays_by_package": last_replays_by_package,
    }
    normalized_payload = _normalize_replay_state_payload(payload, resolved_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(resolved_path, normalized_payload)
    return normalized_payload


def _missing_replay_state_payload(replay_state_path: Path | None) -> dict[str, Any]:
    return {
        "status": "missing",
        "replay_state_path": str(replay_state_path) if replay_state_path else "",
        "session_id": "",
        "generated_at_utc": "",
        "selected_package_id": None,
        "selected_action_preset_id": None,
        "selected_animation_preset_id": None,
        "last_replay_kind": "",
        "source_review_state_path": "",
        "package_replay_counts": {},
        "last_replays_by_package": {},
        "errors": [],
    }


def _normalize_replay_state_payload(payload: dict[str, Any], replay_state_path: Path) -> dict[str, Any]:
    last_replays_by_package = _normalize_last_replays_by_package(dict(payload.get("last_replays_by_package") or {}))
    package_replay_counts = {package_id: len(package_runs) for package_id, package_runs in last_replays_by_package.items()}
    return {
        "status": str(payload.get("status") or ("pass" if last_replays_by_package else "missing")),
        "replay_state_path": str(replay_state_path),
        "session_id": str(payload.get("session_id") or ""),
        "generated_at_utc": str(payload.get("generated_at_utc") or ""),
        "selected_package_id": payload.get("selected_package_id"),
        "selected_action_preset_id": payload.get("selected_action_preset_id"),
        "selected_animation_preset_id": payload.get("selected_animation_preset_id"),
        "last_replay_kind": str(payload.get("last_replay_kind") or ""),
        "source_review_state_path": str(payload.get("source_review_state_path") or ""),
        "package_replay_counts": package_replay_counts,
        "last_replays_by_package": last_replays_by_package,
        "errors": [str(item) for item in list(payload.get("errors") or [])],
    }


def _normalize_last_replays_by_package(last_replays_by_package: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    normalized: dict[str, dict[str, dict[str, Any]]] = {}
    for package_id, package_runs in last_replays_by_package.items():
        resolved_package_id = str(package_id or "").strip()
        if not resolved_package_id:
            continue
        normalized_runs: dict[str, dict[str, Any]] = {}
        for request_kind, run_payload in dict(package_runs or {}).items():
            resolved_request_kind = str(request_kind or "").strip()
            if not resolved_request_kind:
                continue
            normalized_runs[resolved_request_kind] = dict(run_payload or {})
        normalized[resolved_package_id] = normalized_runs
    return normalized
