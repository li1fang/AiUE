from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiue_core.schema_utils import load_json, write_json


ROUND_STATE_FILENAME = "playable_demo_e2_round_state.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def round_state_path_from_session_manifest(session_manifest_path: str | Path | None) -> Path | None:
    if not session_manifest_path:
        return None
    resolved_session_path = Path(session_manifest_path).expanduser().resolve()
    return resolved_session_path.parent / ROUND_STATE_FILENAME


def load_demo_round_state(session_manifest_path: str | Path | None) -> dict[str, Any]:
    resolved_path = round_state_path_from_session_manifest(session_manifest_path)
    if resolved_path is None:
        return _missing_round_state_payload(None)
    if not resolved_path.exists():
        return _missing_round_state_payload(resolved_path)
    try:
        payload = load_json(resolved_path)
    except Exception as exc:
        return {
            **_missing_round_state_payload(resolved_path),
            "status": "error",
            "errors": [f"round_state_invalid_json:{exc}"],
        }
    return _normalize_round_state_payload(payload, resolved_path)


def write_demo_round_state(
    *,
    session_manifest_path: str | Path | None,
    session_id: str,
    operation: str,
    package_results: list[dict[str, Any]],
) -> dict[str, Any]:
    resolved_path = round_state_path_from_session_manifest(session_manifest_path)
    if resolved_path is None:
        raise RuntimeError("demo_round_state_session_manifest_missing")
    payload = {
        "status": "pass" if all(str(item.get("status") or "") == "pass" for item in package_results) else "error",
        "session_id": str(session_id or ""),
        "generated_at_utc": now_utc(),
        "operation": str(operation or ""),
        "package_results": package_results,
    }
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(resolved_path, payload)
    return _normalize_round_state_payload(payload, resolved_path)


def _missing_round_state_payload(round_state_path: Path | None) -> dict[str, Any]:
    return {
        "status": "missing",
        "round_state_path": str(round_state_path) if round_state_path else "",
        "session_id": "",
        "generated_at_utc": "",
        "operation": "",
        "counts": {},
        "package_ids": [],
        "package_results": [],
        "errors": [],
    }


def _normalize_round_state_payload(payload: dict[str, Any], round_state_path: Path) -> dict[str, Any]:
    package_results = [dict(item) for item in list(payload.get("package_results") or [])]
    counts = {
        "package_count": len(package_results),
        "passing_packages": sum(1 for item in package_results if str(item.get("status") or "") == "pass"),
        "invoke_count": len(package_results) * 2,
        "action_motion_verified": sum(
            1
            for item in package_results
            if bool(dict(dict(item.get("action_invoke") or {}).get("credibility_summary") or {}).get("action_motion_verified"))
        ),
        "animation_pose_verified": sum(
            1
            for item in package_results
            if bool(dict(dict(item.get("animation_invoke") or {}).get("credibility_summary") or {}).get("animation_pose_verified"))
        ),
    }
    return {
        "status": str(payload.get("status") or ("pass" if counts["package_count"] else "missing")),
        "round_state_path": str(round_state_path),
        "session_id": str(payload.get("session_id") or ""),
        "generated_at_utc": str(payload.get("generated_at_utc") or ""),
        "operation": str(payload.get("operation") or ""),
        "counts": counts,
        "package_ids": [str(item.get("package_id") or "") for item in package_results],
        "package_results": package_results,
        "errors": [str(item) for item in list(payload.get("errors") or [])],
    }
