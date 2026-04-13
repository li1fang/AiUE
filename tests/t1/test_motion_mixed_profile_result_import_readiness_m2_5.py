from __future__ import annotations

import json
import sys
from pathlib import Path


PMX_PIPELINE_ROOT = Path(__file__).resolve().parents[2] / "workflows" / "pmx_pipeline"
if str(PMX_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PMX_PIPELINE_ROOT))

from run_motion_mixed_profile_result_import_readiness_m2_5 import evaluate_package_import_readiness  # noqa: E402


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_text(path: Path, content: str = "ok") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_green_package_result(tmp_path: Path) -> dict:
    manifest_path = tmp_path / "clips" / "pkg_demo" / "manifest.json"
    _write_json(
        manifest_path,
        {
            "package_id": "pkg_demo",
            "sample_id": "sample_demo",
            "scenario_id": "scenario_demo",
        },
    )
    preview_result_path = _write_text(tmp_path / "preview" / "result.json")
    before_image_path = _write_text(tmp_path / "preview" / "before.png")
    after_image_path = _write_text(tmp_path / "preview" / "after.png")
    import_action_path = _write_text(tmp_path / "motion" / "import_motion_packet.action.json")
    preview_action_path = _write_text(tmp_path / "motion" / "animation_preview.action.json")
    motion_import_report_path = _write_text(tmp_path / "packet" / "motion_import_report.local.json")
    motion_preview_report_path = _write_text(tmp_path / "packet" / "motion_preview_report.local.json")
    consumer_request_path = _write_text(tmp_path / "packet" / "motion_consumer_request_v0.json")
    consumer_result_path = _write_text(tmp_path / "packet" / "motion_consumer_result_v0.json")
    consumer_context_path = _write_text(tmp_path / "packet" / "motion_consumer_context.json")
    consumer_state_path = _write_text(tmp_path / "packet" / "motion_consumer_state.json")

    report_path = tmp_path / "verification" / "pkg_demo_latest_motion_shadow_packet_trial_m0_5_report.json"
    _write_json(
        report_path,
        {
            "consumer_result": {
                "schema_version": "motion_consumer_result_v0",
                "status": "pass",
                "operation": "animation_preview",
                "packet_ref": {
                    "packet_manifest_path": str(manifest_path),
                    "package_id": "pkg_demo",
                    "sample_id": "sample_demo",
                },
                "preview_evidence": {
                    "result_json_path": str(preview_result_path),
                    "before_image_path": str(before_image_path),
                    "after_image_path": str(after_image_path),
                    "subject_visible": True,
                    "pose_changed": True,
                },
                "communication_signal": {
                    "owner": "none",
                    "should_contact_toy_yard": False,
                },
                "artifacts": {
                    "import_action_path": str(import_action_path),
                    "preview_action_path": str(preview_action_path),
                    "motion_import_report_path": str(motion_import_report_path),
                    "motion_preview_report_path": str(motion_preview_report_path),
                },
            },
            "artifacts": {
                "motion_consumer_request_path": str(consumer_request_path),
                "motion_consumer_result_path": str(consumer_result_path),
                "motion_consumer_context_path": str(consumer_context_path),
                "motion_consumer_state_path": str(consumer_state_path),
            },
        },
    )
    return {
        "package_id": "pkg_demo",
        "sample_id": "sample_demo",
        "scenario_id": "scenario_demo",
        "status": "pass",
        "scope_mismatch_only": False,
        "artifacts": {
            "report_path": str(report_path),
        },
    }


def test_evaluate_package_import_readiness_accepts_green_package(tmp_path: Path):
    package_result = _make_green_package_result(tmp_path)

    result = evaluate_package_import_readiness(package_result)

    assert result["status"] == "pass"
    assert result["owner"] == "none"
    assert result["failed_requirements"] == []


def test_evaluate_package_import_readiness_flags_drift_and_missing_artifacts(tmp_path: Path):
    package_result = _make_green_package_result(tmp_path)
    report_path = Path(package_result["artifacts"]["report_path"])
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    report_payload["consumer_result"]["packet_ref"]["sample_id"] = "sample_other"
    report_payload["consumer_result"]["communication_signal"]["owner"] = "aiue"
    report_payload["consumer_result"]["preview_evidence"]["before_image_path"] = str(tmp_path / "missing_before.png")
    _write_json(report_path, report_payload)

    result = evaluate_package_import_readiness(package_result)
    failed_ids = {item["id"] for item in result["failed_requirements"]}

    assert result["status"] == "fail"
    assert "m2_5_sample_id_drift" in failed_ids
    assert "m2_5_owner_not_none" in failed_ids
    assert "m2_5_required_artifact_missing_before_image_path" in failed_ids
