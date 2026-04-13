from __future__ import annotations

import sys
from pathlib import Path


PMX_PIPELINE_ROOT = Path(__file__).resolve().parents[2] / "workflows" / "pmx_pipeline"
if str(PMX_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PMX_PIPELINE_ROOT))

from run_motion_fixture_diversity_readiness_m2 import classify_selection_ready_clips  # noqa: E402


def test_classify_selection_ready_clips_tracks_distinct_scenarios():
    registry_payload = {
        "clips": [
            {
                "package_id": "pkg_turn_v1",
                "selection_ready": True,
                "scenario_id": "turn-hand-ready",
                "sample_id": "sample_a",
            },
            {
                "package_id": "pkg_turn_v2",
                "selection_ready": True,
                "scenario_id": "turn-hand-ready",
                "sample_id": "sample_a",
            },
            {
                "package_id": "pkg_present_v2",
                "selection_ready": True,
                "scenario_id": "half-turn-present",
                "sample_id": "sample_b",
            },
            {
                "package_id": "pkg_hidden",
                "selection_ready": False,
                "scenario_id": "ignored",
                "sample_id": "sample_c",
            },
        ]
    }

    result = classify_selection_ready_clips(registry_payload)

    assert result["selection_ready_count"] == 3
    assert result["distinct_scenario_ids"] == ["half-turn-present", "turn-hand-ready"]
    assert result["distinct_sample_ids"] == ["sample_a", "sample_b"]
    assert result["packages_by_scenario"]["turn-hand-ready"] == ["pkg_turn_v1", "pkg_turn_v2"]


def test_classify_selection_ready_clips_handles_single_scenario_export():
    registry_payload = {
        "clips": [
            {
                "package_id": "pkg_turn_v1",
                "selection_ready": True,
                "scenario_id": "turn-hand-ready",
                "sample_id": "sample_a",
            },
            {
                "package_id": "pkg_turn_v2",
                "selection_ready": True,
                "scenario_id": "turn-hand-ready",
                "sample_id": "sample_a",
            },
        ]
    }

    result = classify_selection_ready_clips(registry_payload)

    assert result["selection_ready_count"] == 2
    assert result["distinct_scenario_ids"] == ["turn-hand-ready"]
    assert result["distinct_sample_ids"] == ["sample_a"]
