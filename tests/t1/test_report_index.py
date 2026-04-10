from __future__ import annotations

from pathlib import Path

from aiue_t1.report_index import build_report_index


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "reports"


def test_report_index_classifies_active_and_platform_reports():
    report_index = build_report_index(FIXTURE_ROOT)
    assert report_index["counts"]["reports"] == 7
    assert report_index["counts"]["active_line_reports"] == 4
    assert report_index["counts"]["platform_line_reports"] == 3
    assert report_index["reports_by_gate_id"]["visual_proof_v1"]["category"] == "active_line"
    assert report_index["reports_by_gate_id"]["generic_slot_abstraction_p1"]["category"] == "platform_line"
