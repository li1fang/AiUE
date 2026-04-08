from __future__ import annotations


def capability_entries(capabilities_payload: dict, capability_id: str | None = None) -> list[dict]:
    entries = list((capabilities_payload or {}).get("capabilities") or [])
    if capability_id:
        entries = [entry for entry in entries if entry.get("capability_id") == capability_id]
    return entries


def capture_entries_by_mode(capabilities_payload: dict) -> dict[str, dict]:
    result = {}
    for entry in capability_entries(capabilities_payload, "capture_frame"):
        mode = entry.get("mode")
        if mode:
            result[mode] = entry
    return result
