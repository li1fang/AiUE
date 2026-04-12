from __future__ import annotations

from pathlib import Path

from aiue_t1.report_index import build_report_index, classify_gate


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "reports"


def test_report_index_classifies_active_and_platform_reports():
    report_index = build_report_index(FIXTURE_ROOT)
    assert report_index["counts"]["reports"] == 9
    assert report_index["counts"]["active_line_reports"] == 4
    assert report_index["counts"]["platform_line_reports"] == 3
    assert report_index["counts"]["governance_line_reports"] == 2
    assert report_index["reports_by_gate_id"]["visual_proof_v1"]["category"] == "active_line"
    assert report_index["reports_by_gate_id"]["generic_slot_abstraction_p1"]["category"] == "platform_line"
    assert report_index["reports_by_gate_id"]["dynamic_balance_governance_progress"]["category"] == "governance_line"
    assert report_index["reports_by_gate_id"]["test_governance_round1"]["category"] == "governance_line"


def test_report_index_knows_new_e1_and_q5x_gates():
    assert classify_gate("showcase_demo_e1")[0] == "active_line"
    assert classify_gate("action_candidate_provider_a1")[0] == "platform_line"
    assert classify_gate("material_texture_proof_m1")[0] == "platform_line"
    assert classify_gate("volumetric_fit_spatial_evidence_q5bx")[0] == "platform_line"
    assert classify_gate("volumetric_inspection_q5c_lite")[0] == "platform_line"
    assert classify_gate("q5c_lite_contrast_lab")[0] == "platform_line"
    assert classify_gate("dynamic_balance_governance_progress")[0] == "governance_line"
    assert classify_gate("test_governance_round1")[0] == "governance_line"
    assert classify_gate("diversity_matrix_dv2")[0] == "governance_line"
    assert classify_gate("diversity_matrix_dv1")[0] == "governance_line"
    assert classify_gate("manual_playable_demo_validation_pv1")[0] == "governance_line"


def test_report_index_classifies_dv1_governance_report(tmp_path: Path):
    from tests.t2.helpers import write_fixture_dv1_report

    verification_root = tmp_path / "verification"
    verification_root.mkdir(parents=True, exist_ok=True)
    write_fixture_dv1_report(verification_root)
    report_index = build_report_index(verification_root)
    governance_gate_ids = [item["gate_id"] for item in report_index["categories"]["governance_line"]]
    assert governance_gate_ids == ["diversity_matrix_dv1"]


def test_report_index_classifies_dv2_governance_report(tmp_path: Path):
    from tests.t2.helpers import write_fixture_dv2_report

    verification_root = tmp_path / "verification"
    verification_root.mkdir(parents=True, exist_ok=True)
    write_fixture_dv2_report(verification_root)
    report_index = build_report_index(verification_root)
    governance_gate_ids = [item["gate_id"] for item in report_index["categories"]["governance_line"]]
    assert governance_gate_ids == ["diversity_matrix_dv2"]


def test_report_index_collects_external_candidate_sources(tmp_path: Path):
    from tests.t2.helpers import write_fixture_a1_report

    verification_root = tmp_path / "verification"
    verification_root.mkdir(parents=True, exist_ok=True)
    write_fixture_a1_report(verification_root)
    report_index = build_report_index(verification_root)
    assert report_index["categories"]["platform_line"][0]["gate_id"] == "action_candidate_provider_a1"
    assert report_index["external_candidate_sources"][0]["provider_name"] == "fixture_provider_v1"
