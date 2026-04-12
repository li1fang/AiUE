from __future__ import annotations

from typing import Any


A1_CANDIDATE_PROVIDER_GATE_ID = "action_candidate_provider_a1"


def build_a1_candidate_provider_summary(report_index: dict[str, Any]) -> dict[str, Any]:
    reports_by_gate_id = dict(report_index.get("reports_by_gate_id") or {})
    entry = dict(reports_by_gate_id.get(A1_CANDIDATE_PROVIDER_GATE_ID) or {})
    report_payload = dict(entry.get("report") or {})
    if not report_payload:
        return {
            "status": "missing",
            "gate_id": A1_CANDIDATE_PROVIDER_GATE_ID,
            "report_source_path": "",
            "counts": {},
            "candidate_sources": [],
            "packages": [],
        }

    counts = {
        str(key): int(value or 0)
        for key, value in dict(report_payload.get("counts") or {}).items()
        if str(key)
    }
    return {
        "status": str(report_payload.get("status") or entry.get("status") or "unknown"),
        "gate_id": A1_CANDIDATE_PROVIDER_GATE_ID,
        "report_source_path": str(entry.get("report_path") or ""),
        "counts": counts,
        "candidate_sources": [dict(item) for item in list(report_payload.get("external_candidate_sources") or [])],
        "packages": [dict(item) for item in list(report_payload.get("per_package_results") or [])],
        "per_candidate_results": [dict(item) for item in list(report_payload.get("per_candidate_results") or [])],
        "artifacts": dict(report_payload.get("artifacts") or {}),
    }
