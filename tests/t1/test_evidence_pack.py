from __future__ import annotations

import json
from pathlib import Path

from aiue_core.schema_utils import load_json, write_json
from aiue_t1.evidence_pack import build_evidence_pack


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
REPORT_FIXTURES = FIXTURE_ROOT / "reports"


def _materialize_reports(target_root: Path) -> Path:
    target_root.mkdir(parents=True, exist_ok=True)
    placeholder_root = str(FIXTURE_ROOT).replace("\\", "/")
    for report_path in REPORT_FIXTURES.glob("*.json"):
        payload = load_json(report_path)
        serialized = json.dumps(payload)
        serialized = serialized.replace("__FIXTURE_ROOT__", placeholder_root)
        write_json(target_root / report_path.name, json.loads(serialized))
    return target_root


def test_build_evidence_pack_generates_static_bundle(tmp_path: Path):
    verification_root = _materialize_reports(tmp_path / "verification")
    q5c_report_path = verification_root / "latest_volumetric_inspection_q5c_lite_report.json"
    preview_image_path = str((FIXTURE_ROOT / "images" / "front.ppm").resolve())
    if q5c_report_path.exists():
        q5c_report = load_json(q5c_report_path)
    else:
        q5c_report = {
            "gate_id": "volumetric_inspection_q5c_lite",
            "status": "pass",
            "generated_at_utc": "2026-04-12T00:00:00+00:00",
            "per_package_results": [
                {
                    "package_id": "pkg_alpha",
                    "status": "pass",
                    "artifacts": {},
                }
            ],
        }
    for package in list(q5c_report.get("per_package_results") or []):
        artifacts = dict(package.get("artifacts") or {})
        artifacts["q5c_debug_image_path"] = preview_image_path
        package["artifacts"] = artifacts
    write_json(q5c_report_path, q5c_report)
    output_root = tmp_path / "tooling" / "run"
    latest_root = tmp_path / "tooling" / "latest"
    manifest = build_evidence_pack(
        verification_root=verification_root,
        output_root=output_root,
        latest_root=latest_root,
        repo_root=tmp_path,
    )
    assert (output_root / "index.html").exists()
    assert (output_root / "manifest.json").exists()
    assert (latest_root / "index.html").exists()
    assert manifest["slot_debugger"]["package_count"] == 1
    assert manifest["report_index"]["counts"]["governance_line_reports"] == 1
    assert len(manifest["artifacts"]["preview_images"]) >= 4
    assert any(str(item.get("key") or "").startswith("q5c_") for item in list(manifest["artifacts"]["preview_images"] or []))
    q5c_summary = dict((manifest.get("quality_summaries") or {}).get("q5c_lite") or {})
    assert q5c_summary["status"] == "pass"
    assert q5c_summary["package_count"] >= 1
    assert q5c_summary["diagnostic_class_counts"]
    assert any(str(item.get("artifact_image_relative_path") or "").startswith("images/q5c_") for item in list(q5c_summary.get("packages") or []))
