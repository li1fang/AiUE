from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from aiue_core.schema_utils import write_json


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def repo_root_from_workspace(workspace: dict, repo_root_fallback: str | Path) -> Path:
    return Path(workspace["paths"].get("aiue_repo_root") or repo_root_fallback).expanduser().resolve()


def default_output_root(workspace: dict, repo_root_fallback: str | Path, gate_id: str) -> Path:
    return repo_root_from_workspace(workspace, repo_root_fallback) / "Saved" / "verification" / f"{gate_id}_{run_stamp()}"


def default_latest_report_path(workspace: dict, repo_root_fallback: str | Path, gate_id: str) -> Path:
    return repo_root_from_workspace(workspace, repo_root_fallback) / "Saved" / "verification" / f"latest_{gate_id}_report.json"


def verification_named_report_path(workspace: dict, repo_root_fallback: str | Path, report_name: str) -> Path:
    return repo_root_from_workspace(workspace, repo_root_fallback) / "Saved" / "verification" / report_name


def make_failed_requirement(requirement_id: str, message: str, **details) -> dict:
    payload = {"id": requirement_id, "message": message}
    payload.update(details)
    return payload


def build_discussion_signal(
    status: str,
    failed_requirements: list[dict],
    previous_report: dict | None,
    previous_report_path: Path | None,
    first_pass_reason: str,
) -> dict:
    current_failed_ids = sorted({item.get("id") for item in failed_requirements if item.get("id")})
    previous_failed_ids = sorted(
        {
            item.get("id")
            for item in ((previous_report or {}).get("failed_requirements") or [])
            if isinstance(item, dict) and item.get("id")
        }
    )
    previous_status = (previous_report or {}).get("status")
    payload = {
        "should_discuss": False,
        "reason": None,
        "previous_report_path": str(previous_report_path) if previous_report_path else None,
        "repeated_failed_requirement_ids": [],
    }
    if status == "pass" and previous_status != "pass":
        payload["should_discuss"] = True
        payload["reason"] = first_pass_reason
        return payload
    if status != "pass" and current_failed_ids and previous_status != "pass" and current_failed_ids == previous_failed_ids:
        payload["should_discuss"] = True
        payload["reason"] = "same_failed_requirement_two_rounds"
        payload["repeated_failed_requirement_ids"] = current_failed_ids
    return payload


def write_report_pair(report_payload: dict, report_path: Path, latest_report_path: Path) -> None:
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
