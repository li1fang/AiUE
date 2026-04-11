from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiue_core.schema_utils import load_json, write_json

from aiue_t1.report_index import ACTIVE_LINE_GATE_IDS, PLATFORM_LINE_GATE_IDS, build_report_index


GATE_ID = "dynamic_balance_governance_progress"
SCHEMA_FAMILY = "aiue_dynamic_balance_report"
CHECKPOINT_KEYWORDS = ("governance", "stabilization", "cleanup", "hardening", "archive")
FIRST_PARTY_SCAN_ROOTS = [
    "adapters/unreal/host_project/runtime",
    "workflows/pmx_pipeline",
    "tools/t1/python/aiue_t1",
    "tools/t2/python/aiue_t2",
    "adapters/unreal/python/aiue_unreal",
    "core/python",
]
EXCLUDED_TOP_LEVEL_DIRS = {"deps", "Saved", "local", "legacy", "tests", "docs", ".venv-tooling"}
DEFAULT_POLICY = {
    "enforcement_level": "soft_signal",
    "round_definition": "checkpoint_round",
    "recent_round_window": 6,
    "hotspot_touch_window": 3,
    "large_first_party_file_threshold_lines": 900,
    "critical_first_party_file_threshold_lines": 1800,
    "consecutive_governance_only_rounds_for_progress_pressure": 2,
    "consecutive_hotspot_touches_for_governance_pressure": 3,
    "recommendation_priority": ["stabilization", "governance", "progress", "flexible"],
    "first_party_scan_roots": list(FIRST_PARTY_SCAN_ROOTS),
    "excluded_top_level_dirs": sorted(EXCLUDED_TOP_LEVEL_DIRS),
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def classify_round_kind(subject: str, checkpoint_paths: list[str]) -> str:
    normalized_subject = str(subject or "").strip().lower()
    checkpoint_names = [Path(path).name.lower() for path in checkpoint_paths]
    governance_signal = normalized_subject.startswith("refactor(") or normalized_subject.startswith("chore(")
    governance_signal = governance_signal or any(
        any(keyword in checkpoint_name for keyword in CHECKPOINT_KEYWORDS) for checkpoint_name in checkpoint_names
    )
    progress_signal = normalized_subject.startswith("feat(")
    if governance_signal and progress_signal:
        return "mixed"
    if governance_signal:
        return "governance"
    if progress_signal or normalized_subject:
        return "progress"
    return "unknown"


def parse_checkpoint_commit_records(raw_output: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for chunk in raw_output.split("\x1e"):
        chunk = chunk.strip()
        if not chunk:
            continue
        lines = [line.rstrip() for line in chunk.splitlines()]
        if not lines:
            continue
        header = lines[0].split("\x1f", 1)
        commit_hash = header[0].strip()
        subject = header[1].strip() if len(header) > 1 else ""
        checkpoint_paths = [line.strip() for line in lines[1:] if line.strip()]
        records.append(
            {
                "commit_hash": commit_hash,
                "subject": subject,
                "checkpoint_paths": checkpoint_paths,
            }
        )
    return records


def build_recent_rounds_from_commit_records(
    commit_records: list[dict[str, Any]],
    *,
    recent_round_window: int,
    changed_paths_by_commit: dict[str, list[str]] | None = None,
    hotspot_paths: set[str] | None = None,
) -> list[dict[str, Any]]:
    rounds: list[dict[str, Any]] = []
    hotspot_paths = hotspot_paths or set()
    changed_paths_by_commit = changed_paths_by_commit or {}
    for index, record in enumerate(commit_records[:recent_round_window]):
        commit_hash = str(record.get("commit_hash") or "")
        checkpoint_paths = [str(item) for item in list(record.get("checkpoint_paths") or [])]
        changed_paths = [str(item) for item in list(changed_paths_by_commit.get(commit_hash) or record.get("changed_paths") or [])]
        touched_hotspots = [path for path in changed_paths if path in hotspot_paths]
        round_kind = classify_round_kind(str(record.get("subject") or ""), checkpoint_paths)
        rounds.append(
            {
                "round_index": index + 1,
                "commit_hash": commit_hash,
                "subject": str(record.get("subject") or ""),
                "checkpoint_paths": checkpoint_paths,
                "changed_paths": changed_paths,
                "round_kind": round_kind,
                "signals": {
                    "governance": round_kind in {"governance", "mixed"},
                    "progress": round_kind in {"progress", "mixed"},
                },
                "touched_hotspot_paths": touched_hotspots,
            }
        )
    return rounds


def scan_first_party_hotspots(
    repo_root: Path,
    *,
    scan_roots: list[str] | None = None,
    excluded_top_level_dirs: set[str] | None = None,
    large_threshold: int = 900,
    critical_threshold: int = 1800,
) -> list[dict[str, Any]]:
    repo_root = Path(repo_root).expanduser().resolve()
    scan_roots = scan_roots or list(FIRST_PARTY_SCAN_ROOTS)
    excluded_top_level_dirs = excluded_top_level_dirs or set(EXCLUDED_TOP_LEVEL_DIRS)
    hotspots: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for relative_root in scan_roots:
        base_root = (repo_root / relative_root).resolve()
        if not base_root.exists():
            continue
        for path in base_root.rglob("*.py"):
            relative_path = path.relative_to(repo_root).as_posix()
            if relative_path in seen_paths:
                continue
            seen_paths.add(relative_path)
            if path.parts and path.parts[0] in excluded_top_level_dirs:
                continue
            try:
                line_count = path.read_text(encoding="utf-8").count("\n") + 1
            except UnicodeDecodeError:
                line_count = path.read_text(encoding="utf-8-sig").count("\n") + 1
            severity = ""
            if line_count >= critical_threshold:
                severity = "critical"
            elif line_count >= large_threshold:
                severity = "large"
            if not severity:
                continue
            hotspots.append(
                {
                    "path": str(path),
                    "relative_path": relative_path,
                    "line_count": line_count,
                    "severity": severity,
                }
            )
    hotspots.sort(key=lambda item: (-int(item["line_count"]), str(item["relative_path"])))
    return hotspots


def build_line_health(report_index: dict[str, Any]) -> dict[str, Any]:
    reports_by_gate_id = dict(report_index.get("reports_by_gate_id") or {})

    def _line_snapshot(expected_gate_ids: list[str], line_name: str) -> dict[str, Any]:
        observed = {gate_id: dict(reports_by_gate_id.get(gate_id) or {}) for gate_id in expected_gate_ids if gate_id in reports_by_gate_id}
        missing_gate_ids = [gate_id for gate_id in expected_gate_ids if gate_id not in observed]
        non_pass_gate_ids = [gate_id for gate_id, entry in observed.items() if str(entry.get("status") or "") != "pass"]
        return {
            "line_name": line_name,
            "expected_gate_ids": list(expected_gate_ids),
            "observed_gate_ids": list(observed.keys()),
            "missing_gate_ids": missing_gate_ids,
            "non_pass_gate_ids": non_pass_gate_ids,
            "passing_gate_count": sum(1 for entry in observed.values() if str(entry.get("status") or "") == "pass"),
            "healthy": not missing_gate_ids and not non_pass_gate_ids,
        }

    active_line = _line_snapshot(ACTIVE_LINE_GATE_IDS, "active_line")
    platform_line = _line_snapshot(PLATFORM_LINE_GATE_IDS, "platform_line")
    return {
        "active_line": active_line,
        "platform_line": platform_line,
        "all_required_latest_green": bool(active_line["healthy"] and platform_line["healthy"]),
    }


def build_ledgers(recent_rounds: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"progress": 0, "governance": 0, "mixed": 0, "unknown": 0}
    streak_kind = None
    streak_length = 0
    governance_only_streak = 0
    for round_payload in recent_rounds:
        round_kind = str(round_payload.get("round_kind") or "unknown")
        counts[round_kind] = counts.get(round_kind, 0) + 1
        if round_kind == streak_kind:
            streak_length += 1
        else:
            streak_kind = round_kind
            streak_length = 1
        if round_kind == "governance":
            governance_only_streak += 1
        else:
            break
    return {
        "counts": counts,
        "recent_round_kinds": [str(item.get("round_kind") or "unknown") for item in recent_rounds],
        "head_round_kind": str(recent_rounds[0].get("round_kind") or "unknown") if recent_rounds else "unknown",
        "head_round_streak_kind": streak_kind or "unknown",
        "head_round_streak_length": streak_length,
        "governance_only_head_streak": governance_only_streak,
    }


def _hotspot_touch_sequences(
    recent_rounds: list[dict[str, Any]],
    hotspot_paths: set[str],
    *,
    hotspot_touch_window: int,
    consecutive_hotspot_touches_for_governance_pressure: int,
) -> dict[str, Any]:
    matching_paths: list[str] = []
    critical_matching_paths: list[str] = []
    recent_window = recent_rounds[:hotspot_touch_window]
    for hotspot_path in sorted(hotspot_paths):
        touches = [hotspot_path in list(round_payload.get("touched_hotspot_paths") or []) for round_payload in recent_window]
        max_streak = 0
        current_streak = 0
        for touched in touches:
            if touched:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        if max_streak >= consecutive_hotspot_touches_for_governance_pressure:
            matching_paths.append(hotspot_path)
    return {
        "high_touch_hotspot_paths": matching_paths,
        "recent_window_size": len(recent_window),
        "touch_window": hotspot_touch_window,
        "required_consecutive_touches": consecutive_hotspot_touches_for_governance_pressure,
    }


def summarize_pressures(
    *,
    line_health: dict[str, Any],
    recent_rounds: list[dict[str, Any]],
    hotspots: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    hotspot_paths = {str(item.get("relative_path") or "") for item in hotspots}
    critical_hotspot_paths = {str(item.get("relative_path") or "") for item in hotspots if item.get("severity") == "critical"}
    hotspot_touch_summary = _hotspot_touch_sequences(
        recent_rounds,
        hotspot_paths,
        hotspot_touch_window=int(policy["hotspot_touch_window"]),
        consecutive_hotspot_touches_for_governance_pressure=int(policy["consecutive_hotspot_touches_for_governance_pressure"]),
    )
    ledgers = build_ledgers(recent_rounds)

    stability_level = "low"
    stability_reasons: list[str] = []
    if not bool(line_health.get("all_required_latest_green")):
        stability_level = "high"
        if list((line_health.get("active_line") or {}).get("missing_gate_ids") or []) or list((line_health.get("active_line") or {}).get("non_pass_gate_ids") or []):
            stability_reasons.append("active_line_not_green")
        if list((line_health.get("platform_line") or {}).get("missing_gate_ids") or []) or list((line_health.get("platform_line") or {}).get("non_pass_gate_ids") or []):
            stability_reasons.append("platform_line_not_green")

    governance_level = "low"
    governance_reasons: list[str] = []
    if hotspot_touch_summary["high_touch_hotspot_paths"]:
        governance_level = "high"
        governance_reasons.append("hotspot_touched_three_checkpoint_rounds")
    else:
        critical_recent_touches = []
        recent_touch_window = recent_rounds[: int(policy["hotspot_touch_window"])]
        for path in sorted(critical_hotspot_paths):
            if all(path in list(round_payload.get("touched_hotspot_paths") or []) for round_payload in recent_touch_window) and recent_touch_window:
                critical_recent_touches.append(path)
        if critical_recent_touches:
            governance_level = "high"
            governance_reasons.append("critical_hotspot_touched_recent_window")
            hotspot_touch_summary["critical_touch_hotspot_paths"] = critical_recent_touches
        elif hotspots:
            governance_level = "moderate"
            governance_reasons.append("large_or_critical_hotspots_present")

    progress_level = "low"
    progress_reasons: list[str] = []
    if int(ledgers.get("governance_only_head_streak") or 0) >= int(policy["consecutive_governance_only_rounds_for_progress_pressure"]):
        progress_level = "high"
        progress_reasons.append("consecutive_governance_only_rounds")
    elif recent_rounds and str(recent_rounds[0].get("round_kind") or "") == "governance":
        progress_level = "moderate"
        progress_reasons.append("latest_round_governance_only")

    return {
        "stability_pressure": {
            "level": stability_level,
            "reasons": stability_reasons,
        },
        "governance_pressure": {
            "level": governance_level,
            "reasons": governance_reasons,
            "hotspot_paths": [str(item.get("relative_path") or "") for item in hotspots],
            "hotspot_touch_summary": hotspot_touch_summary,
        },
        "progress_pressure": {
            "level": progress_level,
            "reasons": progress_reasons,
        },
    }


def build_recommendation(pressure_summary: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    stability_level = str(((pressure_summary.get("stability_pressure") or {}).get("level")) or "low")
    governance_level = str(((pressure_summary.get("governance_pressure") or {}).get("level")) or "low")
    progress_level = str(((pressure_summary.get("progress_pressure") or {}).get("level")) or "low")

    if stability_level == "high":
        return {
            "next_round_kind": "stabilization",
            "reason": "stability_pressure_high",
            "priority": policy["recommendation_priority"][0],
        }
    if governance_level == "high":
        return {
            "next_round_kind": "governance",
            "reason": "governance_pressure_high",
            "priority": policy["recommendation_priority"][1],
        }
    if progress_level == "high":
        return {
            "next_round_kind": "progress",
            "reason": "progress_pressure_high",
            "priority": policy["recommendation_priority"][2],
        }
    return {
        "next_round_kind": "flexible",
        "reason": "balanced_enough_to_choose_flexibly",
        "priority": policy["recommendation_priority"][3],
    }


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def discover_checkpoint_rounds(repo_root: Path, *, recent_round_window: int) -> list[dict[str, Any]]:
    raw_output = _git(
        repo_root,
        "log",
        f"-n{recent_round_window}",
        "--format=%H%x1f%s%x1e",
        "--name-only",
        "--",
        "docs/checkpoints",
    )
    commit_records = parse_checkpoint_commit_records(raw_output)
    changed_paths_by_commit: dict[str, list[str]] = {}
    for record in commit_records:
        commit_hash = str(record.get("commit_hash") or "")
        if not commit_hash:
            continue
        changed_output = _git(repo_root, "show", "--format=", "--name-only", "--no-renames", commit_hash)
        changed_paths_by_commit[commit_hash] = [line.strip() for line in changed_output.splitlines() if line.strip()]
    return build_recent_rounds_from_commit_records(
        commit_records,
        recent_round_window=recent_round_window,
        changed_paths_by_commit=changed_paths_by_commit,
    )


def collect_repo_state(repo_root: Path, hotspots: list[dict[str, Any]]) -> dict[str, Any]:
    branch_name = _git(repo_root, "branch", "--show-current").strip()
    head_commit = _git(repo_root, "rev-parse", "HEAD").strip()
    head_subject = _git(repo_root, "log", "-1", "--pretty=%s").strip()
    status_short = _git(repo_root, "status", "-sb").strip()
    status_lines = [line for line in status_short.splitlines() if line.strip()]
    return {
        "repo_root": str(repo_root),
        "branch": branch_name,
        "head_commit": head_commit,
        "head_subject": head_subject,
        "status_short": status_short,
        "dirty": any(not line.startswith("## ") for line in status_lines),
        "hotspots": hotspots,
    }


def build_discussion_signal(
    *,
    status: str,
    recommendation: dict[str, Any],
    previous_report: dict[str, Any] | None,
) -> dict[str, Any]:
    previous_status = str((previous_report or {}).get("status") or "")
    previous_next_round_kind = str((((previous_report or {}).get("recommendation") or {}).get("next_round_kind")) or "")
    reason = str(recommendation.get("reason") or "balanced_enough_to_choose_flexibly")
    if previous_report is None:
        return {
            "should_discuss": True,
            "reason": "initial_dynamic_balance_baseline",
        }
    if status != previous_status or str(recommendation.get("next_round_kind") or "") != previous_next_round_kind:
        return {
            "should_discuss": True,
            "reason": reason,
        }
    if status == "attention":
        return {
            "should_discuss": True,
            "reason": "same_balance_signal_two_rounds",
        }
    return {
        "should_discuss": False,
        "reason": reason,
    }


def build_dynamic_balance_report(
    *,
    repo_root: Path,
    verification_root: Path,
    policy: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Path, Path]:
    repo_root = Path(repo_root).expanduser().resolve()
    verification_root = Path(verification_root).expanduser().resolve()
    policy_payload = {**DEFAULT_POLICY, **(policy or {})}

    previous_report_path = verification_root / f"latest_{GATE_ID}_report.json"
    previous_report = load_json(previous_report_path) if previous_report_path.exists() else None

    hotspots = scan_first_party_hotspots(
        repo_root,
        scan_roots=list(policy_payload["first_party_scan_roots"]),
        excluded_top_level_dirs=set(policy_payload["excluded_top_level_dirs"]),
        large_threshold=int(policy_payload["large_first_party_file_threshold_lines"]),
        critical_threshold=int(policy_payload["critical_first_party_file_threshold_lines"]),
    )
    hotspot_paths = {str(item.get("relative_path") or "") for item in hotspots}
    recent_rounds = discover_checkpoint_rounds(
        repo_root,
        recent_round_window=int(policy_payload["recent_round_window"]),
    )
    for round_payload in recent_rounds:
        round_payload["touched_hotspot_paths"] = [
            path for path in list(round_payload.get("changed_paths") or []) if path in hotspot_paths
        ]
    report_index = build_report_index(verification_root)
    line_health = build_line_health(report_index)
    ledgers = build_ledgers(recent_rounds)
    pressure_summary = summarize_pressures(
        line_health=line_health,
        recent_rounds=recent_rounds,
        hotspots=hotspots,
        policy=policy_payload,
    )
    recommendation = build_recommendation(pressure_summary, policy_payload)
    status = "attention" if recommendation["next_round_kind"] != "flexible" else "pass"
    discussion_signal = build_discussion_signal(
        status=status,
        recommendation=recommendation,
        previous_report=previous_report,
    )

    report_root = verification_root / f"{GATE_ID}_{run_stamp()}"
    report_root.mkdir(parents=True, exist_ok=True)
    report_path = report_root / f"{GATE_ID}_report.json"
    latest_report_path = verification_root / f"latest_{GATE_ID}_report.json"

    payload = {
        "gate_id": GATE_ID,
        "status": status,
        "generated_at_utc": now_utc(),
        "workflow_pack": "tooling",
        "compatibility": {
            "schema_family": SCHEMA_FAMILY,
            "channel": "alpha",
        },
        "repo_state": collect_repo_state(repo_root, hotspots),
        "round_definition": {
            "kind": policy_payload["round_definition"],
            "description": "single git commit that touches docs/checkpoints/*.md",
        },
        "policy": policy_payload,
        "recent_rounds": recent_rounds,
        "line_health": line_health,
        "ledgers": ledgers,
        "pressure_summary": pressure_summary,
        "recommendation": recommendation,
        "discussion_signal": discussion_signal,
        "failed_requirements": [],
        "artifacts": {
            "report_path": str(report_path),
            "latest_report_path": str(latest_report_path),
        },
    }
    return payload, report_path, latest_report_path


def write_dynamic_balance_report(
    *,
    repo_root: Path,
    verification_root: Path,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload, report_path, latest_report_path = build_dynamic_balance_report(
        repo_root=repo_root,
        verification_root=verification_root,
        policy=policy,
    )
    write_json(report_path, payload)
    write_json(latest_report_path, payload)
    return payload
