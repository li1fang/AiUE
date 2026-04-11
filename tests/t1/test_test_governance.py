from __future__ import annotations

from pathlib import Path

from aiue_t1.test_governance import (
    build_test_governance_report,
    load_coverage_ledger,
    resolve_lane_ids,
    summarize_coverage_ledger,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_test_governance_resolves_required_and_recommended_lanes():
    required_lane_ids, recommended_lane_ids = resolve_lane_ids(
        [
            "tools/t2/python/aiue_t2/state.py",
            "tools/t1/python/aiue_t1/test_governance.py",
        ]
    )
    assert required_lane_ids == [
        "repo_surface",
        "schema_contracts",
        "t1_default",
        "t2_smoke",
    ]
    assert recommended_lane_ids == ["t2_default"]


def test_test_governance_summarizes_high_priority_blind_spots():
    ledger = load_coverage_ledger(REPO_ROOT / "docs" / "governance" / "test_coverage_ledger_round1.json")
    coverage_summary, _, high_priority_blind_spot_ids = summarize_coverage_ledger(ledger)
    assert coverage_summary["missing_count"] >= 2
    assert coverage_summary["high_priority_missing_count"] == 2
    assert high_priority_blind_spot_ids == [
        "material_texture_loading",
        "manual_playable_demo_validation",
    ]


def test_test_governance_report_stays_attention_when_high_priority_blind_spots_remain(tmp_path: Path):
    executed_lanes: list[str] = []

    def fake_lane_executor(repo_root, lane_id, python_executable):
        executed_lanes.append(lane_id)
        return {
            "lane_id": lane_id,
            "status": "pass",
            "returncode": 0,
            "stdout_tail": [],
            "stderr_tail": [],
            "command": [python_executable, lane_id],
        }

    report, _, _ = build_test_governance_report(
        repo_root=REPO_ROOT,
        verification_root=tmp_path,
        coverage_ledger_path=REPO_ROOT / "docs" / "governance" / "test_coverage_ledger_round1.json",
        changed_paths=[
            "tools/t2/python/aiue_t2/state.py",
            "tools/t1/python/aiue_t1/test_governance.py",
        ],
        lane_executor=fake_lane_executor,
    )
    assert executed_lanes == ["repo_surface", "schema_contracts", "t1_default", "t2_smoke"]
    assert report["status"] == "attention"
    assert report["checkpoint_readiness"]["ready"] is False
    assert report["required_lane_ids"] == ["repo_surface", "schema_contracts", "t1_default", "t2_smoke"]
    assert report["recommended_lane_ids"] == ["t2_default"]
    assert report["checkpoint_readiness"]["high_priority_blind_spot_ids"] == [
        "material_texture_loading",
        "manual_playable_demo_validation",
    ]
