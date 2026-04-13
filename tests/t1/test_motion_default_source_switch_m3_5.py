from __future__ import annotations

import sys
from pathlib import Path


PMX_PIPELINE_ROOT = Path(__file__).resolve().parents[2] / "workflows" / "pmx_pipeline"
if str(PMX_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PMX_PIPELINE_ROOT))

from run_motion_default_source_switch_m3_5 import evaluate_cutover_report, select_cutover_package_id  # noqa: E402


def test_select_cutover_package_id_prefers_preferred_package():
    selected = select_cutover_package_id(
        {
            "package_ids": [
                "pkg_other",
                "pkg_route-a-3s-turn-hand-ready-v0-2_a70fed1ad7",
            ]
        }
    )

    assert selected == "pkg_route-a-3s-turn-hand-ready-v0-2_a70fed1ad7"


def test_evaluate_cutover_report_accepts_green_report():
    status, failed_requirements, summary = evaluate_cutover_report(
        "pkg_demo",
        {
            "status": "pass",
            "toy_yard_motion_view_root": "C:/toy-yard/motion/default",
            "consumer_result": {
                "status": "pass",
                "communication_signal": {
                    "owner": "none",
                    "should_contact_toy_yard": False,
                },
                "preview_evidence": {
                    "subject_visible": True,
                    "pose_changed": True,
                    "before_image_path": "C:/tmp/before.png",
                    "after_image_path": "C:/tmp/after.png",
                },
            },
        },
        0,
        "C:/toy-yard/motion/default",
    )

    assert status == "pass"
    assert failed_requirements == []
    assert summary["owner"] == "none"


def test_evaluate_cutover_report_flags_view_root_and_visibility_failures():
    status, failed_requirements, _ = evaluate_cutover_report(
        "pkg_demo",
        {
            "status": "fail",
            "toy_yard_motion_view_root": "C:/toy-yard/motion/other",
            "consumer_result": {
                "status": "fail",
                "communication_signal": {
                    "owner": "aiue",
                    "should_contact_toy_yard": True,
                },
                "preview_evidence": {
                    "subject_visible": False,
                    "pose_changed": False,
                },
            },
        },
        1,
        "C:/toy-yard/motion/default",
    )
    failed_ids = {item["id"] for item in failed_requirements}

    assert status == "fail"
    assert "m3_5_cutover_process_failed" in failed_ids
    assert "m3_5_cutover_gate_failed" in failed_ids
    assert "m3_5_consumer_result_not_pass" in failed_ids
    assert "m3_5_owner_not_none" in failed_ids
    assert "m3_5_should_contact_toy_yard_true" in failed_ids
    assert "m3_5_subject_not_visible" in failed_ids
    assert "m3_5_pose_not_changed" in failed_ids
    assert "m3_5_view_root_drift" in failed_ids
