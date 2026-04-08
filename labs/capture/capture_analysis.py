from __future__ import annotations

import hashlib
from pathlib import Path


def file_sha256(path: str | None) -> str | None:
    if not path:
        return None
    resolved = Path(path)
    if not resolved.exists() or not resolved.is_file():
        return None
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluate_capture_entry(entry: dict) -> dict:
    image_path = entry.get("image_path")
    resolved = Path(image_path) if image_path else None
    exists = bool(resolved and resolved.exists())
    size_bytes = resolved.stat().st_size if exists else 0
    capture_status = entry.get("capture_status")
    valid = exists and size_bytes > 0 and str(capture_status).startswith("captured")
    timing_bucket = capture_status if str(capture_status) in {
        "captured_before_report",
        "captured_after_report_before_exit",
        "captured_after_exit",
    } else None
    return {
        **entry,
        "exists": exists,
        "size_bytes": size_bytes,
        "sha256": file_sha256(image_path) if valid else None,
        "valid_capture": valid,
        "timing_bucket": timing_bucket,
        "late_capture": timing_bucket in {"captured_after_report_before_exit", "captured_after_exit"},
        "captured_before_report": timing_bucket == "captured_before_report",
        "captured_after_report_before_exit": timing_bucket == "captured_after_report_before_exit",
        "captured_after_exit": timing_bucket == "captured_after_exit",
        "motion_inconclusive": False,
    }


def annotate_motion_inconclusive(entries: list[dict]) -> list[dict]:
    idle_hash_by_package = {}
    for entry in entries:
        if entry.get("scenario") == "idle_2s" and entry.get("valid_capture"):
            idle_hash_by_package[entry.get("package_id")] = entry.get("sha256")
    for entry in entries:
        if entry.get("scenario") == "idle_2s":
            continue
        idle_hash = idle_hash_by_package.get(entry.get("package_id"))
        if idle_hash and idle_hash == entry.get("sha256") and entry.get("valid_capture"):
            entry["motion_inconclusive"] = True
    return entries
