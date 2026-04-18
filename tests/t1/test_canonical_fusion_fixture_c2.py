from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PMX_PIPELINE_ROOT = REPO_ROOT / "workflows" / "pmx_pipeline"
T1_ROOT = REPO_ROOT / "tools" / "t1" / "python"
CORE_ROOT = REPO_ROOT / "core" / "python"
for candidate in (PMX_PIPELINE_ROOT, T1_ROOT, CORE_ROOT):
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)

from aiue_t1.body_platform import build_body_platform_quality_summary  # noqa: E402
from aiue_t1.report_index import build_report_index  # noqa: E402


def _workspace_payload() -> dict:
    return {
        "version": "0.1.0",
        "schema_version": 1,
        "paths": {
            "aiue_repo_root": str(REPO_ROOT),
        },
    }


def _c1_source_report() -> dict:
    return {
        "gate_id": "parametric_body_contract_c1",
        "status": "pass",
        "body_family_id": "family_alpha",
        "contract_id": "family_alpha::parametric_body_contract_c1",
        "source_inventory_summary": {
            "source_root": "C:/fixture/body_source",
            "counts": {
                "module_count": 5,
                "classified_module_count": 5,
                "family_count": 1,
                "candidate_fixture_family_count": 1,
            },
            "module_kind_counts": {
                "head": 1,
                "hair": 1,
                "bust_variant": 1,
                "core_torso_arm": 1,
                "leg_profile": 1,
            },
            "canonical_fixture_family_id": "family_alpha",
            "per_family_results": [
                {
                    "family_id": "family_alpha",
                    "family_root": "C:/fixture/body_source/family_alpha",
                    "module_count": 5,
                    "classified_module_count": 5,
                    "module_kind_counts": {
                        "head": 1,
                        "hair": 1,
                        "bust_variant": 1,
                        "core_torso_arm": 1,
                        "leg_profile": 1,
                    },
                    "required_axes_present": {
                        "head": True,
                        "bust_variant": True,
                        "leg_profile": True,
                        "core_torso_arm": True,
                    },
                    "optional_axes_present": {"hair": True},
                    "candidate_fixture_family": True,
                }
            ],
        },
    }


def _write_zip_fixture(zip_path: Path, *, include_manifest: bool) -> None:
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


def test_c2_runner_passes_with_manifested_zip_fixture(tmp_path: Path):
    workspace_path = tmp_path / "pipeline_workspace.local.json"
    source_report_path = tmp_path / "latest_parametric_body_contract_c1_report.json"
    fixture_zip = tmp_path / "scan-model-hi.zip"
    output_root = tmp_path / "verification" / "c2_run"
    latest_report_path = tmp_path / "verification" / "latest_canonical_fusion_fixture_c2_report.json"
    latest_provider_path = tmp_path / "body_platform" / "latest" / "converted_model_provider_v0_1.json"

    workspace_path.write_text(json.dumps(_workspace_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    source_report_path.write_text(json.dumps(_c1_source_report(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_zip_fixture(fixture_zip, include_manifest=True)

    completed = subprocess.run(
        [
            sys.executable,
            str(PMX_PIPELINE_ROOT / "run_canonical_fusion_fixture_c2.py"),
            "--workspace-config",
            str(workspace_path),
            "--source-report",
            str(source_report_path),
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
    assert payload["fixture_id"] == "family_alpha::lower_body_core_hi"
    assert payload["canonical_fusion_fixture"]["primary_mesh_format"] == "fbx"
    assert payload["canonical_fusion_fixture"]["manifest_present"] is True
    assert payload["artifacts"]["converted_model_provider_path"].endswith("converted_model_provider.json")
    assert payload["artifacts"]["latest_provider_path"] == str(latest_provider_path)
    provider_payload = json.loads(latest_provider_path.read_text(encoding="utf-8"))
    assert provider_payload["status"] == "ready"
    assert provider_payload["consumer_hints"]["ready_for_bodypaint"] is True
    assert provider_payload["consumer_hints"]["ready_for_ue"] is False


def test_c2_runner_marks_raw_zip_as_attention_when_manifest_is_missing(tmp_path: Path):
    workspace_path = tmp_path / "pipeline_workspace.local.json"
    source_report_path = tmp_path / "latest_parametric_body_contract_c1_report.json"
    fixture_zip = tmp_path / "scan-model-hi.zip"
    output_root = tmp_path / "verification" / "c2_run"
    latest_report_path = tmp_path / "verification" / "latest_canonical_fusion_fixture_c2_report.json"
    latest_provider_path = tmp_path / "body_platform" / "latest" / "converted_model_provider_v0_1.json"

    workspace_path.write_text(json.dumps(_workspace_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    source_report_path.write_text(json.dumps(_c1_source_report(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_zip_fixture(fixture_zip, include_manifest=False)

    completed = subprocess.run(
        [
            sys.executable,
            str(PMX_PIPELINE_ROOT / "run_canonical_fusion_fixture_c2.py"),
            "--workspace-config",
            str(workspace_path),
            "--source-report",
            str(source_report_path),
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
    assert payload["canonical_fusion_fixture"]["manifest_present"] is False
    assert any(item["id"] == "c2_manifest_missing" for item in payload["failed_requirements"])
    provider_payload = json.loads(latest_provider_path.read_text(encoding="utf-8"))
    assert provider_payload["status"] == "missing_manifest"


def test_body_platform_quality_summary_prefers_c2_when_available(tmp_path: Path):
    from tests.t2.helpers import write_fixture_c0_report, write_fixture_c1_report, write_fixture_c2_report

    verification_root = tmp_path / "verification"
    write_fixture_c0_report(verification_root)
    write_fixture_c1_report(verification_root)
    write_fixture_c2_report(verification_root)
    report_index = build_report_index(verification_root)
    summary = build_body_platform_quality_summary(report_index)

    assert summary["gate_id"] == "canonical_fusion_fixture_c2"
    assert summary["status"] == "pass"
    assert summary["fixture_scope"] == "lower_body_core"
    assert summary["fixture_id"] == "family_alpha::lower_body_core_hi"
    assert summary["primary_mesh_format"] == "fbx"
