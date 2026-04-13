from __future__ import annotations

import sys
from pathlib import Path


PMX_PIPELINE_ROOT = Path(__file__).resolve().parents[2] / "workflows" / "pmx_pipeline"
if str(PMX_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PMX_PIPELINE_ROOT))

from run_motion_fixture_diversity_m2 import evaluate_package_result, summarize_packages  # noqa: E402


def test_evaluate_package_result_accepts_green_package():
    entry = {
        "package_id": "pkg_turn",
        "scenario_id": "turn",
        "sample_id": "sample_turn",
    }
    report_payload = {
        "status": "pass",
        "_report_path": "C:/tmp/pkg_turn_report.json",
        "consumer_result": {
            "status": "pass",
            "communication_signal": {
                "owner": "none",
            },
            "preview_evidence": {
                "subject_visible": True,
                "pose_changed": True,
                "result_json_path": "C:/tmp/result.json",
                "before_image_path": "C:/tmp/before.png",
                "after_image_path": "C:/tmp/after.png",
            },
            "warnings": [],
            "errors": [],
        },
    }

    result = evaluate_package_result(entry, report_payload, 0, [])

    assert result["status"] == "pass"
    assert result["owner"] == "none"
    assert result["subject_visible"] is True
    assert result["pose_changed"] is True
    assert result["failed_requirements"] == []


def test_evaluate_package_result_flags_consumer_failures():
    entry = {
        "package_id": "pkg_present",
        "scenario_id": "present",
        "sample_id": "sample_present",
    }
    report_payload = {
        "status": "fail",
        "consumer_result": {
            "status": "fail",
            "communication_signal": {
                "owner": "aiue",
            },
            "preview_evidence": {
                "subject_visible": False,
                "pose_changed": False,
            },
        },
    }

    result = evaluate_package_result(entry, report_payload, 1, [])
    failed_ids = {item["id"] for item in result["failed_requirements"]}

    assert result["status"] == "fail"
    assert "m2_package_process_failed" in failed_ids
    assert "m2_package_gate_failed" in failed_ids
    assert "m2_package_consumer_result_failed" in failed_ids
    assert "m2_package_owner_not_none" in failed_ids
    assert "m2_package_subject_not_visible" in failed_ids
    assert "m2_package_pose_not_changed" in failed_ids


def test_evaluate_package_result_allows_scope_mismatch_only_when_consumer_result_is_green():
    entry = {
        "package_id": "pkg_receive",
        "scenario_id": "receive",
        "sample_id": "sample_receive",
    }
    report_payload = {
        "status": "fail",
        "failed_requirements": [
            {
                "id": "m0_5_candidate_scope_mismatch",
                "message": "locked to original single-fixture scope",
            }
        ],
        "consumer_result": {
            "status": "pass",
            "communication_signal": {
                "owner": "none",
            },
            "preview_evidence": {
                "subject_visible": True,
                "pose_changed": True,
                "result_json_path": "C:/tmp/result.json",
                "before_image_path": "C:/tmp/before.png",
                "after_image_path": "C:/tmp/after.png",
            },
            "warnings": [],
            "errors": [],
        },
    }

    result = evaluate_package_result(entry, report_payload, 1, [])

    assert result["status"] == "pass"
    assert result["scope_mismatch_only"] is True
    assert result["failed_requirements"] == []


def test_summarize_packages_detects_package_or_scenario_mismatch():
    package_results = [
        {
            "package_id": "pkg_turn",
            "scenario_id": "turn",
            "status": "pass",
            "owner": "none",
            "subject_visible": True,
            "pose_changed": True,
            "failed_requirements": [],
        },
        {
            "package_id": "pkg_present",
            "scenario_id": "present",
            "status": "pass",
            "owner": "none",
            "subject_visible": True,
            "pose_changed": True,
            "failed_requirements": [],
        },
    ]

    status, failed_requirements, counts = summarize_packages(
        package_results,
        expected_packages=["pkg_turn", "pkg_receive"],
        expected_scenarios=["present", "turn", "receive"],
    )

    assert status == "fail"
    assert counts["package_count"] == 2
    assert counts["package_passes"] == 2
    assert counts["distinct_scenarios_executed"] == 2
    assert {item["id"] for item in failed_requirements} == {
        "m2_package_set_mismatch",
        "m2_scenario_set_mismatch",
    }
