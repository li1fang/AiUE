from __future__ import annotations

import json
import sys
from pathlib import Path


PMX_PIPELINE_ROOT = Path(__file__).resolve().parents[2] / "workflows" / "pmx_pipeline"
if str(PMX_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PMX_PIPELINE_ROOT))

from run_motion_result_import_readiness_m1_5 import evaluate_iteration_readiness  # noqa: E402


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _make_green_iteration(tmp_path: Path) -> dict:
    manifest_path = tmp_path / "packet" / "manifest.json"
    preview_result_path = tmp_path / "preview" / "result.json"
    before_image_path = tmp_path / "preview" / "before.png"
    after_image_path = tmp_path / "preview" / "after.png"
    import_action_path = tmp_path / "motion" / "import_motion_packet.action.json"
    preview_action_path = tmp_path / "motion" / "animation_preview.action.json"
    motion_import_report_path = tmp_path / "packet" / "motion_import_report.local.json"
    motion_preview_report_path = tmp_path / "packet" / "motion_preview_report.local.json"
    for path in (
        manifest_path,
        preview_result_path,
        before_image_path,
        after_image_path,
        import_action_path,
        preview_action_path,
        motion_import_report_path,
        motion_preview_report_path,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ok", encoding="utf-8")

    report_path = tmp_path / "verification" / "iteration_01_latest_motion_shadow_packet_trial_m0_5_report.json"
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
                "generated_assets": {
                    "animation_asset_path": "/Game/PMXPipeline/MotionPackets/Source/AN_Demo",
                    "retargeted_animation_asset_path": "/Game/RTG_AN_Demo",
                    "import_mode": "source_bundle_fallback",
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
                    "reason": "motion_consumed_and_previewed",
                },
                "artifacts": {
                    "import_action_path": str(import_action_path),
                    "preview_action_path": str(preview_action_path),
                    "motion_import_report_path": str(motion_import_report_path),
                    "motion_preview_report_path": str(motion_preview_report_path),
                },
            }
        },
    )
    return {
        "iteration_index": 1,
        "artifacts": {
            "report_path": str(report_path),
        },
    }


def test_evaluate_iteration_readiness_accepts_import_ready_result(tmp_path):
    iteration_payload = _make_green_iteration(tmp_path)

    result = evaluate_iteration_readiness(iteration_payload, "pkg_demo", "sample_demo")

    assert result["status"] == "pass"
    assert result["artifact_presence"]["packet_manifest"] is True
    assert result["artifact_presence"]["motion_import_report"] is True
    assert result["failed_requirements"] == []


def test_evaluate_iteration_readiness_flags_drift_and_missing_artifacts(tmp_path):
    iteration_payload = _make_green_iteration(tmp_path)
    report_path = Path(iteration_payload["artifacts"]["report_path"])
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    report_payload["consumer_result"]["packet_ref"]["package_id"] = "pkg_other"
    report_payload["consumer_result"]["communication_signal"]["owner"] = "aiue"
    report_payload["consumer_result"]["preview_evidence"]["before_image_path"] = str(tmp_path / "missing_before.png")
    _write_json(report_path, report_payload)

    result = evaluate_iteration_readiness(iteration_payload, "pkg_demo", "sample_demo")
    failed_ids = {item["id"] for item in result["failed_requirements"]}

    assert result["status"] == "fail"
    assert "m1_5_package_id_drift" in failed_ids
    assert "m1_5_owner_not_none" in failed_ids
    assert "m1_5_preview_artifact_missing_before_image_path" in failed_ids
