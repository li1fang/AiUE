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

from aiue_t1.converted_model_provider import build_converted_model_provider_from_c2_report  # noqa: E402


def _build_c2_report(
    tmp_path: Path,
    *,
    status: str = "pass",
    manifest_exists: bool = True,
    runtime_ready: bool = False,
) -> dict:
    fixture_root = tmp_path / "fixture"
    mesh_path = fixture_root / "meshes" / "lower_body_core_hi.fbx"
    manifest_path = fixture_root / "canonical_fusion_fixture_manifest.json"
    material_root = fixture_root / "materials"
    mesh_path.parent.mkdir(parents=True, exist_ok=True)
    mesh_path.write_text("fixture-fbx", encoding="utf-8")
    material_root.mkdir(parents=True, exist_ok=True)
    (material_root / "body_diffuse.png").write_text("png", encoding="utf-8")
    if manifest_exists:
        manifest_path.write_text("{}", encoding="utf-8")

    return {
        "gate_id": "canonical_fusion_fixture_c2",
        "status": status,
        "generated_at_utc": "2026-04-18T08:30:00Z",
        "body_family_id": "family_alpha",
        "fixture_id": "family_alpha::lower_body_core_hi",
        "canonical_fusion_fixture": {
            "fixture_id": "family_alpha::lower_body_core_hi",
            "body_family_id": "family_alpha",
            "primary_mesh_abs_path": str(mesh_path.resolve()),
            "primary_mesh_relative_path": "meshes/lower_body_core_hi.fbx",
            "primary_mesh_format": "fbx",
            "manifest_path": str(manifest_path.resolve()),
            "manifest_present": manifest_exists,
            "source_root": str(fixture_root.resolve()),
            "source_module_ids": ["family_alpha/core_lower_body_hi"],
            "material_bundle_relative_root": "materials",
            "discovered_texture_relative_paths": ["body_diffuse.png"],
            "exporter": {
                "tool": "houdini",
                "version": "20.5",
            },
            "quality": {
                "runtime_ready": runtime_ready,
            },
        },
        "source_inventory_summary": {
            "source_root": str((tmp_path / "source_inventory").resolve()),
        },
        "failed_requirements": [],
    }


def test_provider_marks_passing_c2_fixture_ready_for_bodypaint(tmp_path: Path):
    report_source_path = tmp_path / "verification" / "canonical_fusion_fixture_report.json"
    report_source_path.parent.mkdir(parents=True, exist_ok=True)
    report_source_path.write_text("{}", encoding="utf-8")
    provider = build_converted_model_provider_from_c2_report(
        _build_c2_report(tmp_path, manifest_exists=True, runtime_ready=False),
        report_source_path=report_source_path,
    )

    assert provider["version"] == "aiue-converted-model-provider-0.1"
    assert provider["status"] == "ready"
    assert provider["consumer_hints"]["ready_for_bodypaint"] is True
    assert provider["consumer_hints"]["ready_for_ue"] is False
    assert provider["identity"]["package_id"] == "family_alpha::lower_body_core_hi"
    assert provider["primary_asset"]["format"] == "fbx"
    assert any(item["role"] == "upstream_manifest" for item in provider["companions"])
    assert any(item["role"] == "textures_root" for item in provider["companions"])
    assert any(item["role"] == "body_platform_report" for item in provider["companions"])
    assert "converted_model_not_runtime_ready_for_ue" in provider["warnings"]


def test_provider_marks_missing_manifest_when_mesh_exists_but_manifest_is_absent(tmp_path: Path):
    provider = build_converted_model_provider_from_c2_report(
        _build_c2_report(tmp_path, manifest_exists=False),
    )

    assert provider["status"] == "missing_manifest"
    assert provider["consumer_hints"]["ready_for_bodypaint"] is False
    assert provider["consumer_hints"]["ready_for_ue"] is False


def test_resolver_writes_not_found_provider_when_c2_report_is_missing(tmp_path: Path):
    workspace_path = tmp_path / "pipeline_workspace.local.json"
    output_path = tmp_path / "resolved" / "converted_model_provider.json"
    latest_output_path = tmp_path / "resolved" / "latest_converted_model_provider.json"
    workspace_path.write_text(
        json.dumps(
            {
                "version": "0.1.0",
                "schema_version": 1,
                "paths": {
                    "aiue_repo_root": str(REPO_ROOT),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(PMX_PIPELINE_ROOT / "run_resolve_converted_model_provider_v0.py"),
            "--workspace-config",
            str(workspace_path),
            "--c2-report",
            str(tmp_path / "missing_c2_report.json"),
            "--output-path",
            str(output_path),
            "--latest-output-path",
            str(latest_output_path),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "not_found"
    assert payload["consumer_hints"]["ready_for_bodypaint"] is False
    assert "c2 report not found" in payload["notes"][0]
    latest_payload = json.loads(latest_output_path.read_text(encoding="utf-8"))
    assert latest_payload["status"] == "not_found"
