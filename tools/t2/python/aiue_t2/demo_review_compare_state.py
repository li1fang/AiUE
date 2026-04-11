from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiue_core.schema_utils import load_json, write_json


COMPARE_STATE_FILENAME = "playable_demo_e2_review_compare_state.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def compare_state_path_from_session_manifest(session_manifest_path: str | Path | None) -> Path | None:
    if not session_manifest_path:
        return None
    resolved_session_path = Path(session_manifest_path).expanduser().resolve()
    return resolved_session_path.parent / COMPARE_STATE_FILENAME


def load_demo_review_compare_state(
    session_manifest_path: str | Path | None,
    *,
    demo_review_history_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_path = compare_state_path_from_session_manifest(session_manifest_path)
    if resolved_path is None:
        return _missing_compare_state_payload(None)
    history_state = dict(demo_review_history_state or {})
    if resolved_path.exists():
        try:
            payload = load_json(resolved_path)
        except Exception as exc:
            if str(history_state.get("status") or "") == "pass":
                return build_demo_review_compare_state(history_state, compare_state_path=resolved_path, persisted=False)
            return {
                **_missing_compare_state_payload(resolved_path),
                "status": "error",
                "errors": [f"review_compare_state_invalid_json:{exc}"],
            }
        if str(history_state.get("status") or "") == "pass":
            return build_demo_review_compare_state(history_state, compare_state_path=resolved_path, persisted=True)
        return _normalize_compare_state_payload(payload, resolved_path)
    if str(history_state.get("status") or "") == "pass":
        return build_demo_review_compare_state(history_state, compare_state_path=resolved_path, persisted=False)
    return _missing_compare_state_payload(resolved_path)


def build_demo_review_compare_state(
    demo_review_history_state: dict[str, Any],
    *,
    compare_state_path: Path | None,
    persisted: bool,
) -> dict[str, Any]:
    recent_events = [dict(item) for item in list(demo_review_history_state.get("recent_events") or [])]
    package_rows: dict[str, dict[str, Any]] = {}
    for event in recent_events:
        package_id = str(event.get("package_id") or "").strip()
        if not package_id:
            continue
        row = package_rows.setdefault(
            package_id,
            {
                "package_id": package_id,
                "event_count": 0,
                "replay_kinds": set(),
                "action_events": [],
                "animation_events": [],
                "latest_action_event": {},
                "latest_animation_event": {},
                "warning_flags": set(),
            },
        )
        row["event_count"] = int(row["event_count"]) + 1
        request_kind = str(event.get("request_kind") or "").strip()
        if request_kind:
            row["replay_kinds"].add(request_kind)
        warning_flags = list(dict(event.get("credibility_summary") or {}).get("warning_flags") or [])
        for warning_flag in warning_flags:
            if str(warning_flag).strip():
                row["warning_flags"].add(str(warning_flag))
        if request_kind == "action_preview" and not row["latest_action_event"]:
            row["latest_action_event"] = event
            row["action_events"].append(event)
        elif request_kind == "animation_preview" and not row["latest_animation_event"]:
            row["latest_animation_event"] = event
            row["animation_events"].append(event)
        elif request_kind == "action_preview":
            row["action_events"].append(event)
        elif request_kind == "animation_preview":
            row["animation_events"].append(event)

    package_compares: list[dict[str, Any]] = []
    for package_id in sorted(package_rows):
        row = package_rows[package_id]
        latest_action_event = dict(row["latest_action_event"] or {})
        latest_animation_event = dict(row["latest_animation_event"] or {})
        action_events = [dict(item) for item in list(row["action_events"] or [])]
        animation_events = [dict(item) for item in list(row["animation_events"] or [])]
        compare_pairs: list[dict[str, Any]] = []
        pair_count = max(len(action_events), len(animation_events))
        for pair_index in range(pair_count):
            action_event = dict(action_events[pair_index]) if pair_index < len(action_events) else {}
            animation_event = dict(animation_events[pair_index]) if pair_index < len(animation_events) else {}
            compare_pair_ready = bool(action_event and animation_event)
            pair_timestamps = [
                str(action_event.get("generated_at_utc") or ""),
                str(animation_event.get("generated_at_utc") or ""),
            ]
            pair_timestamps = [item for item in pair_timestamps if item]
            pair_warning_flags = sorted(
                {
                    str(flag)
                    for payload in (action_event, animation_event)
                    for flag in list(dict(payload.get("credibility_summary") or {}).get("warning_flags") or [])
                    if str(flag).strip()
                }
            )
            compare_pairs.append(
                {
                    "pair_index": pair_index,
                    "compare_ready": compare_pair_ready,
                    "status": "pass" if compare_pair_ready else "fail",
                    "pair_generated_at_utc": max(pair_timestamps) if pair_timestamps else "",
                    "action_event": action_event,
                    "animation_event": animation_event,
                    "warning_flags": pair_warning_flags,
                }
            )
        compare_ready = bool(latest_action_event and latest_animation_event)
        pair_timestamps = [
            str(latest_action_event.get("generated_at_utc") or ""),
            str(latest_animation_event.get("generated_at_utc") or ""),
        ]
        pair_timestamps = [item for item in pair_timestamps if item]
        package_compares.append(
            {
                "package_id": package_id,
                "event_count": int(row["event_count"]),
                "replay_kinds": sorted(str(item) for item in row["replay_kinds"] if str(item).strip()),
                "compare_ready": compare_ready,
                "status": "pass" if compare_ready else "fail",
                "latest_pair_generated_at_utc": max(pair_timestamps) if pair_timestamps else "",
                "latest_action_event": latest_action_event,
                "latest_animation_event": latest_animation_event,
                "warning_flags": sorted(str(item) for item in row["warning_flags"] if str(item).strip()),
                "compare_pairs": compare_pairs,
            }
        )

    payload = {
        "status": "pass" if package_compares else "missing",
        "session_id": str(demo_review_history_state.get("session_id") or ""),
        "generated_at_utc": now_utc(),
        "source_review_history_state_path": str(demo_review_history_state.get("history_state_path") or ""),
        "persisted": bool(persisted),
        "package_compares": package_compares,
        "errors": [str(item) for item in list(demo_review_history_state.get("errors") or [])],
    }
    return _normalize_compare_state_payload(payload, compare_state_path)


def build_demo_review_compare_focus(
    demo_review_compare_state: dict[str, Any],
    *,
    selected_package_id: str | None,
    selected_pair_index: int | None = None,
) -> dict[str, Any]:
    if not selected_package_id:
        return {
            "status": "missing",
            "selected_package_id": "",
            "compare_ready": False,
            "event_count": 0,
            "selected_pair_index": 0,
            "available_pair_count": 0,
            "replay_kinds": [],
            "latest_pair_generated_at_utc": "",
            "selected_compare_pair": {},
            "compare_pair_summaries": [],
            "latest_action_event": {},
            "latest_animation_event": {},
            "warning_flags": [],
        }
    package_compares = [dict(item) for item in list(demo_review_compare_state.get("package_compares") or [])]
    selected_compare = next(
        (item for item in package_compares if str(item.get("package_id") or "") == str(selected_package_id or "")),
        None,
    )
    if selected_compare is None:
        return {
            "status": "missing",
            "selected_package_id": str(selected_package_id or ""),
            "compare_ready": False,
            "event_count": 0,
            "selected_pair_index": 0,
            "available_pair_count": 0,
            "replay_kinds": [],
            "latest_pair_generated_at_utc": "",
            "selected_compare_pair": {},
            "compare_pair_summaries": [],
            "latest_action_event": {},
            "latest_animation_event": {},
            "warning_flags": [],
        }
    compare_pairs = [dict(item) for item in list(selected_compare.get("compare_pairs") or [])]
    available_pair_count = len(compare_pairs)
    resolved_pair_index = max(0, int(selected_pair_index or 0))
    if available_pair_count:
        resolved_pair_index = min(resolved_pair_index, available_pair_count - 1)
        selected_pair = dict(compare_pairs[resolved_pair_index])
    else:
        resolved_pair_index = 0
        selected_pair = {}
    pair_summaries = [
        {
            "pair_index": int(item.get("pair_index") or 0),
            "status": str(item.get("status") or ""),
            "compare_ready": bool(item.get("compare_ready")),
            "pair_generated_at_utc": str(item.get("pair_generated_at_utc") or ""),
            "warning_flags": [str(flag) for flag in list(item.get("warning_flags") or []) if str(flag).strip()],
            "action_event_id": str(dict(item.get("action_event") or {}).get("history_event_id") or ""),
            "animation_event_id": str(dict(item.get("animation_event") or {}).get("history_event_id") or ""),
        }
        for item in compare_pairs
    ]
    focus_action_event = dict(selected_pair.get("action_event") or selected_compare.get("latest_action_event") or {})
    focus_animation_event = dict(selected_pair.get("animation_event") or selected_compare.get("latest_animation_event") or {})
    focus_warning_flags = [str(item) for item in list(selected_pair.get("warning_flags") or selected_compare.get("warning_flags") or [])]
    compare_ready = bool(selected_pair.get("compare_ready")) if selected_pair else bool(selected_compare.get("compare_ready"))
    return {
        "status": "pass" if compare_ready else "attention",
        "selected_package_id": str(selected_package_id or ""),
        "compare_ready": compare_ready,
        "event_count": int(selected_compare.get("event_count") or 0),
        "selected_pair_index": resolved_pair_index,
        "available_pair_count": available_pair_count,
        "replay_kinds": [str(item) for item in list(selected_compare.get("replay_kinds") or [])],
        "latest_pair_generated_at_utc": str(selected_pair.get("pair_generated_at_utc") or selected_compare.get("latest_pair_generated_at_utc") or ""),
        "selected_compare_pair": selected_pair,
        "compare_pair_summaries": pair_summaries,
        "latest_action_event": focus_action_event,
        "latest_animation_event": focus_animation_event,
        "warning_flags": focus_warning_flags,
    }


def write_demo_review_compare_state(
    *,
    session_manifest_path: str | Path | None,
    demo_review_history_state: dict[str, Any],
) -> dict[str, Any]:
    resolved_path = compare_state_path_from_session_manifest(session_manifest_path)
    if resolved_path is None:
        raise RuntimeError("demo_review_compare_state_session_manifest_missing")
    payload = build_demo_review_compare_state(
        demo_review_history_state,
        compare_state_path=resolved_path,
        persisted=True,
    )
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(resolved_path, payload)
    return payload


def _missing_compare_state_payload(compare_state_path: Path | None) -> dict[str, Any]:
    return {
        "status": "missing",
        "compare_state_path": str(compare_state_path) if compare_state_path else "",
        "session_id": "",
        "generated_at_utc": "",
        "source_review_history_state_path": "",
        "persisted": False,
        "counts": {
            "package_count": 0,
            "passing_packages": 0,
            "packages_with_compare_pair": 0,
        },
        "package_compares": [],
        "errors": [],
    }


def _normalize_compare_state_payload(payload: dict[str, Any], compare_state_path: Path | None) -> dict[str, Any]:
    package_compares = [dict(item) for item in list(payload.get("package_compares") or [])]
    normalized_package_compares: list[dict[str, Any]] = []
    passing_packages = 0
    compare_pair_count = 0
    for item in package_compares:
        compare_ready = bool(item.get("compare_ready"))
        if compare_ready:
            passing_packages += 1
            compare_pair_count += 1
        normalized_package_compares.append(
            {
                "package_id": str(item.get("package_id") or ""),
                "event_count": int(item.get("event_count") or 0),
                "replay_kinds": [str(kind) for kind in list(item.get("replay_kinds") or []) if str(kind).strip()],
                "compare_ready": compare_ready,
                "status": str(item.get("status") or ("pass" if compare_ready else "fail")),
                "latest_pair_generated_at_utc": str(item.get("latest_pair_generated_at_utc") or ""),
                "latest_action_event": dict(item.get("latest_action_event") or {}),
                "latest_animation_event": dict(item.get("latest_animation_event") or {}),
                "warning_flags": [str(flag) for flag in list(item.get("warning_flags") or []) if str(flag).strip()],
                "compare_pairs": [
                    {
                        "pair_index": int(pair.get("pair_index") or 0),
                        "compare_ready": bool(pair.get("compare_ready")),
                        "status": str(pair.get("status") or ""),
                        "pair_generated_at_utc": str(pair.get("pair_generated_at_utc") or ""),
                        "action_event": dict(pair.get("action_event") or {}),
                        "animation_event": dict(pair.get("animation_event") or {}),
                        "warning_flags": [str(flag) for flag in list(pair.get("warning_flags") or []) if str(flag).strip()],
                    }
                    for pair in list(item.get("compare_pairs") or [])
                ],
            }
        )
    return {
        "status": str(payload.get("status") or ("pass" if normalized_package_compares else "missing")),
        "compare_state_path": str(compare_state_path) if compare_state_path else "",
        "session_id": str(payload.get("session_id") or ""),
        "generated_at_utc": str(payload.get("generated_at_utc") or ""),
        "source_review_history_state_path": str(payload.get("source_review_history_state_path") or ""),
        "persisted": bool(payload.get("persisted")),
        "counts": {
            "package_count": len(normalized_package_compares),
            "passing_packages": passing_packages,
            "packages_with_compare_pair": compare_pair_count,
        },
        "package_compares": normalized_package_compares,
        "errors": [str(item) for item in list(payload.get("errors") or [])],
    }
