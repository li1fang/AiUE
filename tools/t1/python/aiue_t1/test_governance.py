from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from aiue_core.schema_utils import load_json, write_json

from aiue_t1.dynamic_balance import now_utc, run_stamp
from aiue_t1.report_index import build_report_index


GATE_ID = "test_governance_round1"
SCHEMA_FAMILY = "aiue_test_governance_report"
COVERAGE_LEDGER_RELATIVE_PATH = "docs/governance/test_coverage_ledger_round1.json"
HIGH_PRIORITY_AXIS_IDS = [
    "material_texture_loading",
    "manual_playable_demo_validation",
]
DV1_COVERAGE_AXIS_IDS = {
    "character_variant_diversity",
    "weapon_variant_diversity",
    "clothing_fixture_diversity",
    "fx_fixture_diversity",
    "action_variation",
    "animation_variation",
}
RECOMMENDED_T2_DEFAULT_PATHS = {
    "tools/t2/python/aiue_t2/state.py",
    "tools/t2/python/aiue_t2/ui.py",
    "tools/t2/python/aiue_t2/ui_demo.py",
    "tools/t2/python/aiue_t2/workbench_demo_ops.py",
}
T1_TRIGGER_PREFIXES = (
    "tools/t1/python/aiue_t1/",
    "tests/t1/",
)
T1_TRIGGER_EXACT = {
    "tools/run_t1_evidence_pack.ps1",
    "tools/run_dynamic_balance.ps1",
    "tools/run_test_governance.ps1",
}
T2_TRIGGER_PREFIXES = (
    "tools/t2/python/aiue_t2/",
    "tests/t2/",
)
T2_TRIGGER_PREFIX_GLOBS = (
    "tools/run_t2_workbench",
)
DEFAULT_LANE_POLICY = {
    "change_source_default": "worktree",
    "required_base_lane_ids": [
        "repo_surface",
        "schema_contracts",
    ],
    "recommended_t2_default_paths": sorted(RECOMMENDED_T2_DEFAULT_PATHS),
    "lane_catalog": {
        "repo_surface": "python tools/check_repo_surface.py",
        "schema_contracts": "python tools/check_schema_contracts.py",
        "t1_default": "python -m pytest tests/t1 -q",
        "t2_smoke": "powershell tools/run_t2_workbench_tests.ps1 -Profile smoke",
        "t2_default": "powershell tools/run_t2_workbench_tests.ps1 -Profile default -SkipSoak",
    },
}


LaneExecutor = Callable[[Path, str, str], dict[str, Any]]


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def resolve_changed_paths(repo_root: Path, *, change_source: str = "worktree") -> list[str]:
    repo_root = Path(repo_root).expanduser().resolve()
    if change_source == "head":
        output = _git(repo_root, "show", "--format=", "--name-only", "--no-renames", "HEAD")
        return [line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()]
    if change_source != "worktree":
        raise ValueError(f"Unsupported change source: {change_source}")
    output = _git(repo_root, "status", "--short", "--untracked-files=all")
    changed_paths: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        path_text = line[3:].strip() if len(line) >= 4 else line.strip()
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1].strip()
        normalized = path_text.replace("\\", "/")
        if normalized:
            changed_paths.append(normalized)
    return changed_paths


def load_coverage_ledger(coverage_ledger_path: Path) -> dict[str, Any]:
    payload = load_json(coverage_ledger_path)
    coverage_axes = list(payload.get("coverage_axes") or [])
    if not coverage_axes:
        raise ValueError("coverage_axes_missing")
    for entry in coverage_axes:
        axis_id = str(entry.get("axis_id") or "")
        status = str(entry.get("status") or "")
        if not axis_id:
            raise ValueError("coverage_axis_id_missing")
        if status not in {"covered", "partial", "missing"}:
            raise ValueError(f"coverage_axis_status_invalid:{axis_id}")
    return payload


def summarize_coverage_ledger(coverage_ledger: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    axes = [dict(item) for item in list(coverage_ledger.get("coverage_axes") or [])]
    covered_count = sum(1 for item in axes if str(item.get("status") or "") == "covered")
    partial_count = sum(1 for item in axes if str(item.get("status") or "") == "partial")
    missing_count = sum(1 for item in axes if str(item.get("status") or "") == "missing")
    known_blind_spots: list[dict[str, Any]] = []
    high_priority_missing_ids: list[str] = []
    for entry in axes:
        axis_id = str(entry.get("axis_id") or "")
        status = str(entry.get("status") or "")
        if status == "covered":
            continue
        priority = "high" if axis_id in HIGH_PRIORITY_AXIS_IDS else "normal"
        known_blind_spots.append(
            {
                "axis_id": axis_id,
                "status": status,
                "summary": str(entry.get("summary") or ""),
                "priority": priority,
                "evidence_gate_ids": [str(item) for item in list(entry.get("evidence_gate_ids") or []) if str(item)],
            }
        )
        if axis_id in HIGH_PRIORITY_AXIS_IDS and status == "missing":
            high_priority_missing_ids.append(axis_id)
    coverage_summary = {
        "covered_count": covered_count,
        "partial_count": partial_count,
        "missing_count": missing_count,
        "blind_spot_count": len(known_blind_spots),
        "high_priority_missing_count": len(high_priority_missing_ids),
    }
    return coverage_summary, known_blind_spots, high_priority_missing_ids


def apply_report_coverage_overrides(coverage_ledger: dict[str, Any], verification_root: Path) -> dict[str, Any]:
    verification_root = Path(verification_root).expanduser().resolve()
    if not verification_root.exists():
        return coverage_ledger
    report_index = build_report_index(verification_root)
    reports_by_gate_id = dict(report_index.get("reports_by_gate_id") or {})
    overridden_axes = []
    for entry in list(coverage_ledger.get("coverage_axes") or []):
        axis = dict(entry)
        axis_id = str(axis.get("axis_id") or "")
        evidence_gate_ids = [str(item) for item in list(axis.get("evidence_gate_ids") or []) if str(item)]
        if axis_id == "material_texture_loading":
            evidence_gate_ids = sorted(set(evidence_gate_ids + ["material_texture_proof_m1"]))
            m1_report = dict(reports_by_gate_id.get("material_texture_proof_m1") or {}).get("report") or {}
            if str(m1_report.get("status") or "") == "pass":
                axis["status"] = "covered"
                axis["summary"] = "Material and texture loading are covered by the current M1 material proof."
        elif axis_id == "manual_playable_demo_validation":
            evidence_gate_ids = sorted(set(evidence_gate_ids + ["manual_playable_demo_validation_pv1"]))
            pv1_report = dict(reports_by_gate_id.get("manual_playable_demo_validation_pv1") or {}).get("report") or {}
            if str(pv1_report.get("status") or "") == "pass":
                axis["status"] = "covered"
                axis["summary"] = "Playable demo has a recorded manual PV1 signoff for the current demo path."
        elif axis_id in DV1_COVERAGE_AXIS_IDS:
            evidence_gate_ids = sorted(set(evidence_gate_ids + ["diversity_matrix_dv1"]))
            dv1_report = dict(reports_by_gate_id.get("diversity_matrix_dv1") or {}).get("report") or {}
            dv1_axis = next(
                (
                    dict(item)
                    for item in list(dv1_report.get("coverage_axes") or [])
                    if str(item.get("axis_id") or "") == axis_id
                ),
                {},
            )
            if dv1_axis:
                axis["status"] = str(dv1_axis.get("status") or axis.get("status") or "partial")
                axis["summary"] = str(dv1_axis.get("summary") or axis.get("summary") or "")
        axis["evidence_gate_ids"] = evidence_gate_ids
        overridden_axes.append(axis)
    return {
        **coverage_ledger,
        "coverage_axes": overridden_axes,
    }


def resolve_lane_ids(changed_paths: list[str]) -> tuple[list[str], list[str]]:
    normalized_paths = [str(path or "").replace("\\", "/") for path in changed_paths if str(path or "").strip()]
    required = set(DEFAULT_LANE_POLICY["required_base_lane_ids"])
    recommended: set[str] = set()

    if any(path.startswith(T1_TRIGGER_PREFIXES) or path in T1_TRIGGER_EXACT for path in normalized_paths):
        required.add("t1_default")
    if any(
        path.startswith(T2_TRIGGER_PREFIXES) or any(path.startswith(prefix) for prefix in T2_TRIGGER_PREFIX_GLOBS)
        for path in normalized_paths
    ):
        required.add("t2_smoke")
    if any(path in RECOMMENDED_T2_DEFAULT_PATHS for path in normalized_paths):
        recommended.add("t2_default")

    ordered_required = [lane_id for lane_id in ["repo_surface", "schema_contracts", "t1_default", "t2_smoke"] if lane_id in required]
    ordered_recommended = [lane_id for lane_id in ["t2_default"] if lane_id in recommended]
    return ordered_required, ordered_recommended


def _lane_command(repo_root: Path, lane_id: str, python_exe: str) -> list[str]:
    repo_root = Path(repo_root).expanduser().resolve()
    if lane_id == "repo_surface":
        return [python_exe, str((repo_root / "tools" / "check_repo_surface.py").resolve()), "--repo-root", str(repo_root)]
    if lane_id == "schema_contracts":
        return [python_exe, str((repo_root / "tools" / "check_schema_contracts.py").resolve()), "--repo-root", str(repo_root)]
    if lane_id == "t1_default":
        return [python_exe, "-m", "pytest", "tests/t1", "-q"]
    if lane_id == "t2_smoke":
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str((repo_root / "tools" / "run_t2_workbench_tests.ps1").resolve()),
            "-Profile",
            "smoke",
        ]
    if lane_id == "t2_default":
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str((repo_root / "tools" / "run_t2_workbench_tests.ps1").resolve()),
            "-Profile",
            "default",
            "-SkipSoak",
        ]
    raise ValueError(f"Unsupported lane id: {lane_id}")


def run_lane(repo_root: Path, lane_id: str, python_exe: str) -> dict[str, Any]:
    command = _lane_command(repo_root, lane_id, python_exe)
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    duration_seconds = time.perf_counter() - started
    stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    stderr_lines = [line for line in completed.stderr.splitlines() if line.strip()]
    return {
        "lane_id": lane_id,
        "status": "pass" if completed.returncode == 0 else "fail",
        "returncode": int(completed.returncode),
        "command": command,
        "duration_seconds": round(float(duration_seconds), 3),
        "stdout_tail": stdout_lines[-10:],
        "stderr_tail": stderr_lines[-10:],
    }


def build_checkpoint_readiness(
    *,
    required_lane_ids: list[str],
    executed_lane_results: list[dict[str, Any]],
    high_priority_blind_spot_ids: list[str],
) -> dict[str, Any]:
    results_by_lane_id = {
        str(item.get("lane_id") or ""): dict(item)
        for item in executed_lane_results
        if str(item.get("lane_id") or "")
    }
    failed_required_lane_ids = [
        lane_id
        for lane_id in required_lane_ids
        if str((results_by_lane_id.get(lane_id) or {}).get("status") or "missing") != "pass"
    ]
    reasons: list[str] = []
    if failed_required_lane_ids:
        reasons.append("required_lanes_failed_or_missing")
    if high_priority_blind_spot_ids:
        reasons.append("high_priority_blind_spots_missing")
    return {
        "ready": not failed_required_lane_ids and not high_priority_blind_spot_ids,
        "failed_required_lane_ids": failed_required_lane_ids,
        "high_priority_blind_spot_ids": list(high_priority_blind_spot_ids),
        "reasons": reasons,
    }


def build_discussion_signal(*, status: str, checkpoint_readiness: dict[str, Any]) -> dict[str, Any]:
    if str(status) == "error":
        return {
            "should_discuss": True,
            "reason": "governance_tooling_error",
        }
    if list(checkpoint_readiness.get("failed_required_lane_ids") or []):
        return {
            "should_discuss": True,
            "reason": "required_lanes_failed_or_missing",
        }
    if list(checkpoint_readiness.get("high_priority_blind_spot_ids") or []):
        return {
            "should_discuss": True,
            "reason": "high_priority_blind_spots_missing",
        }
    return {
        "should_discuss": False,
        "reason": "test_governance_green",
    }


def collect_repo_state(repo_root: Path, *, change_source: str, changed_paths: list[str]) -> dict[str, Any]:
    repo_root = Path(repo_root).expanduser().resolve()
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
        "change_source": change_source,
        "changed_paths": list(changed_paths),
    }


def build_test_governance_report(
    *,
    repo_root: Path,
    verification_root: Path,
    coverage_ledger_path: Path | None = None,
    change_source: str = "worktree",
    changed_paths: list[str] | None = None,
    lane_executor: LaneExecutor | None = None,
    python_exe: str | None = None,
) -> tuple[dict[str, Any], Path, Path]:
    repo_root = Path(repo_root).expanduser().resolve()
    verification_root = Path(verification_root).expanduser().resolve()
    coverage_ledger_path = Path(coverage_ledger_path or (repo_root / COVERAGE_LEDGER_RELATIVE_PATH)).expanduser().resolve()
    python_exe = python_exe or sys.executable
    lane_executor = lane_executor or run_lane

    coverage_ledger = apply_report_coverage_overrides(
        load_coverage_ledger(coverage_ledger_path),
        verification_root=verification_root,
    )
    resolved_changed_paths = list(changed_paths) if changed_paths is not None else resolve_changed_paths(repo_root, change_source=change_source)
    required_lane_ids, recommended_lane_ids = resolve_lane_ids(resolved_changed_paths)
    coverage_summary, known_blind_spots, high_priority_blind_spot_ids = summarize_coverage_ledger(coverage_ledger)

    executed_lane_results = [
        lane_executor(repo_root, lane_id, python_exe)
        for lane_id in required_lane_ids
    ]
    checkpoint_readiness = build_checkpoint_readiness(
        required_lane_ids=required_lane_ids,
        executed_lane_results=executed_lane_results,
        high_priority_blind_spot_ids=high_priority_blind_spot_ids,
    )

    status = "pass"
    if list(checkpoint_readiness.get("failed_required_lane_ids") or []) or high_priority_blind_spot_ids:
        status = "attention"

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
        "repo_state": collect_repo_state(
            repo_root,
            change_source=change_source,
            changed_paths=resolved_changed_paths,
        ),
        "coverage_summary": coverage_summary,
        "coverage_axes": [dict(item) for item in list(coverage_ledger.get("coverage_axes") or [])],
        "known_blind_spots": known_blind_spots,
        "lane_policy": dict(DEFAULT_LANE_POLICY),
        "required_lane_ids": required_lane_ids,
        "recommended_lane_ids": recommended_lane_ids,
        "executed_lane_results": executed_lane_results,
        "checkpoint_readiness": checkpoint_readiness,
        "discussion_signal": build_discussion_signal(
            status=status,
            checkpoint_readiness=checkpoint_readiness,
        ),
        "artifacts": {
            "coverage_ledger_path": str(coverage_ledger_path),
            "report_path": str(report_path),
            "latest_report_path": str(latest_report_path),
        },
    }
    return payload, report_path, latest_report_path


def write_test_governance_report(
    *,
    repo_root: Path,
    verification_root: Path,
    coverage_ledger_path: Path | None = None,
    change_source: str = "worktree",
) -> dict[str, Any]:
    payload, report_path, latest_report_path = build_test_governance_report(
        repo_root=repo_root,
        verification_root=verification_root,
        coverage_ledger_path=coverage_ledger_path,
        change_source=change_source,
    )
    write_json(report_path, payload)
    write_json(latest_report_path, payload)
    return payload
