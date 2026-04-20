from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = REPO_ROOT / "workflows" / "pmx_pipeline"


def _load_p0_module():
    sys.modules.pop("_bootstrap", None)
    workflow_root_text = str(WORKFLOW_ROOT)
    if workflow_root_text not in sys.path:
        sys.path.insert(0, workflow_root_text)
    spec = importlib.util.spec_from_file_location(
        "aiue_test_run_source_contract_preflight_p0",
        WORKFLOW_ROOT / "run_source_contract_preflight_p0.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evaluate_source_evidence = _load_p0_module().evaluate_source_evidence


def test_p0_source_evidence_passes_with_complete_contract(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    import_report_path = tmp_path / "ue_import_report.local.json"
    validation_report_path = tmp_path / "ue_validation_report.local.json"
    for path in (manifest_path, import_report_path, validation_report_path):
        path.write_text("{}", encoding="utf-8")

    evidence, failures = evaluate_source_evidence(
        {
            "validation": {
                "package_id": "pkg_alpha",
                "sample_id": "sample_alpha",
                "status": "pass",
                "source_path": str(validation_report_path),
                "expected_texture_count": 2,
                "imported_texture_count": 2,
                "expected_material_slot_names": ["Body", "Face"],
                "actual_material_slot_names": ["Body", "Face"],
            },
            "import": {
                "package_id": "pkg_alpha",
                "sample_id": "sample_alpha",
                "status": "pass",
                "source_path": str(import_report_path),
                "manifest_path": str(manifest_path),
                "mesh_destination": "/Game/Characters/Alpha",
                "texture_destination": "/Game/Characters/Alpha/Textures",
                "imported_texture_assets": [
                    "/Game/Characters/Alpha/Textures/T_Diffuse",
                    "/Game/Characters/Alpha/Textures/T_Normal",
                ],
            },
        },
        expected_package_id="pkg_alpha",
        expected_sample_id="sample_alpha",
        package_id="pkg_alpha",
        role="character",
    )

    assert evidence["status"] == "pass"
    assert failures == []


def test_p0_source_evidence_detects_missing_manifest_and_slot_mismatch(tmp_path: Path):
    import_report_path = tmp_path / "ue_import_report.local.json"
    validation_report_path = tmp_path / "ue_validation_report.local.json"
    for path in (import_report_path, validation_report_path):
        path.write_text("{}", encoding="utf-8")

    _, failures = evaluate_source_evidence(
        {
            "validation": {
                "package_id": "pkg_alpha",
                "sample_id": "sample_alpha",
                "status": "pass",
                "source_path": str(validation_report_path),
                "expected_texture_count": 2,
                "imported_texture_count": 1,
                "expected_material_slot_names": ["Body", "Face"],
                "actual_material_slot_names": ["Body"],
            },
            "import": {
                "package_id": "pkg_alpha",
                "sample_id": "sample_alpha",
                "status": "pass",
                "source_path": str(import_report_path),
                "manifest_path": str(tmp_path / "missing_manifest.json"),
                "mesh_destination": "",
                "texture_destination": "/Game/Characters/Alpha/Textures",
                "imported_texture_assets": [],
            },
        },
        expected_package_id="pkg_alpha",
        expected_sample_id="sample_alpha",
        package_id="pkg_alpha",
        role="character",
    )

    failure_ids = {str(item.get("id") or "") for item in failures}
    assert "p0_texture_count_mismatch" in failure_ids
    assert "p0_material_slot_names_mismatch" in failure_ids
    assert "p0_manifest_missing" in failure_ids
    assert "p0_mesh_destination_missing" in failure_ids
