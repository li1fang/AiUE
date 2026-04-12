from __future__ import annotations

from typing import Any


E2C_SHOWCASE_GATE_ID = "playable_demo_e2c_credible_showcase_polish"


def build_e2c_showcase_polish_summary(report_index: dict[str, Any]) -> dict[str, Any]:
    reports_by_gate_id = dict(report_index.get("reports_by_gate_id") or {})
    entry = dict(reports_by_gate_id.get(E2C_SHOWCASE_GATE_ID) or {})
    report_payload = dict(entry.get("report") or {})
    if not report_payload:
        return {
            "status": "missing",
            "gate_id": E2C_SHOWCASE_GATE_ID,
            "report_source_path": "",
            "counts": {},
            "packages": [],
        }

    counts = {
        str(key): int(value or 0)
        for key, value in dict(report_payload.get("counts") or {}).items()
        if str(key)
    }
    return {
        "status": str(report_payload.get("status") or entry.get("status") or "unknown"),
        "gate_id": E2C_SHOWCASE_GATE_ID,
        "report_source_path": str(entry.get("report_path") or ""),
        "counts": counts,
        "packages": [dict(item) for item in list(report_payload.get("per_package_results") or [])],
        "consumed_reports": dict(report_payload.get("consumed_reports") or {}),
        "polish_state_path": str(dict(report_payload.get("artifacts") or {}).get("polish_state_path") or ""),
    }
