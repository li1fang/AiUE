from __future__ import annotations

import json
import sys
from pathlib import Path


PMX_PIPELINE_ROOT = Path(__file__).resolve().parents[2] / "workflows" / "pmx_pipeline"
if str(PMX_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PMX_PIPELINE_ROOT))

from run_demo_gate_d1 import build_local_manifest_index, resolve_registry_path
from run_editor_gate_g1 import resolve_equipment_report_path, resolve_summary_path
from toy_yard_view import (
    build_toy_yard_manifest_index,
    resolve_toy_yard_equipment_report_path,
    resolve_toy_yard_registry_path,
    resolve_toy_yard_summary_path,
)


def _workspace(view_root: Path) -> dict:
    return {
        "paths": {
            "toy_yard_pmx_view_root": str(view_root),
            "auto_ue_cli_output_root": str(view_root / "_missing_auto"),
            "conversion_root": str(view_root / "_missing_conversion_root"),
        }
    }


def test_toy_yard_view_resolution_prefers_export_root(tmp_path):
    summary_dir = tmp_path / "summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    equipment_report = summary_dir / "ue_equipment_assets_report.local.json"
    suite_summary = summary_dir / "ue_suite_summary.json"
    registry = summary_dir / "ue_equipment_registry.json"

    equipment_report.write_text(json.dumps({"registry_json_path": str(registry)}), encoding="utf-8")
    suite_summary.write_text(json.dumps({"successes": []}), encoding="utf-8")
    registry.write_text(json.dumps({"package_index": {}}), encoding="utf-8")

    workspace = _workspace(tmp_path)

    resolved_equipment = resolve_equipment_report_path(workspace, None)
    resolved_summary = resolve_summary_path(workspace, resolved_equipment, {}, None)
    resolved_registry = resolve_registry_path({}, resolved_summary, None, workspace=workspace)

    assert resolved_equipment == equipment_report.resolve()
    assert resolved_summary == suite_summary.resolve()
    assert resolved_registry == registry.resolve()


def test_build_local_manifest_index_works_with_toy_yard_export_shape(tmp_path):
    summary_dir = tmp_path / "summary"
    conversion_dir = tmp_path / "conversion" / "pkg_alpha"
    summary_dir.mkdir(parents=True, exist_ok=True)
    conversion_dir.mkdir(parents=True, exist_ok=True)

    summary_path = summary_dir / "ue_suite_summary.json"
    manifest_path = conversion_dir / "manifest.json"
    summary_path.write_text(json.dumps({"successes": []}), encoding="utf-8")
    manifest_path.write_text(json.dumps({"package_id": "pkg_alpha"}), encoding="utf-8")

    conversion_root, manifest_index = build_local_manifest_index(summary_path)

    assert conversion_root == (tmp_path / "conversion").resolve()
    assert manifest_index["pkg_alpha"] == manifest_path.resolve()


def test_toy_yard_view_helpers_resolve_summary_registry_and_report(tmp_path):
    summary_dir = tmp_path / "summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / "ue_suite_summary.json"
    registry_path = summary_dir / "ue_equipment_registry.json"
    report_path = summary_dir / "ue_equipment_assets_report.local.json"
    summary_path.write_text(json.dumps({"successes": []}), encoding="utf-8")
    registry_path.write_text(json.dumps({"package_index": {}}), encoding="utf-8")
    report_path.write_text(json.dumps({"suite_name": "toy-yard:test"}), encoding="utf-8")

    workspace = _workspace(tmp_path)

    assert resolve_toy_yard_summary_path(workspace) == summary_path.resolve()
    assert resolve_toy_yard_registry_path(workspace) == registry_path.resolve()
    assert resolve_toy_yard_equipment_report_path(workspace) == report_path.resolve()


def test_build_toy_yard_manifest_index_ignores_invalid_manifest_json(tmp_path):
    conversion_dir = tmp_path / "conversion"
    valid_dir = conversion_dir / "pkg_alpha"
    invalid_dir = conversion_dir / "pkg_broken"
    valid_dir.mkdir(parents=True, exist_ok=True)
    invalid_dir.mkdir(parents=True, exist_ok=True)
    summary_dir = tmp_path / "summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / "ue_suite_summary.json"
    summary_path.write_text(json.dumps({"successes": []}), encoding="utf-8")
    valid_manifest = valid_dir / "manifest.json"
    invalid_manifest = invalid_dir / "manifest.json"
    valid_manifest.write_text(json.dumps({"package_id": "pkg_alpha"}), encoding="utf-8")
    invalid_manifest.write_text("{not-json", encoding="utf-8")

    conversion_root, manifest_index = build_toy_yard_manifest_index(summary_path)

    assert conversion_root == conversion_dir.resolve()
    assert manifest_index == {"pkg_alpha": valid_manifest.resolve()}
