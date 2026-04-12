from __future__ import annotations

import json
from pathlib import Path

from aiue_t1.toy_yard_manifest_artifact_check import (
    build_manifest_artifact_check_report,
    discover_manifest_paths,
    inspect_manifest_artifacts,
)


def test_inspect_manifest_artifacts_flags_external_output_fbx(tmp_path: Path):
    export_root = tmp_path / "export"
    manifest_dir = export_root / "conversion" / "pkg_alpha"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "package_id": "pkg_alpha",
                "sample_id": "sample_alpha",
                "output_fbx": "C:/Users/source/_fbx_out/pkg_alpha/model.fbx",
                "source_file": "C:/Users/source/models/pkg_alpha/model.pmx",
                "textures": [],
            }
        ),
        encoding="utf-8",
    )

    result = inspect_manifest_artifacts(manifest_path, export_root=export_root)

    assert result["status"] == "attention"
    assert "output_fbx_missing" in result["issues"]
    assert "source_file_external_reference" in result["issues"]
    assert result["output_fbx"]["exists"] is False


def test_inspect_manifest_artifacts_passes_for_export_local_files(tmp_path: Path):
    export_root = tmp_path / "export"
    manifest_dir = export_root / "conversion" / "pkg_alpha"
    textures_dir = manifest_dir / "textures"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    textures_dir.mkdir(parents=True, exist_ok=True)
    output_fbx = manifest_dir / "model.fbx"
    source_file = manifest_dir / "model.pmx"
    texture = textures_dir / "diffuse.png"
    output_fbx.write_text("fbx", encoding="utf-8")
    source_file.write_text("pmx", encoding="utf-8")
    texture.write_text("png", encoding="utf-8")
    manifest_path = manifest_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "package_id": "pkg_alpha",
                "sample_id": "sample_alpha",
                "output_fbx": str(output_fbx),
                "source_file": str(source_file),
                "textures": [
                    {
                        "material_name": "Body",
                        "relocated_path": str(texture),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = inspect_manifest_artifacts(manifest_path, export_root=export_root)

    assert result["status"] == "pass"
    assert "output_fbx_missing" not in result["issues"]
    assert result["textures"][0]["chosen_exists"] is True
    assert result["textures"][0]["chosen_in_export_root"] is True


def test_build_manifest_artifact_check_report_aggregates_counts(tmp_path: Path):
    export_root = tmp_path / "export"
    manifest_dir = export_root / "conversion" / "pkg_alpha"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "package_id": "pkg_alpha",
                "sample_id": "sample_alpha",
                "output_fbx": "C:/missing/model.fbx",
                "textures": [],
            }
        ),
        encoding="utf-8",
    )

    payload = build_manifest_artifact_check_report(
        manifest_paths=[manifest_path],
        export_root=export_root,
        source_workspace_config=None,
    )

    assert payload["status"] == "attention"
    assert payload["counts"]["manifest_count"] == 1
    assert payload["counts"]["output_fbx_missing_count"] == 1


def test_discover_manifest_paths_supports_summary_file_entrypoint(tmp_path: Path):
    export_root = tmp_path / "export"
    summary_dir = export_root / "summary"
    conversion_dir = export_root / "conversion" / "pkg_alpha"
    summary_dir.mkdir(parents=True, exist_ok=True)
    conversion_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / "ue_suite_summary.json"
    manifest_path = conversion_dir / "manifest.json"
    summary_path.write_text(json.dumps({"successes": []}), encoding="utf-8")
    manifest_path.write_text(json.dumps({"package_id": "pkg_alpha"}), encoding="utf-8")

    resolved_root, manifest_paths = discover_manifest_paths(summary=summary_path)

    assert resolved_root == export_root.resolve()
    assert manifest_paths == [manifest_path.resolve()]


def test_discover_manifest_paths_supports_summary_directory_entrypoint(tmp_path: Path):
    export_root = tmp_path / "export"
    summary_dir = export_root / "summary"
    conversion_dir = export_root / "conversion" / "pkg_alpha"
    summary_dir.mkdir(parents=True, exist_ok=True)
    conversion_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = conversion_dir / "manifest.json"
    manifest_path.write_text(json.dumps({"package_id": "pkg_alpha"}), encoding="utf-8")

    resolved_root, manifest_paths = discover_manifest_paths(summary=summary_dir)

    assert resolved_root == export_root.resolve()
    assert manifest_paths == [manifest_path.resolve()]
