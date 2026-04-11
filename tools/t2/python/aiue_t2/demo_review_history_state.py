from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiue_core.schema_utils import load_json, write_json


HISTORY_STATE_FILENAME = "playable_demo_e2_review_history_state.json"
DEFAULT_HISTORY_LIMIT = 12


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def history_state_path_from_session_manifest(session_manifest_path: str | Path | None) -> Path | None:
    if not session_manifest_path:
        return None
    resolved_session_path = Path(session_manifest_path).expanduser().resolve()
    return resolved_session_path.parent / HISTORY_STATE_FILENAME


def load_demo_review_history_state(session_manifest_path: str | Path | None) -> dict[str, Any]:
    resolved_path = history_state_path_from_session_manifest(session_manifest_path)
    if resolved_path is None:
        return _missing_history_state_payload(None)
    if not resolved_path.exists():
        return _missing_history_state_payload(resolved_path)
    try:
        payload = load_json(resolved_path)
    except Exception as exc:
        return {
            **_missing_history_state_payload(resolved_path),
            "status": "error",
            "errors": [f"review_history_state_invalid_json:{exc}"],
        }
    return _normalize_history_state_payload(payload, resolved_path)


def build_demo_review_history_focus(demo_review_history_state: dict[str, Any], *, selected_package_id: str | None) -> dict[str, Any]:
    events = [dict(item) for item in list(demo_review_history_state.get("recent_events") or [])]
    if not selected_package_id:
        return {
            "status": "missing",
            "selected_package_id": "",
            "event_count": 0,
            "replay_kinds": [],
            "latest_event": {},
        }
    package_events = [item for item in events if str(item.get("package_id") or "") == str(selected_package_id or "")]
    if not package_events:
        return {
            "status": "missing",
            "selected_package_id": str(selected_package_id or ""),
            "event_count": 0,
            "replay_kinds": [],
            "latest_event": {},
        }
    latest_event = dict(package_events[0])
    replay_kinds = sorted({str(item.get("request_kind") or "") for item in package_events if str(item.get("request_kind") or "").strip()})
    return {
        "status": "pass",
        "selected_package_id": str(selected_package_id or ""),
        "event_count": len(package_events),
        "replay_kinds": replay_kinds,
        "latest_event": latest_event,
    }


def write_demo_review_history_event(
    *,
    session_manifest_path: str | Path | None,
    source_review_state_path: str | None,
    source_replay_state_path: str | None,
    session_id: str,
    selected_package_id: str | None,
    request_kind: str,
    replay_run: dict[str, Any],
) -> dict[str, Any]:
    resolved_path = history_state_path_from_session_manifest(session_manifest_path)
    if resolved_path is None:
        raise RuntimeError("demo_review_history_state_session_manifest_missing")
    existing = load_demo_review_history_state(session_manifest_path)
    recent_events = [dict(item) for item in list(existing.get("recent_events") or [])]
    event = {
        "history_event_id": f"{now_utc()}::{selected_package_id or 'unknown'}::{request_kind or 'unknown'}",
        "package_id": str(selected_package_id or ""),
        "request_kind": str(request_kind or ""),
        "operation": str(replay_run.get("operation") or "review_replay"),
        "generated_at_utc": str(replay_run.get("generated_at_utc") or now_utc()),
        "request_json_path": str(replay_run.get("request_json_path") or ""),
        "result_json_path": str(replay_run.get("result_json_path") or ""),
        "result_status": str(replay_run.get("result_status") or ""),
        "selected_action_preset_id": replay_run.get("selected_action_preset_id"),
        "selected_animation_preset_id": replay_run.get("selected_animation_preset_id"),
        "source_review_state_path": str(source_review_state_path or ""),
        "source_replay_state_path": str(source_replay_state_path or ""),
        "key_image_paths": dict(replay_run.get("key_image_paths") or {}),
        "credibility_summary": dict(replay_run.get("credibility_summary") or {}),
    }
    recent_events.insert(0, event)
    recent_events = recent_events[:DEFAULT_HISTORY_LIMIT]
    payload = {
        "status": "pass",
        "session_id": str(session_id or ""),
        "generated_at_utc": now_utc(),
        "retention_limit": DEFAULT_HISTORY_LIMIT,
        "source_review_state_path": str(source_review_state_path or ""),
        "source_replay_state_path": str(source_replay_state_path or ""),
        "recent_events": recent_events,
    }
    normalized_payload = _normalize_history_state_payload(payload, resolved_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(resolved_path, normalized_payload)
    return normalized_payload


def _missing_history_state_payload(history_state_path: Path | None) -> dict[str, Any]:
    return {
        "status": "missing",
        "history_state_path": str(history_state_path) if history_state_path else "",
        "session_id": "",
        "generated_at_utc": "",
        "retention_limit": DEFAULT_HISTORY_LIMIT,
        "source_review_state_path": "",
        "source_replay_state_path": "",
        "package_history_counts": {},
        "request_kind_counts": {},
        "recent_events": [],
        "errors": [],
    }


def _normalize_history_state_payload(payload: dict[str, Any], history_state_path: Path) -> dict[str, Any]:
    recent_events = [dict(item) for item in list(payload.get("recent_events") or [])]
    package_history_counts: dict[str, int] = {}
    request_kind_counts: dict[str, int] = {}
    for event in recent_events:
        package_id = str(event.get("package_id") or "").strip()
        request_kind = str(event.get("request_kind") or "").strip()
        if package_id:
            package_history_counts[package_id] = int(package_history_counts.get(package_id, 0)) + 1
        if request_kind:
            request_kind_counts[request_kind] = int(request_kind_counts.get(request_kind, 0)) + 1
    return {
        "status": str(payload.get("status") or ("pass" if recent_events else "missing")),
        "history_state_path": str(history_state_path),
        "session_id": str(payload.get("session_id") or ""),
        "generated_at_utc": str(payload.get("generated_at_utc") or ""),
        "retention_limit": int(payload.get("retention_limit") or DEFAULT_HISTORY_LIMIT),
        "source_review_state_path": str(payload.get("source_review_state_path") or ""),
        "source_replay_state_path": str(payload.get("source_replay_state_path") or ""),
        "package_history_counts": package_history_counts,
        "request_kind_counts": request_kind_counts,
        "recent_events": recent_events,
        "errors": [str(item) for item in list(payload.get("errors") or [])],
    }
