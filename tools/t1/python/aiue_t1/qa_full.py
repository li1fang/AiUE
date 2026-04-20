from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, write_json


GATE_ID = "qa_full_nightly"
SCHEMA_FAMILY = "aiue_qa_full_nightly_report"
EXIT_CODE_BY_STATUS = {
    "pass": 0,
    "attention": 1,
    "fail": 2,
    "error": 3,
}
TOKEN_PATTERN = re.compile(r"\$\{([^}]+)\}")
LANE_CLASS_VALUES = {
    "authoritative_hard",
    "quality_hard",
    "environment_or_contract",
    "soft_discovery",
    "expected_watchlist",
}


def now_utc() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_stamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def default_latest_report_path(repo_root: Path, gate_id: str = GATE_ID) -> Path:
    return repo_root / "Saved" / "verification" / f"latest_{gate_id}_report.json"


def _sanitize_gate_id(value: str, fallback: str = GATE_ID) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "").strip()).strip("_").lower()
    return cleaned or fallback


def _profile_gate_id(profile: dict[str, Any]) -> str:
    return _sanitize_gate_id(str(profile.get("gate_id") or profile.get("profile_id") or GATE_ID))


def _effective_gate_id(profile: dict[str, Any], lane_ids: list[str] | None) -> str:
    profile_gate_id = _profile_gate_id(profile)
    if lane_ids:
        return _sanitize_gate_id(str(profile.get("selected_lanes_gate_id") or f"{profile_gate_id}_selected"))
    return profile_gate_id


def _schema_family_for_gate(profile: dict[str, Any], gate_id: str) -> str:
    if str(profile.get("schema_family") or "").strip() and gate_id == _profile_gate_id(profile):
        return str(profile.get("schema_family") or "").strip()
    return f"aiue_{gate_id}_report"


def _count_total_attempts(lanes: list[dict[str, Any]]) -> int:
    total = 0
    for lane in lanes:
        if not bool(lane.get("enabled", True)):
            continue
        total += max(int(lane.get("rerun_count") or 1), 1)
    return total


def _render_progress_bar(completed: int, total: int, *, width: int = 28) -> str:
    safe_total = max(int(total), 1)
    safe_completed = max(0, min(int(completed), safe_total))
    filled = int(width * safe_completed / safe_total)
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


def _emit_progress(
    *,
    completed: int,
    total: int,
    lane_id: str,
    run_index: int,
    rerun_count: int,
    phase: str,
    status: str = "",
) -> None:
    percent = int((max(0, min(completed, max(total, 1))) * 100) / max(total, 1))
    bar = _render_progress_bar(completed, total)
    suffix = f" | {status}" if status else ""
    print(
        f"[qa-full] {bar} {completed}/{total} {percent:>3}%"
        f" | {phase}"
        f" | lane={lane_id}"
        f" | attempt={run_index}/{max(rerun_count, 1)}"
        f"{suffix}",
        flush=True,
    )


def _decode_output(blob: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk", "cp936"):
        try:
            return blob.decode(encoding)
        except UnicodeDecodeError:
            continue
    return blob.decode("utf-8", errors="replace")


def _load_profile(profile_path: Path) -> dict[str, Any]:
    payload = load_json(profile_path)
    if not isinstance(payload, dict):
        raise ValueError("qa_full_profile_invalid")
    workspace_refs = dict(payload.get("workspace_refs") or {})
    if not workspace_refs:
        raise ValueError("qa_full_workspace_refs_missing")

    lanes = []
    lane_registry = dict(payload.get("lane_registry") or {})
    lane_order = [str(item) for item in list(payload.get("lane_order") or []) if str(item)]
    if lane_registry:
        if not lane_order:
            lane_order = list(lane_registry.keys())
        for lane_id in lane_order:
            lane_payload = dict(lane_registry.get(lane_id) or {})
            if not lane_payload:
                raise ValueError(f"qa_full_lane_missing:{lane_id}")
            lane_payload["lane_id"] = lane_id
            lanes.append(lane_payload)
    else:
        lanes = [dict(item) for item in list(payload.get("lanes") or [])]
    if not lanes:
        raise ValueError("qa_full_lanes_missing")

    normalized_lanes = []
    for lane in lanes:
        lane_id = str(lane.get("lane_id") or "").strip()
        if not lane_id:
            raise ValueError("qa_full_lane_id_missing")
        severity = str(lane.get("severity") or "").strip().lower()
        if severity not in {"hard", "soft", "expected_soft"}:
            raise ValueError(f"qa_full_lane_severity_invalid:{lane_id}")
        mode = str(lane.get("mode") or "").strip().lower()
        if mode not in {"command", "snapshot"}:
            raise ValueError(f"qa_full_lane_mode_invalid:{lane_id}")
        lane_class = str(lane.get("lane_class") or "").strip().lower()
        if not lane_class:
            if severity == "expected_soft":
                lane_class = "expected_watchlist"
            elif severity == "soft":
                lane_class = "soft_discovery"
            elif str(lane.get("group") or "").strip().lower() == "quality":
                lane_class = "quality_hard"
            else:
                lane_class = "authoritative_hard"
        if lane_class not in LANE_CLASS_VALUES:
            raise ValueError(f"qa_full_lane_class_invalid:{lane_id}")
        normalized_lanes.append(
            {
                **lane,
                "lane_id": lane_id,
                "severity": severity,
                "mode": mode,
                "enabled": bool(lane.get("enabled", True)),
                "workspace_ref": str(lane.get("workspace_ref") or "").strip(),
                "group": str(lane.get("group") or "").strip(),
                "command": list(lane.get("command") or []),
                "prerequisite_lane_ids": [str(item) for item in list(lane.get("prerequisite_lane_ids") or []) if str(item)],
                "rerun_count": max(int(lane.get("rerun_count") or 1), 1),
                "signature_paths": [str(item) for item in list(lane.get("signature_paths") or []) if str(item)],
                "report_gate_id": str(lane.get("report_gate_id") or "").strip(),
                "latest_report_path": str(lane.get("latest_report_path") or "").strip(),
                "report_glob": str(lane.get("report_glob") or "").strip(),
                "notes": [str(item) for item in list(lane.get("notes") or []) if str(item)],
                "lane_class": lane_class,
                "requires_workspace_keys": [
                    str(item)
                    for item in list(lane.get("requires_workspace_keys") or [])
                    if str(item)
                ],
                "cascade_from_lane_ids": [
                    str(item)
                    for item in list(lane.get("cascade_from_lane_ids") or [])
                    if str(item)
                ],
                "authoritative_group": str(lane.get("authoritative_group") or "").strip(),
            }
        )

    return {
        **payload,
        "workspace_refs": workspace_refs,
        "lanes": normalized_lanes,
    }


def _resolve_workspace_refs(profile_path: Path, workspace_refs: dict[str, Any]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for key, raw_value in workspace_refs.items():
        text = str(raw_value or "").strip()
        if not text:
            continue
        path = Path(text).expanduser()
        if not path.is_absolute():
            path = (profile_path.parent / path).resolve()
        resolved[str(key)] = str(path.resolve())
    return resolved


def _load_workspace_payload_cached(
    workspace_cache: dict[str, dict[str, Any] | None],
    workspace_path: str,
) -> dict[str, Any] | None:
    if workspace_path in workspace_cache:
        return workspace_cache[workspace_path]
    candidate = Path(workspace_path).expanduser().resolve()
    if not candidate.exists():
        workspace_cache[workspace_path] = None
        return None
    try:
        payload = load_json(candidate)
    except Exception:
        workspace_cache[workspace_path] = None
        return None
    workspace_cache[workspace_path] = dict(payload or {})
    return workspace_cache[workspace_path]


def _workspace_missing_keys(
    workspace_payload: dict[str, Any] | None,
    required_keys: list[str],
) -> list[str]:
    if not required_keys:
        return []
    if workspace_payload is None:
        return list(required_keys)
    missing: list[str] = []
    for dotted_key in required_keys:
        cursor: Any = workspace_payload
        resolved = True
        for part in [item for item in dotted_key.split(".") if item]:
            if not isinstance(cursor, dict) or part not in cursor:
                resolved = False
                break
            cursor = cursor.get(part)
        if not resolved or cursor is None or cursor == "":
            missing.append(dotted_key)
    return missing


def _flatten_json_path(payload: Any, parts: list[str]) -> list[Any]:
    if not parts:
        return [payload]
    part = parts[0]
    remainder = parts[1:]
    if isinstance(payload, list):
        values: list[Any] = []
        for item in payload:
            values.extend(_flatten_json_path(item, parts))
        return values
    if isinstance(payload, dict):
        if part not in payload:
            return []
        return _flatten_json_path(payload.get(part), remainder)
    return []


def _derive_owner_distribution(report_payload: dict[str, Any]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for item in list(report_payload.get("per_package_results") or []):
        owner = ""
        if isinstance(item, dict):
            owner = str(item.get("owner") or "")
            if not owner:
                owner = str((dict(item.get("owner_routing") or {})).get("owner") or "")
        if owner:
            distribution[owner] = distribution.get(owner, 0) + 1
    return distribution


def _derive_package_ids(report_payload: dict[str, Any]) -> list[str]:
    package_ids: list[str] = []
    for value in list(report_payload.get("resolved_package_ids") or []):
        text = str(value or "")
        if text:
            package_ids.append(text)
    for item in list(report_payload.get("per_package_results") or []):
        text = str((dict(item or {})).get("package_id") or "")
        if text:
            package_ids.append(text)
    seen: set[str] = set()
    ordered: list[str] = []
    for item in package_ids:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def extract_signature(report_payload: dict[str, Any], signature_paths: list[str]) -> dict[str, Any]:
    signature: dict[str, Any] = {}
    for path_text in signature_paths:
        if path_text == "@owner_distribution":
            signature[path_text] = _derive_owner_distribution(report_payload)
            continue
        if path_text == "@package_ids":
            signature[path_text] = _derive_package_ids(report_payload)
            continue
        parts = [part for part in path_text.split(".") if part]
        values = _flatten_json_path(report_payload, parts)
        if len(values) == 1:
            signature[path_text] = values[0]
        else:
            signature[path_text] = values
    return signature


def _replace_tokens(text: str, context: dict[str, str]) -> str:
    def _resolve(match: re.Match[str]) -> str:
        token = str(match.group(1) or "")
        if token.startswith("workspace:"):
            return context.get(token, "")
        return context.get(token, "")

    return TOKEN_PATTERN.sub(_resolve, text)


def _resolve_command(command_spec: list[str], context: dict[str, str]) -> list[str]:
    return [_replace_tokens(str(item), context) for item in command_spec]


def _resolve_report_path(lane: dict[str, Any], verification_root: Path, context: dict[str, str]) -> Path | None:
    latest_report_path = str(lane.get("latest_report_path") or "")
    if latest_report_path:
        return Path(_replace_tokens(latest_report_path, context)).expanduser().resolve()
    report_gate_id = str(lane.get("report_gate_id") or "")
    if report_gate_id:
        return (verification_root / f"latest_{report_gate_id}_report.json").resolve()
    report_glob = str(lane.get("report_glob") or "")
    if report_glob:
        matches = sorted(verification_root.glob(report_glob))
        return matches[-1].resolve() if matches else None
    return None


def _build_lane_context(
    *,
    repo_root: Path,
    profile_path: Path,
    verification_root: Path,
    run_root: Path,
    lane_id: str,
    lane_output_root: Path,
    lane_stdout_path: Path,
    lane_stderr_path: Path,
    lane_latest_report_path: Path | None,
    workspace_refs: dict[str, str],
    selected_workspace: str,
) -> dict[str, str]:
    context = {
        "repo_root": str(repo_root.resolve()),
        "profile_dir": str(profile_path.parent.resolve()),
        "verification_root": str(verification_root.resolve()),
        "run_root": str(run_root.resolve()),
        "lane_id": lane_id,
        "lane_output_root": str(lane_output_root.resolve()),
        "lane_stdout_path": str(lane_stdout_path.resolve()),
        "lane_stderr_path": str(lane_stderr_path.resolve()),
        "lane_latest_report_path": str(lane_latest_report_path.resolve()) if lane_latest_report_path else "",
        "python": sys.executable,
        "workspace": selected_workspace,
    }
    for key, value in workspace_refs.items():
        context[f"workspace:{key}"] = str(value)
    return context


def _run_command_lane(
    *,
    repo_root: Path,
    lane: dict[str, Any],
    command: list[str],
    lane_output_root: Path,
    stdout_path: Path,
    stderr_path: Path,
    report_path: Path | None,
    run_index: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=str(repo_root),
        capture_output=True,
    )
    duration_seconds = round(float(time.perf_counter() - started), 3)
    stdout_text = _decode_output(completed.stdout)
    stderr_text = _decode_output(completed.stderr)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")

    report_payload: dict[str, Any] | None = None
    report_load_error = ""
    if report_path and report_path.exists():
        try:
            report_payload = load_json(report_path)
        except Exception as exc:
            report_load_error = str(exc)

    if completed.returncode != 0:
        status = "fail"
    elif report_load_error:
        status = "error"
    elif report_path is not None and report_payload is None:
        status = "fail"
    elif report_payload is not None:
        status = str(report_payload.get("status") or "unknown")
    else:
        status = "pass"

    signature = extract_signature(report_payload or {}, list(lane.get("signature_paths") or []))
    failed_requirement_ids = []
    if report_payload:
        for item in list(report_payload.get("failed_requirements") or []):
            requirement = dict(item or {})
            requirement_id = str(requirement.get("id") or "")
            if requirement_id:
                failed_requirement_ids.append(requirement_id)

    return {
        "lane_id": str(lane.get("lane_id") or ""),
        "status": status,
        "mode": "command",
        "severity": str(lane.get("severity") or ""),
        "group": str(lane.get("group") or ""),
        "command": command,
        "returncode": int(completed.returncode),
        "duration_seconds": duration_seconds,
        "run_index": int(run_index),
        "stdout_path": str(stdout_path.resolve()),
        "stderr_path": str(stderr_path.resolve()),
        "lane_output_root": str(lane_output_root.resolve()),
        "report_path": str(report_path.resolve()) if report_path else "",
        "report_status": str((report_payload or {}).get("status") or ""),
        "report_gate_id": str((report_payload or {}).get("gate_id") or lane.get("report_gate_id") or ""),
        "failed_requirement_ids": failed_requirement_ids,
        "report_load_error": report_load_error,
        "signature": signature,
        "report_payload": report_payload or {},
    }


def _run_snapshot_lane(
    *,
    lane: dict[str, Any],
    lane_output_root: Path,
    report_path: Path | None,
    run_index: int,
) -> dict[str, Any]:
    report_payload: dict[str, Any] | None = None
    report_load_error = ""
    if report_path and report_path.exists():
        try:
            report_payload = load_json(report_path)
        except Exception as exc:
            report_load_error = str(exc)
    if report_load_error:
        status = "error"
    elif report_payload is None:
        status = "blocked"
    else:
        status = str(report_payload.get("status") or "unknown")
    failed_requirement_ids = []
    if report_payload:
        for item in list(report_payload.get("failed_requirements") or []):
            requirement_id = str((dict(item or {})).get("id") or "")
            if requirement_id:
                failed_requirement_ids.append(requirement_id)
    return {
        "lane_id": str(lane.get("lane_id") or ""),
        "status": status,
        "mode": "snapshot",
        "severity": str(lane.get("severity") or ""),
        "group": str(lane.get("group") or ""),
        "command": [],
        "returncode": None,
        "duration_seconds": 0.0,
        "run_index": int(run_index),
        "stdout_path": "",
        "stderr_path": "",
        "lane_output_root": str(lane_output_root.resolve()),
        "report_path": str(report_path.resolve()) if report_path else "",
        "report_status": str((report_payload or {}).get("status") or ""),
        "report_gate_id": str((report_payload or {}).get("gate_id") or lane.get("report_gate_id") or ""),
        "failed_requirement_ids": failed_requirement_ids,
        "report_load_error": report_load_error,
        "signature": extract_signature(report_payload or {}, list(lane.get("signature_paths") or [])),
        "report_payload": report_payload or {},
    }


def _lane_expected_soft_reason(lane_result: dict[str, Any]) -> str:
    gate_id = str(lane_result.get("report_gate_id") or lane_result.get("lane_id") or "")
    status = str(lane_result.get("status") or "")
    report_payload = dict(lane_result.get("report_payload") or {})

    if gate_id == "manual_playable_demo_validation_pv1":
        if status in {"attention", "blocked", "missing"} and not bool(report_payload.get("success")):
            return "manual_signoff_pending"
        return ""

    if gate_id == "canonical_fusion_fixture_c2":
        if status != "pass":
            return "houdini_fixture_not_ready"
        return ""

    if gate_id == "test_governance_round1":
        checkpoint = dict(report_payload.get("checkpoint_readiness") or {})
        automation_missing = [
            str(item)
            for item in list(checkpoint.get("high_priority_automation_blind_spot_ids") or [])
            if str(item)
        ]
        signoff_missing = [
            str(item)
            for item in list(checkpoint.get("high_priority_signoff_blind_spot_ids") or [])
            if str(item)
        ]
        if not automation_missing and signoff_missing and set(signoff_missing).issubset({"manual_playable_demo_validation"}):
            return "manual_signoff_only_blind_spot"
        return ""

    if status == "blocked":
        return "expected_soft_blocked"
    return ""


def _compare_attempts(first_attempt: dict[str, Any], second_attempt: dict[str, Any]) -> dict[str, Any]:
    first_status = str(first_attempt.get("status") or "")
    second_status = str(second_attempt.get("status") or "")
    first_signature = dict(first_attempt.get("signature") or {})
    second_signature = dict(second_attempt.get("signature") or {})
    comparison = {
        "lane_id": str(first_attempt.get("lane_id") or ""),
        "first_status": first_status,
        "second_status": second_status,
        "first_signature": first_signature,
        "second_signature": second_signature,
        "comparison_status": "stable",
        "reason": "",
    }
    if first_status == "pass" and second_status != "pass":
        comparison["comparison_status"] = "flake_detected"
        comparison["reason"] = "first_pass_second_nonpass"
        return comparison
    if first_status == "pass" and second_status == "pass" and first_signature != second_signature:
        comparison["comparison_status"] = "output_drift"
        comparison["reason"] = "stable_signature_changed"
        return comparison
    return comparison


def _classify_failure_kind(
    *,
    lane: dict[str, Any],
    lane_entry: dict[str, Any],
    lane_status_by_id: dict[str, str],
) -> str:
    status = str(lane_entry.get("status") or "")
    if status == "pass":
        return "pass"
    if status == "blocked":
        blocked_reason = str(lane_entry.get("blocked_reason") or "")
        if blocked_reason == "prerequisite_not_pass":
            return "cascade_failure"
        if blocked_reason in {"workspace_keys_missing", "workspace_ref_missing"}:
            return "environment_failure"
    for source_lane_id in list(lane.get("cascade_from_lane_ids") or []):
        if str(lane_status_by_id.get(source_lane_id) or "") != "pass":
            return "cascade_failure"
    if str(lane.get("lane_class") or "") == "environment_or_contract":
        return "environment_failure"
    if str(lane.get("severity") or "") == "expected_soft":
        return "watchlist_only"
    return "root_failure"


def _repo_state(repo_root: Path, profile_path: Path) -> dict[str, Any]:
    def _git(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip()

    try:
        branch = _git("branch", "--show-current")
        head_commit = _git("rev-parse", "HEAD")
        status_short = _git("status", "--short")
    except Exception as exc:
        return {
            "repo_root": str(repo_root.resolve()),
            "profile_path": str(profile_path.resolve()),
            "git_error": str(exc),
        }
    return {
        "repo_root": str(repo_root.resolve()),
        "profile_path": str(profile_path.resolve()),
        "branch": branch,
        "head_commit": head_commit,
        "dirty": bool(status_short.strip()),
        "status_short": status_short,
    }


def _resolve_lane_subset(lanes: list[dict[str, Any]], lane_ids: list[str] | None) -> list[dict[str, Any]]:
    if not lane_ids:
        return [lane for lane in lanes if bool(lane.get("enabled", True))]
    requested = {str(item) for item in lane_ids if str(item)}
    return [lane for lane in lanes if bool(lane.get("enabled", True)) and str(lane.get("lane_id") or "") in requested]


def build_qa_full_report(
    *,
    repo_root: Path,
    profile_path: Path,
    output_root: Path | None = None,
    latest_report_path: Path | None = None,
    lane_ids: list[str] | None = None,
) -> tuple[dict[str, Any], Path, Path, int]:
    repo_root = Path(repo_root).expanduser().resolve()
    profile_path = Path(profile_path).expanduser().resolve()
    profile = _load_profile(profile_path)
    effective_lane_ids = [str(item) for item in list(lane_ids or []) if str(item)]
    profile_gate_id = _profile_gate_id(profile)
    gate_id = _effective_gate_id(profile, effective_lane_ids)
    schema_family = _schema_family_for_gate(profile, gate_id)
    workspace_refs = _resolve_workspace_refs(profile_path, dict(profile.get("workspace_refs") or {}))
    verification_root = repo_root / "Saved" / "verification"
    report_root = output_root or (verification_root / f"{gate_id}_{run_stamp()}")
    latest_report = latest_report_path or default_latest_report_path(repo_root, gate_id)
    report_root.mkdir(parents=True, exist_ok=True)
    latest_report.parent.mkdir(parents=True, exist_ok=True)

    selected_lanes = _resolve_lane_subset(list(profile.get("lanes") or []), effective_lane_ids)
    total_attempts = _count_total_attempts(selected_lanes)
    completed_attempts = 0
    attempts_by_lane: dict[str, list[dict[str, Any]]] = {}
    lane_status_by_id: dict[str, str] = {}
    runner_errors: list[str] = []
    workspace_cache: dict[str, dict[str, Any] | None] = {}

    for lane in selected_lanes:
        lane_id = str(lane.get("lane_id") or "")
        rerun_count = max(int(lane.get("rerun_count") or 1), 1)
        selected_workspace = workspace_refs.get(str(lane.get("workspace_ref") or ""), "")
        required_workspace_keys = list(lane.get("requires_workspace_keys") or [])

        if required_workspace_keys:
            if not selected_workspace:
                attempts_by_lane[lane_id] = []
                for run_index in range(1, rerun_count + 1):
                    blocked_attempt = {
                        "lane_id": lane_id,
                        "status": "blocked",
                        "mode": str(lane.get("mode") or ""),
                        "severity": str(lane.get("severity") or ""),
                        "lane_class": str(lane.get("lane_class") or ""),
                        "authoritative_group": str(lane.get("authoritative_group") or ""),
                        "group": str(lane.get("group") or ""),
                        "command": [],
                        "returncode": None,
                        "duration_seconds": 0.0,
                        "run_index": run_index,
                        "stdout_path": "",
                        "stderr_path": "",
                        "lane_output_root": str((report_root / "lanes" / lane_id).resolve()),
                        "report_path": "",
                        "report_status": "",
                        "report_gate_id": str(lane.get("report_gate_id") or ""),
                        "failed_requirement_ids": [],
                        "report_load_error": "",
                        "signature": {},
                        "report_payload": {},
                        "blocked_reason": "workspace_ref_missing",
                        "missing_workspace_keys": list(required_workspace_keys),
                    }
                    attempts_by_lane[lane_id].append(blocked_attempt)
                    completed_attempts += 1
                    _emit_progress(
                        completed=completed_attempts,
                        total=total_attempts,
                        lane_id=lane_id,
                        run_index=run_index,
                        rerun_count=rerun_count,
                        phase="blocked",
                        status="blocked",
                    )
                lane_status_by_id[lane_id] = "blocked"
                continue

            workspace_payload = _load_workspace_payload_cached(workspace_cache, selected_workspace)
            missing_workspace_keys = _workspace_missing_keys(workspace_payload, required_workspace_keys)
            if missing_workspace_keys:
                attempts_by_lane[lane_id] = []
                for run_index in range(1, rerun_count + 1):
                    blocked_attempt = {
                        "lane_id": lane_id,
                        "status": "blocked",
                        "mode": str(lane.get("mode") or ""),
                        "severity": str(lane.get("severity") or ""),
                        "lane_class": str(lane.get("lane_class") or ""),
                        "authoritative_group": str(lane.get("authoritative_group") or ""),
                        "group": str(lane.get("group") or ""),
                        "command": [],
                        "returncode": None,
                        "duration_seconds": 0.0,
                        "run_index": run_index,
                        "stdout_path": "",
                        "stderr_path": "",
                        "lane_output_root": str((report_root / "lanes" / lane_id).resolve()),
                        "report_path": "",
                        "report_status": "",
                        "report_gate_id": str(lane.get("report_gate_id") or ""),
                        "failed_requirement_ids": [],
                        "report_load_error": "",
                        "signature": {},
                        "report_payload": {},
                        "blocked_reason": "workspace_keys_missing",
                        "missing_workspace_keys": list(missing_workspace_keys),
                        "selected_workspace": selected_workspace,
                    }
                    attempts_by_lane[lane_id].append(blocked_attempt)
                    completed_attempts += 1
                    _emit_progress(
                        completed=completed_attempts,
                        total=total_attempts,
                        lane_id=lane_id,
                        run_index=run_index,
                        rerun_count=rerun_count,
                        phase="blocked",
                        status="blocked",
                    )
                lane_status_by_id[lane_id] = "blocked"
                continue

        prerequisites = [lane_status_by_id.get(item, "missing") for item in list(lane.get("prerequisite_lane_ids") or [])]
        if prerequisites and any(status != "pass" for status in prerequisites):
            attempts_by_lane[lane_id] = []
            for run_index in range(1, rerun_count + 1):
                blocked_attempt = {
                    "lane_id": lane_id,
                    "status": "blocked",
                    "mode": str(lane.get("mode") or ""),
                    "severity": str(lane.get("severity") or ""),
                    "lane_class": str(lane.get("lane_class") or ""),
                    "authoritative_group": str(lane.get("authoritative_group") or ""),
                    "group": str(lane.get("group") or ""),
                    "command": [],
                    "returncode": None,
                    "duration_seconds": 0.0,
                    "run_index": run_index,
                    "stdout_path": "",
                    "stderr_path": "",
                    "lane_output_root": str((report_root / "lanes" / lane_id).resolve()),
                    "report_path": "",
                    "report_status": "",
                    "report_gate_id": str(lane.get("report_gate_id") or ""),
                    "failed_requirement_ids": [],
                    "report_load_error": "",
                    "signature": {},
                    "report_payload": {},
                    "blocked_reason": "prerequisite_not_pass",
                    "blocked_prerequisite_lane_ids": list(lane.get("prerequisite_lane_ids") or []),
                }
                attempts_by_lane[lane_id].append(blocked_attempt)
                completed_attempts += 1
                _emit_progress(
                    completed=completed_attempts,
                    total=total_attempts,
                    lane_id=lane_id,
                    run_index=run_index,
                    rerun_count=rerun_count,
                    phase="blocked",
                    status="blocked",
                )
            lane_status_by_id[lane_id] = "blocked"
            continue

        lane_attempts: list[dict[str, Any]] = []
        for run_index in range(1, rerun_count + 1):
            _emit_progress(
                completed=completed_attempts,
                total=total_attempts,
                lane_id=lane_id,
                run_index=run_index,
                rerun_count=rerun_count,
                phase="running",
            )
            attempt_suffix = "" if run_index == 1 else f"_rerun{run_index}"
            lane_output_root = report_root / "lanes" / lane_id / f"attempt_{run_index}"
            lane_output_root.mkdir(parents=True, exist_ok=True)
            stdout_path = lane_output_root / f"{lane_id}{attempt_suffix}.stdout.txt"
            stderr_path = lane_output_root / f"{lane_id}{attempt_suffix}.stderr.txt"
            lane_context = _build_lane_context(
                repo_root=repo_root,
                profile_path=profile_path,
                verification_root=verification_root,
                run_root=report_root,
                lane_id=lane_id,
                lane_output_root=lane_output_root,
                lane_stdout_path=stdout_path,
                lane_stderr_path=stderr_path,
                lane_latest_report_path=None,
                workspace_refs=workspace_refs,
                selected_workspace=selected_workspace,
            )
            report_path = _resolve_report_path(lane, verification_root, lane_context)
            lane_context = _build_lane_context(
                repo_root=repo_root,
                profile_path=profile_path,
                verification_root=verification_root,
                run_root=report_root,
                lane_id=lane_id,
                lane_output_root=lane_output_root,
                lane_stdout_path=stdout_path,
                lane_stderr_path=stderr_path,
                lane_latest_report_path=report_path,
                workspace_refs=workspace_refs,
                selected_workspace=selected_workspace,
            )
            try:
                if str(lane.get("mode") or "") == "snapshot":
                    lane_attempt = _run_snapshot_lane(
                        lane=lane,
                        lane_output_root=lane_output_root,
                        report_path=report_path,
                        run_index=run_index,
                    )
                else:
                    command = _resolve_command(list(lane.get("command") or []), lane_context)
                    lane_attempt = _run_command_lane(
                        repo_root=repo_root,
                        lane=lane,
                        command=command,
                        lane_output_root=lane_output_root,
                        stdout_path=stdout_path,
                        stderr_path=stderr_path,
                        report_path=report_path,
                        run_index=run_index,
                    )
            except Exception as exc:
                runner_errors.append(f"{lane_id}: {exc}")
                lane_attempt = {
                    "lane_id": lane_id,
                    "status": "error",
                    "mode": str(lane.get("mode") or ""),
                    "severity": str(lane.get("severity") or ""),
                    "group": str(lane.get("group") or ""),
                    "command": _resolve_command(list(lane.get("command") or []), lane_context) if str(lane.get("mode") or "") == "command" else [],
                    "returncode": None,
                    "duration_seconds": 0.0,
                    "run_index": run_index,
                    "stdout_path": str(stdout_path.resolve()) if stdout_path else "",
                    "stderr_path": str(stderr_path.resolve()) if stderr_path else "",
                    "lane_output_root": str(lane_output_root.resolve()),
                    "report_path": str(report_path.resolve()) if report_path else "",
                    "report_status": "",
                    "report_gate_id": str(lane.get("report_gate_id") or ""),
                    "failed_requirement_ids": [],
                    "report_load_error": str(exc),
                    "signature": {},
                    "report_payload": {},
                }
            lane_attempts.append(lane_attempt)
            completed_attempts += 1
            _emit_progress(
                completed=completed_attempts,
                total=total_attempts,
                lane_id=lane_id,
                run_index=run_index,
                rerun_count=rerun_count,
                phase="done",
                status=str(lane_attempt.get("status") or ""),
            )
        attempts_by_lane[lane_id] = lane_attempts
        lane_status_by_id[lane_id] = str((lane_attempts[0] if lane_attempts else {}).get("status") or "error")

    lane_results: list[dict[str, Any]] = []
    hard_failures: list[dict[str, Any]] = []
    soft_findings: list[dict[str, Any]] = []
    expected_watchlist: list[dict[str, Any]] = []
    blocked_lanes: list[dict[str, Any]] = []
    rerun_comparisons: list[dict[str, Any]] = []
    root_failures: list[dict[str, Any]] = []
    cascade_failures: list[dict[str, Any]] = []
    environment_failures: list[dict[str, Any]] = []

    for lane in selected_lanes:
        lane_id = str(lane.get("lane_id") or "")
        attempts = list(attempts_by_lane.get(lane_id) or [])
        first_attempt = dict(attempts[0] if attempts else {})
        failure_kind = _classify_failure_kind(
            lane=lane,
            lane_entry=first_attempt,
            lane_status_by_id=lane_status_by_id,
        )
        lane_entry = {
            "lane_id": lane_id,
            "severity": str(lane.get("severity") or ""),
            "lane_class": str(lane.get("lane_class") or ""),
            "authoritative_group": str(lane.get("authoritative_group") or ""),
            "mode": str(lane.get("mode") or ""),
            "group": str(lane.get("group") or ""),
            "workspace_ref": str(lane.get("workspace_ref") or ""),
            "status": str(first_attempt.get("status") or "error"),
            "report_gate_id": str(first_attempt.get("report_gate_id") or lane.get("report_gate_id") or ""),
            "report_path": str(first_attempt.get("report_path") or ""),
            "report_status": str(first_attempt.get("report_status") or ""),
            "failed_requirement_ids": list(first_attempt.get("failed_requirement_ids") or []),
            "blocked_reason": str(first_attempt.get("blocked_reason") or ""),
            "failure_kind": failure_kind,
            "requires_workspace_keys": list(lane.get("requires_workspace_keys") or []),
            "missing_workspace_keys": list(first_attempt.get("missing_workspace_keys") or []),
            "cascade_from_lane_ids": list(lane.get("cascade_from_lane_ids") or []),
            "attempts": attempts,
        }
        lane_results.append(lane_entry)
        if lane_entry["status"] == "blocked":
            blocked_lanes.append(
                {
                    "lane_id": lane_id,
                    "severity": lane_entry["severity"],
                    "lane_class": lane_entry["lane_class"],
                    "group": lane_entry["group"],
                    "reason": lane_entry["blocked_reason"] or "blocked",
                    "failure_kind": failure_kind,
                    "missing_workspace_keys": list(lane_entry["missing_workspace_keys"] or []),
                }
            )

        if len(attempts) >= 2:
            comparison = _compare_attempts(dict(attempts[0]), dict(attempts[1]))
            rerun_comparisons.append(comparison)
            if str(comparison.get("comparison_status") or "") in {"flake_detected", "output_drift"}:
                soft_findings.append(
                    {
                        "lane_id": lane_id,
                        "severity": "soft",
                        "status": str(comparison.get("comparison_status") or ""),
                        "reason": str(comparison.get("reason") or ""),
                    }
                )

        severity = str(lane.get("severity") or "")
        status = lane_entry["status"]
        classified_entry = {
            "lane_id": lane_id,
            "severity": severity,
            "lane_class": lane_entry["lane_class"],
            "authoritative_group": lane_entry["authoritative_group"],
            "group": lane_entry["group"],
            "status": status,
            "report_gate_id": lane_entry["report_gate_id"],
            "failed_requirement_ids": list(lane_entry["failed_requirement_ids"]),
            "blocked_reason": lane_entry["blocked_reason"],
            "missing_workspace_keys": list(lane_entry["missing_workspace_keys"]),
            "cascade_from_lane_ids": list(lane_entry["cascade_from_lane_ids"]),
        }
        if failure_kind == "root_failure":
            root_failures.append(dict(classified_entry))
        elif failure_kind == "cascade_failure":
            cascade_failures.append(dict(classified_entry))
        elif failure_kind == "environment_failure":
            environment_failures.append(dict(classified_entry))

        if severity == "hard":
            if status != "pass":
                hard_failures.append(
                    {
                        "lane_id": lane_id,
                        "group": lane_entry["group"],
                        "lane_class": lane_entry["lane_class"],
                        "status": status,
                        "report_gate_id": lane_entry["report_gate_id"],
                        "failed_requirement_ids": list(lane_entry["failed_requirement_ids"]),
                        "failure_kind": failure_kind,
                        "missing_workspace_keys": list(lane_entry["missing_workspace_keys"]),
                    }
                )
            continue

        if status == "pass":
            continue

        if severity == "expected_soft":
            expected_reason = _lane_expected_soft_reason(first_attempt)
            target = expected_watchlist if expected_reason else soft_findings
            target.append(
                {
                    "lane_id": lane_id,
                    "severity": severity,
                    "status": status,
                    "report_gate_id": lane_entry["report_gate_id"],
                    "lane_class": lane_entry["lane_class"],
                    "failure_kind": failure_kind,
                    "reason": expected_reason or "unexpected_expected_soft_failure",
                    "failed_requirement_ids": list(lane_entry["failed_requirement_ids"]),
                }
            )
            continue

        soft_findings.append(
            {
                "lane_id": lane_id,
                "severity": severity,
                "status": status,
                "report_gate_id": lane_entry["report_gate_id"],
                "lane_class": lane_entry["lane_class"],
                "failure_kind": failure_kind,
                "failed_requirement_ids": list(lane_entry["failed_requirement_ids"]),
            }
        )

    if runner_errors:
        status = "error"
    elif hard_failures:
        status = "fail"
    elif soft_findings:
        status = "attention"
    else:
        status = "pass"

    payload = with_report_envelope(
        {
            "gate_id": gate_id,
            "status": status,
            "generated_at_utc": now_utc(),
            "profile_id": str(profile.get("profile_id") or ""),
            "profile_gate_id": profile_gate_id,
            "effective_gate_id": gate_id,
            "run_scope": "selected_lanes" if effective_lane_ids else "full_profile",
            "is_lane_subset": bool(effective_lane_ids),
            "selected_lane_ids": list(effective_lane_ids),
            "runtime_budget_class": str(profile.get("runtime_budget_class") or "nightly_6h_plus"),
            "workspace_refs": workspace_refs,
            "repo_state": _repo_state(repo_root, profile_path),
            "lane_results": lane_results,
            "hard_failures": hard_failures,
            "root_failures": root_failures,
            "cascade_failures": cascade_failures,
            "environment_failures": environment_failures,
            "soft_findings": soft_findings,
            "expected_watchlist": expected_watchlist,
            "watchlist_only": {
                "status": bool(expected_watchlist and not hard_failures and not soft_findings and not runner_errors),
                "lane_ids": [str(item.get("lane_id") or "") for item in expected_watchlist if str(item.get("lane_id") or "")],
            },
            "blocked_lanes": blocked_lanes,
            "rerun_comparisons": rerun_comparisons,
            "artifacts": {
                "profile_path": str(profile_path.resolve()),
                "report_root": str(report_root.resolve()),
                "report_path": str((report_root / f"{gate_id}_report.json").resolve()),
                "latest_report_path": str(latest_report.resolve()),
            },
            "discussion_signal": {
                "reason": (
                    "hard_lane_failed"
                    if hard_failures
                    else "unexpected_soft_findings"
                    if soft_findings
                    else "expected_watchlist_only"
                    if expected_watchlist
                    else "qa_full_green"
                ),
                "should_discuss": bool(hard_failures or soft_findings),
            },
            "runner_errors": runner_errors,
            "policy": {
                "hard_fail_fails_total": True,
                "unexpected_soft_raises_attention": True,
                "expected_watchlist_does_not_raise_total": True,
                "sequential_ue_lanes": True,
            },
        },
        schema_family=schema_family,
        workflow_pack="tooling",
        compatibility=make_compatibility_block(
            schema_family,
            notes=[
                "profile-driven QA orchestration for mainline plus motion plus body handoff",
                "hard, soft, and expected-soft lanes are aggregated without stopping at the first failure",
                "selected lane subsets write to a separate gate id so they do not overwrite full-profile latest reports",
            ],
        ),
    )
    report_path = report_root / f"{gate_id}_report.json"
    return payload, report_path, latest_report, EXIT_CODE_BY_STATUS.get(status, 3)


def write_qa_full_report(
    *,
    repo_root: Path,
    profile_path: Path,
    output_root: Path | None = None,
    latest_report_path: Path | None = None,
    lane_ids: list[str] | None = None,
) -> tuple[dict[str, Any], Path, Path, int]:
    payload, report_path, latest_report, exit_code = build_qa_full_report(
        repo_root=repo_root,
        profile_path=profile_path,
        output_root=output_root,
        latest_report_path=latest_report_path,
        lane_ids=lane_ids,
    )
    write_json(report_path, payload)
    write_json(latest_report, payload)
    return payload, report_path, latest_report, exit_code


def build_qa_full_summary(report_index: dict[str, Any], gate_id: str = GATE_ID) -> dict[str, Any]:
    record = dict((dict(report_index.get("reports_by_gate_id") or {}).get(gate_id) or {}))
    report = dict(record.get("report") or {})
    if not report:
        return {
            "gate_id": gate_id,
            "status": "missing",
            "hard_failure_count": 0,
            "root_failure_count": 0,
            "cascade_failure_count": 0,
            "environment_failure_count": 0,
            "soft_finding_count": 0,
            "expected_watchlist_count": 0,
            "blocked_lane_count": 0,
            "flake_count": 0,
            "output_drift_count": 0,
            "watchlist_only": False,
            "root_failure_lane_ids": [],
            "cascade_failure_lane_ids": [],
            "environment_failure_lane_ids": [],
            "report_source_path": "",
        }
    rerun_comparisons = [dict(item) for item in list(report.get("rerun_comparisons") or [])]
    flake_count = sum(1 for item in rerun_comparisons if str(item.get("comparison_status") or "") == "flake_detected")
    output_drift_count = sum(1 for item in rerun_comparisons if str(item.get("comparison_status") or "") == "output_drift")
    root_failures = [dict(item) for item in list(report.get("root_failures") or [])]
    cascade_failures = [dict(item) for item in list(report.get("cascade_failures") or [])]
    environment_failures = [dict(item) for item in list(report.get("environment_failures") or [])]
    watchlist_only = dict(report.get("watchlist_only") or {})
    return {
        "gate_id": gate_id,
        "status": str(report.get("status") or "unknown"),
        "hard_failure_count": len(list(report.get("hard_failures") or [])),
        "root_failure_count": len(root_failures),
        "cascade_failure_count": len(cascade_failures),
        "environment_failure_count": len(environment_failures),
        "soft_finding_count": len(list(report.get("soft_findings") or [])),
        "expected_watchlist_count": len(list(report.get("expected_watchlist") or [])),
        "blocked_lane_count": len(list(report.get("blocked_lanes") or [])),
        "flake_count": flake_count,
        "output_drift_count": output_drift_count,
        "watchlist_only": bool(watchlist_only.get("status")),
        "root_failure_lane_ids": [
            str(item.get("lane_id") or "")
            for item in root_failures
            if str(item.get("lane_id") or "")
        ],
        "cascade_failure_lane_ids": [
            str(item.get("lane_id") or "")
            for item in cascade_failures
            if str(item.get("lane_id") or "")
        ],
        "environment_failure_lane_ids": [
            str(item.get("lane_id") or "")
            for item in environment_failures
            if str(item.get("lane_id") or "")
        ],
        "report_source_path": str(record.get("report_path") or ""),
        "discussion_reason": str((dict(report.get("discussion_signal") or {})).get("reason") or ""),
        "runtime_budget_class": str(report.get("runtime_budget_class") or ""),
    }
