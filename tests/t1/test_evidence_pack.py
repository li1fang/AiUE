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
                    "fit_diagnostic_class": "pass_stable",
                    "embedding_ratio": 0.48,
                    "floating_ratio": 0.02,
                    "penetration_ratio": 0.0,
                    "diagnostic_signals": {
                        "embedding_ratio_below_threshold": False,
                        "floating_ratio_exceeded": False,
                        "penetration_ratio_exceeded": False,
                        "borderline_fit": False,
                    },
                    "threshold_deltas": {
                        "embedding_ratio_delta_to_min": 0.18,
                        "floating_ratio_delta_to_max": -0.18,
                        "penetration_ratio_delta_to_max": -0.02,
                    },
                    "failed_requirements": [],
                    "artifacts": {},
                }
            ],
        }
    for package in list(q5c_report.get("per_package_results") or []):
        artifacts = dict(package.get("artifacts") or {})
        artifacts["q5c_debug_image_path"] = preview_image_path
        package["artifacts"] = artifacts
    write_json(q5c_report_path, q5c_report)
    write_json(
        verification_root / "latest_q5c_lite_contrast_lab_report.json",
        {
            "gate_id": "q5c_lite_contrast_lab",
            "status": "pass",
            "generated_at_utc": "2026-04-12T00:00:00+00:00",
            "per_package_results": [
                {
                    "package_id": "pkg_alpha",
                    "status": "pass",
                    "case_results": [
                        {
                            "case_id": "baseline_current",
                            "artifacts": {
                                "debug_image_path": preview_image_path,
                            },
                        },
                        {
                            "case_id": "closest_fail_reference",
                            "artifacts": {
                                "debug_image_path": preview_image_path,
                            },
                        },
                    ],
                }
            ],
        },
    )
    output_root = tmp_path / "tooling" / "run"
    latest_root = tmp_path / "tooling" / "latest"
    latest_root.mkdir(parents=True, exist_ok=True)
    (latest_root / "stale.txt").write_text("stale", encoding="utf-8")
    manifest = build_evidence_pack(
        verification_root=verification_root,
        output_root=output_root,
        latest_root=latest_root,
        repo_root=tmp_path,
    )
    assert (output_root / "index.html").exists()
    assert (output_root / "manifest.json").exists()
    assert (latest_root / "index.html").exists()
    assert not (latest_root / "stale.txt").exists()
    assert manifest["slot_debugger"]["package_count"] == 1
    assert manifest["report_index"]["counts"]["governance_line_reports"] == 1
    assert len(manifest["artifacts"]["preview_images"]) >= 4
    assert any(str(item.get("key") or "").startswith("q5c_") for item in list(manifest["artifacts"]["preview_images"] or []))
    assert any(str(item.get("key") or "").startswith("q5c_contrast_") for item in list(manifest["artifacts"]["preview_images"] or []))
    q5c_summary = dict((manifest.get("quality_summaries") or {}).get("q5c_lite") or {})
    assert q5c_summary["status"] == "pass"
    assert q5c_summary["package_count"] >= 1
    assert q5c_summary["diagnostic_class_counts"]
    assert q5c_summary["risk_band_counts"]["watch"] >= 1
    assert q5c_summary["highest_risk_band"] == "watch"
    assert q5c_summary["watchlist_count"] >= 1
    assert "pkg_alpha" in q5c_summary["watchlist_package_ids"]
    assert q5c_summary["focus_package_id"]
    assert q5c_summary["focus_metric"]
    assert any(str(item.get("artifact_image_relative_path") or "").startswith("images/q5c_") for item in list(q5c_summary.get("packages") or []))
