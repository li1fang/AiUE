from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PMX_PIPELINE_ROOT = REPO_ROOT / "workflows" / "pmx_pipeline"
T1_ROOT = REPO_ROOT / "tools" / "t1" / "python"
CORE_ROOT = REPO_ROOT / "core" / "python"
for candidate in (PMX_PIPELINE_ROOT, T1_ROOT, CORE_ROOT):
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)


def _workspace_payload() -> dict:
    return {
        "version": "0.1.0",
        "schema_version": 1,
        "paths": {
            "aiue_repo_root": str(REPO_ROOT),
        },
    }


def _write_zip_fixture(zip_path: Path, *, include_manifest: bool) -> None:
    import zipfile

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_payload = {
        "fixture_id": "family_alpha::lower_body_core_hi",
        "body_family_id": "family_alpha",
        "fixture_scope": "lower_body_core",
        "source_module_ids": ["family_alpha/core_lower_body_hi"],
        "primary_mesh_relative_path": "meshes/lower_body_core_hi.fbx",
        "mesh_format": "fbx",
        "material_bundle_relative_root": "materials",
        "texture_relative_paths": [],
        "fusion_recipe_id": "houdini_recipe::family_alpha::lower_body_core_v1",
        "rig_profile_id": "rig_profile::family_alpha::pending",
        "material_profile_id": "material_profile::family_alpha::scan_source_v1",
        "exporter": {
            "tool": "houdini",
            "version": "20.5",
            "network": "/obj/aiue_body_platform/c2_lower_body_core",
        },
        "coordinate_system": {
            "linear_unit": "cm",
            "up_axis": "z",
            "forward_axis": "x",
        },
        "quality": {
            "topology_state": "scan_raw_cleaned",
            "uv_state": "source_preserved",
            "watertight_expected": False,
            "runtime_ready": False,
        },
    }
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("meshes/lower_body_core_hi.fbx", "fixture-fbx")
        if include_manifest:
            archive.writestr(
                "canonical_fusion_fixture_manifest.json",
                json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n",
            )


def test_provider_ready_handoff_check_passes_for_manifested_fixture(tmp_path: Path):
    workspace_path = tmp_path / "pipeline_workspace.local.json"
    fixture_zip = tmp_path / "scan-model-hi.zip"
    output_root = tmp_path / "verification" / "handoff_check"
    latest_report_path = tmp_path / "verification" / "latest_c2_provider_ready_source_handoff_check_report.json"
    latest_provider_path = tmp_path / "body_platform" / "latest" / "converted_model_provider_provider_ready_check_v0_1.json"

    workspace_path.write_text(json.dumps(_workspace_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_zip_fixture(fixture_zip, include_manifest=True)

    completed = subprocess.run(
        [
            sys.executable,
            str(PMX_PIPELINE_ROOT / "run_check_c2_provider_ready_source_handoff.py"),
            "--workspace-config",
            str(workspace_path),
            "--fixture-zip",
            str(fixture_zip),
            "--output-root",
            str(output_root),
            "--latest-report-path",
            str(latest_report_path),
            "--latest-provider-path",
            str(latest_provider_path),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(latest_report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["bodypaint_intake_summary"]["provider_ready_source_handoff"] is True
    assert payload["bodypaint_intake_summary"]["ready_for_bodypaint"] is True
    assert payload["bodypaint_intake_summary"]["blocking_issue_ids"] == []
    assert payload["package_inventory"]["discovered_mesh_count"] == 1
    assert payload["provider_preview"]["status"] == "ready"
    assert payload["provider_preview"]["consumer_hints"]["ready_for_bodypaint"] is True
    checklist = {item["item_id"]: item for item in payload["checklist"]}
    assert checklist["manifest_present"]["status"] == "pass"
    assert payload["next_actions"] == []
    provider_payload = json.loads(latest_provider_path.read_text(encoding="utf-8"))
    assert provider_payload["status"] == "ready"


def test_provider_ready_handoff_check_flags_missing_manifest(tmp_path: Path):
    workspace_path = tmp_path / "pipeline_workspace.local.json"
    fixture_zip = tmp_path / "scan-model-hi.zip"
    output_root = tmp_path / "verification" / "handoff_check"
    latest_report_path = tmp_path / "verification" / "latest_c2_provider_ready_source_handoff_check_report.json"
    latest_provider_path = tmp_path / "body_platform" / "latest" / "converted_model_provider_provider_ready_check_v0_1.json"

    workspace_path.write_text(json.dumps(_workspace_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_zip_fixture(fixture_zip, include_manifest=False)

    completed = subprocess.run(
        [
            sys.executable,
            str(PMX_PIPELINE_ROOT / "run_check_c2_provider_ready_source_handoff.py"),
            "--workspace-config",
            str(workspace_path),
            "--fixture-zip",
            str(fixture_zip),
            "--output-root",
            str(output_root),
            "--latest-report-path",
            str(latest_report_path),
            "--latest-provider-path",
            str(latest_provider_path),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(latest_report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "attention"
    assert any(item["id"] == "c2_manifest_missing" for item in payload["failed_requirements"])
    assert payload["bodypaint_intake_summary"]["provider_ready_source_handoff"] is False
    assert payload["bodypaint_intake_summary"]["ready_for_bodypaint"] is False
    assert "c2_manifest_missing" in payload["bodypaint_intake_summary"]["blocking_issue_ids"]
    checklist = {item["item_id"]: item for item in payload["checklist"]}
    assert checklist["manifest_present"]["status"] == "attention"
    assert any(item["issue_id"] == "c2_manifest_missing" for item in payload["next_actions"])
    provider_payload = json.loads(latest_provider_path.read_text(encoding="utf-8"))
    assert provider_payload["status"] == "missing_manifest"


def test_manifest_example_contains_schema_required_fields():
    manifest_path = REPO_ROOT / "examples" / "body_platform" / "canonical_fusion_fixture_manifest.example.json"
    schema_path = REPO_ROOT / "schemas" / "canonical_fusion_fixture_manifest.v0.schema.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    required = list(schema.get("required") or [])
    for key in required:
        assert key in manifest, key
    assert manifest["exporter"]["tool"] == "houdini"
    assert manifest["coordinate_system"]["linear_unit"] == "cm"
    assert manifest["coordinate_system"]["up_axis"] == "z"
