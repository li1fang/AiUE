from __future__ import annotations

import sys
from pathlib import Path


PMX_PIPELINE_ROOT = Path(__file__).resolve().parents[2] / "workflows" / "pmx_pipeline"
if str(PMX_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PMX_PIPELINE_ROOT))

from run_motion_consumer_baseline_m1 import (  # noqa: E402
    evaluate_iteration_report,
    make_iteration_paths,
    summarize_iterations,
)


def test_make_iteration_paths_creates_isolated_m0_5_paths():
    output_root = Path("C:/tmp/m1-output")
    state_root = Path("C:/tmp/m1-state")

    paths = make_iteration_paths(output_root, state_root, 2)

    assert paths["output_root"] == output_root / "iteration_02"
    assert paths["state_root"] == state_root / "iteration_02"
    assert paths["latest_report_path"] == output_root / "iteration_02_latest_motion_shadow_packet_trial_m0_5_report.json"


def test_evaluate_iteration_report_accepts_green_m0_5_result():
    report_payload = {
        "status": "pass",
        "_report_path": "C:/tmp/iteration_01_latest_motion_shadow_packet_trial_m0_5_report.json",
        "consumer_result": {
            "status": "pass",
            "communication_signal": {
                "owner": "none",
            },
            "preview_evidence": {
                "subject_visible": True,
                "pose_changed": True,
                "result_json_path": "C:/tmp/preview.action.json",
                "before_image_path": "C:/tmp/before.png",
                "after_image_path": "C:/tmp/after.png",
            },
            "warnings": [],
            "errors": [],
        },
    }

    result = evaluate_iteration_report(1, report_payload, 0, [])

    assert result["status"] == "pass"
    assert result["owner"] == "none"
    assert result["subject_visible"] is True
    assert result["pose_changed"] is True
    assert result["failed_requirements"] == []


def test_evaluate_iteration_report_flags_owner_or_visibility_failures():
    report_payload = {
        "status": "pass",
        "consumer_result": {
            "status": "pass",
            "communication_signal": {
                "owner": "aiue",
            },
            "preview_evidence": {
                "subject_visible": False,
                "pose_changed": False,
            },
        },
    }

    result = evaluate_iteration_report(2, report_payload, 0, [])
    failed_ids = {item["id"] for item in result["failed_requirements"]}

    assert result["status"] == "fail"
    assert "m1_iteration_owner_not_none" in failed_ids
    assert "m1_iteration_subject_not_visible" in failed_ids
    assert "m1_iteration_pose_not_changed" in failed_ids


def test_summarize_iterations_requires_all_requested_passes():
    iteration_results = [
        {
            "iteration_index": 1,
            "status": "pass",
            "owner": "none",
            "subject_visible": True,
            "pose_changed": True,
            "failed_requirements": [],
        },
        {
            "iteration_index": 2,
            "status": "fail",
            "owner": "aiue",
            "subject_visible": True,
            "pose_changed": False,
            "failed_requirements": [
                {"id": "m1_iteration_pose_not_changed", "message": "missing pose change"},
            ],
        },
    ]

    status, failed_requirements, counts = summarize_iterations(iteration_results, 3)

    assert status == "fail"
    assert counts["iterations_requested"] == 3
    assert counts["iterations_completed"] == 2
    assert counts["iterations_passed"] == 1
    assert counts["iteration_failures"] == 1
    assert {item["id"] for item in failed_requirements} == {
        "m1_iteration_pose_not_changed",
        "m1_iteration_count_mismatch",
    }
