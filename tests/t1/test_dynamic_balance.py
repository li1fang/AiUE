from __future__ import annotations

from pathlib import Path

from aiue_t1.dynamic_balance import (
    build_line_health,
    build_recent_rounds_from_commit_records,
    build_recommendation,
    classify_round_kind,
    parse_checkpoint_commit_records,
    scan_first_party_hotspots,
    summarize_pressures,
)
from aiue_t1.report_index import ACTIVE_LINE_GATE_IDS, PLATFORM_LINE_GATE_IDS


def test_dynamic_balance_classifies_round_kinds():
    assert classify_round_kind("refactor(unreal): split helpers", ["docs/checkpoints/runtime_governance_checkpoint.md"]) == "governance"
    assert classify_round_kind("feat(tooling): add new capability", ["docs/checkpoints/e2_checkpoint.md"]) == "progress"
    assert classify_round_kind("feat(tooling): add checkpoint hardening", ["docs/checkpoints/e2_hardening_checkpoint.md"]) == "mixed"


def test_dynamic_balance_scans_hotspots(tmp_path: Path):
    runtime_dir = tmp_path / "adapters" / "unreal" / "host_project" / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    hotspot_path = runtime_dir / "common.py"
    hotspot_path.write_text("\n".join("x = 1" for _ in range(1900)), encoding="utf-8")
    hotspots = scan_first_party_hotspots(
        tmp_path,
        scan_roots=["adapters/unreal/host_project/runtime"],
        large_threshold=900,
        critical_threshold=1800,
    )
    assert hotspots
    assert hotspots[0]["relative_path"] == "adapters/unreal/host_project/runtime/common.py"
    assert hotspots[0]["severity"] == "critical"


def test_dynamic_balance_parses_git_log_with_name_only_records():
    raw_output = (
        "4a17aa2\x1ffeat(tooling): add dynamic balance foundation\n\n"
        "docs/checkpoints/dynamic_balance_foundation_checkpoint.md\n"
        "2d32ad0\x1ffeat(tooling): add e2 native invoke path\n\n"
        "docs/checkpoints/e2_native_invoke_path_checkpoint.md\n"
    )
    records = parse_checkpoint_commit_records(raw_output)
    assert records == [
        {
            "commit_hash": "4a17aa2",
            "subject": "feat(tooling): add dynamic balance foundation",
            "checkpoint_paths": ["docs/checkpoints/dynamic_balance_foundation_checkpoint.md"],
        },
        {
            "commit_hash": "2d32ad0",
            "subject": "feat(tooling): add e2 native invoke path",
            "checkpoint_paths": ["docs/checkpoints/e2_native_invoke_path_checkpoint.md"],
        },
    ]


def test_dynamic_balance_detects_pressure_and_recommendation():
    report_index = {
        "reports_by_gate_id": {
            gate_id: {"status": "pass"}
            for gate_id in [*ACTIVE_LINE_GATE_IDS, *PLATFORM_LINE_GATE_IDS]
        }
    }
    line_health = build_line_health(report_index)
    hotspots = [
        {
            "relative_path": "tools/t2/python/aiue_t2/ui.py",
            "severity": "large",
            "line_count": 1000,
        }
    ]
    rounds = build_recent_rounds_from_commit_records(
        [
            {
                "commit_hash": "a1",
                "subject": "refactor(tooling): split view",
                "checkpoint_paths": ["docs/checkpoints/runtime_governance_checkpoint.md"],
                "changed_paths": ["tools/t2/python/aiue_t2/ui.py"],
            },
            {
                "commit_hash": "a2",
                "subject": "refactor(tooling): keep splitting",
                "checkpoint_paths": ["docs/checkpoints/runtime_governance_checkpoint.md"],
                "changed_paths": ["tools/t2/python/aiue_t2/ui.py"],
            },
            {
                "commit_hash": "a3",
                "subject": "refactor(tooling): one more split",
                "checkpoint_paths": ["docs/checkpoints/runtime_governance_checkpoint.md"],
                "changed_paths": ["tools/t2/python/aiue_t2/ui.py"],
            },
        ],
        recent_round_window=6,
        hotspot_paths={"tools/t2/python/aiue_t2/ui.py"},
    )
    pressure_summary = summarize_pressures(
        line_health=line_health,
        recent_rounds=rounds,
        hotspots=hotspots,
        policy={
            "hotspot_touch_window": 3,
            "consecutive_hotspot_touches_for_governance_pressure": 3,
            "consecutive_governance_only_rounds_for_progress_pressure": 2,
            "recommendation_priority": ["stabilization", "governance", "progress", "flexible"],
        },
    )
    recommendation = build_recommendation(
        pressure_summary,
        {
            "recommendation_priority": ["stabilization", "governance", "progress", "flexible"],
        },
    )
    assert pressure_summary["stability_pressure"]["level"] == "low"
    assert pressure_summary["governance_pressure"]["level"] == "high"
    assert pressure_summary["progress_pressure"]["level"] == "high"
    assert recommendation["next_round_kind"] == "governance"


def test_dynamic_balance_detects_stability_pressure_when_required_latest_missing():
    line_health = build_line_health({"reports_by_gate_id": {"visual_proof_v1": {"status": "pass"}}})
    pressure_summary = summarize_pressures(
        line_health=line_health,
        recent_rounds=[],
        hotspots=[],
        policy={
            "hotspot_touch_window": 3,
            "consecutive_hotspot_touches_for_governance_pressure": 3,
            "consecutive_governance_only_rounds_for_progress_pressure": 2,
            "recommendation_priority": ["stabilization", "governance", "progress", "flexible"],
        },
    )
    recommendation = build_recommendation(
        pressure_summary,
        {
            "recommendation_priority": ["stabilization", "governance", "progress", "flexible"],
        },
    )
    assert pressure_summary["stability_pressure"]["level"] == "high"
    assert recommendation["next_round_kind"] == "stabilization"
