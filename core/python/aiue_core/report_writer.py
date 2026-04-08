from __future__ import annotations

from pathlib import Path

AIUE_TOOL_NAME = "AiUE"
AIUE_SCHEMA_VERSION = "0.1.0"
AIUE_RELEASE_CHANNEL = "alpha"


def make_compatibility_block(
    schema_family: str,
    legacy_fields: list[str] | None = None,
    notes: list[str] | None = None,
) -> dict:
    return {
        "channel": AIUE_RELEASE_CHANNEL,
        "schema_family": schema_family,
        "legacy_fields": list(legacy_fields or []),
        "notes": list(notes or []),
    }


def with_report_envelope(
    payload: dict,
    schema_family: str,
    workflow_pack: str = "core",
    *,
    tool_name: str = AIUE_TOOL_NAME,
    schema_version: str = AIUE_SCHEMA_VERSION,
    compatibility: dict | None = None,
) -> dict:
    body = dict(payload or {})
    generated_at_utc = body.get("generated_at_utc")
    envelope = {
        "schema_version": schema_version,
        "tool_name": tool_name,
        "workflow_pack": workflow_pack,
        "generated_at_utc": generated_at_utc,
        "compatibility": compatibility or make_compatibility_block(schema_family),
    }
    envelope.update(body)
    return envelope


def latest_capabilities_report_path(root_path):
    root = Path(root_path).expanduser().resolve()
    latest_marker = root / "latest_capabilities.json"
    if latest_marker.exists():
        return latest_marker
    if not root.exists():
        return None
    candidates = sorted(
        (item / "ue_capabilities.json" for item in root.iterdir() if item.is_dir() and (item / "ue_capabilities.json").exists()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None
