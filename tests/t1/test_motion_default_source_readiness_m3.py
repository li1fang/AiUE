from __future__ import annotations

import sys
from pathlib import Path


PMX_PIPELINE_ROOT = Path(__file__).resolve().parents[2] / "workflows" / "pmx_pipeline"
if str(PMX_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PMX_PIPELINE_ROOT))

from run_motion_default_source_readiness_m3 import evaluate_default_source_readiness  # noqa: E402


def _build_green_payloads():
    m2_5_report = {
        "status": "pass",
        "mixed_profile_snapshot": {
            "profile": "trial-motion-m2-diversity",
            "sample_id": "",
            "sample_ids": ["sample_a", "sample_b", "sample_c"],
            "scenario_id": "",
            "scenario_ids": ["scenario_a", "scenario_b", "scenario_c"],
        },
        "package_results": [
            {"package_id": "pkg_a", "status": "pass", "subject_visible": True, "pose_changed": True, "owner": "none"},
            {"package_id": "pkg_b", "status": "pass", "subject_visible": True, "pose_changed": True, "owner": "none"},
            {"package_id": "pkg_c", "status": "pass", "subject_visible": True, "pose_changed": True, "owner": "none"},
        ],
    }
    m2_report = {"status": "pass"}
    readiness_report = {"status": "pass"}
    summary_payload = {
        "profile": "trial-motion-m2-diversity",
        "source": "toy-yard export",
        "export_contract_version": "toy-yard-motion-1.0",
        "sample_id": "",
        "scenario_id": "",
    }
    registry_payload = {"export_contract_version": "toy-yard-motion-1.0"}
    communication_signal = {
        "handoff_ready": True,
        "needs_counterparty_contact": False,
        "problem_owner": "none",
        "recommended_next_node": "aiue_import_motion_packet",
    }
    return m2_5_report, m2_report, readiness_report, summary_payload, registry_payload, communication_signal


def test_evaluate_default_source_readiness_accepts_green_candidate():
    payloads = _build_green_payloads()

    result = evaluate_default_source_readiness(*payloads)

    assert result["status"] == "pass"
    assert result["default_source_candidate"] is True
    assert result["counts"]["package_passes"] == 3


def test_evaluate_default_source_readiness_flags_contract_and_signal_gaps():
    payloads = list(_build_green_payloads())
    payloads[3]["sample_id"] = "sample_a"
    payloads[5]["handoff_ready"] = False
    payloads[5]["problem_owner"] = "toy-yard"

    result = evaluate_default_source_readiness(*payloads)
    failed_ids = {item["id"] for item in result["failed_requirements"]}

    assert result["status"] == "fail"
    assert result["default_source_candidate"] is False
    assert "m3_summary_sample_id_not_empty" in failed_ids
    assert "m3_handoff_not_ready" in failed_ids
    assert "m3_problem_owner_not_none" in failed_ids
