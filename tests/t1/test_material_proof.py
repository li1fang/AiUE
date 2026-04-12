from __future__ import annotations

from pathlib import Path

from aiue_t1.material_proof import (
    build_material_proof_quality_summary,
    load_lenient_json,
    validation_summary_from_payload,
)
from aiue_t1.report_index import build_report_index
from aiue_t1.test_governance import apply_report_coverage_overrides, load_coverage_ledger

from tests.t2.helpers import build_fixture_pack


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_load_lenient_json_recovers_invalid_backslashes(tmp_path: Path):
    payload_path = tmp_path / "ue_validation_report.local.json"
    payload_path.write_text(
        '{\n'
        '  "package_id": "pkg_alpha",\n'
        '  "source_file": "C:\\broken\\path\\模型.pmx",\n'
        '  "import_report_path": "C:\\broken\\reports\\ue_import_report.local.json",\n'
        '  "checks": {\n'
        '    "expected_texture_count": 3,\n'
        '    "imported_texture_count": 3,\n'
        '    "expected_material_slot_names": ["Mat_001"],\n'
        '    "actual_material_slot_names": ["Mat_001"]\n'
        '  },\n'
        '  "status": "pass"\n'
        '}',
        encoding="utf-8",
    )
    payload, warnings = load_lenient_json(payload_path)
    summary = validation_summary_from_payload(payload, payload_path, warnings=warnings)
    assert summary["package_id"] == "pkg_alpha"
    assert summary["expected_texture_count"] == 3
    assert summary["imported_texture_count"] == 3
    assert summary["material_slot_names_match"] is True
    assert any(item.startswith("lenient_backslash_fallback:") for item in summary["warnings"])


def test_build_material_proof_quality_summary_reads_latest_m1(tmp_path: Path):
    build_fixture_pack(tmp_path, include_m1=True)
    report_index = build_report_index(tmp_path / "verification")
    summary = build_material_proof_quality_summary(report_index)
    assert summary["status"] == "pass"
    assert summary["package_count"] == 1
    assert summary["packages"][0]["package_id"] == "pkg_alpha"
    assert summary["packages"][0]["character_imported_texture_count"] == 13
    assert summary["packages"][0]["weapon_imported_texture_count"] == 3


def test_apply_report_coverage_overrides_clears_m1_and_pv1_when_latest_pass(tmp_path: Path):
    build_fixture_pack(tmp_path, include_m1=True, include_pv1=True)
    ledger = load_coverage_ledger(REPO_ROOT / "docs" / "governance" / "test_coverage_ledger_round1.json")
    overridden = apply_report_coverage_overrides(ledger, tmp_path / "verification")
    status_by_axis = {str(item.get("axis_id") or ""): str(item.get("status") or "") for item in list(overridden.get("coverage_axes") or [])}
    assert status_by_axis["material_texture_loading"] == "covered"
    # Fixture PV1 defaults to attention, so it should remain missing until a pass signoff exists.
    assert status_by_axis["manual_playable_demo_validation"] == "missing"
