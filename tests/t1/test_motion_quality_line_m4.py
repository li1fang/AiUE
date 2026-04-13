from __future__ import annotations

import json
import sys
from pathlib import Path


PMX_PIPELINE_ROOT = Path(__file__).resolve().parents[2] / "workflows" / "pmx_pipeline"
if str(PMX_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PMX_PIPELINE_ROOT))

from run_motion_quality_line_m4 import evaluate_package_quality  # noqa: E402


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_text(path: Path, content: str = "ok") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_green_package(tmp_path: Path) -> dict:
    manifest_path = _write_json(
        tmp_path / "clips" / "pkg_demo" / "manifest.json",
        {
            "duration_sec": 3.0,
            "fps": 30,
            "frame_count": 90,
        },
    )
    before_image_path = _write_text(tmp_path / "preview" / "before.png")
    after_image_path = _write_text(tmp_path / "preview" / "after.png")
    preview_action_path = _write_json(
        tmp_path / "preview" / "animation_preview.action.json",
        {
            "status": "pass",
            "success": True,
            "warnings": ["animation_blueprint_library_unavailable"],
            "result": {
                "status": "pass",
                "package_id": "pkg_demo",
                "sample_id": "sample_demo",
                "animation_compatibility": {
                    "compatible": True,
                },
                "direct_animation_compatibility": {
                    "compatible": False,
                },
                "retarget_generation": {
                    "success": True,
                    "exact_named_mapped_chain_names": [
                        "root",
                        "Spine",
                        "LeftClavicle",
                        "RightClavicle",
                        "LeftArm",
                        "RightArm",
                    ],
                },
                "native_animation_pose_evaluation": {
                    "available": True,
                    "success": True,
                    "pose_changed": True,
                    "changed_bone_count": 2,
                    "max_location_delta": 16.4,
                },
            },
        },
    )
    consumer_result_report_path = _write_json(
        tmp_path / "verification" / "latest_motion_shadow_packet_trial_m0_5_report.json",
        {
            "consumer_result": {
                "status": "pass",
            }
        },
    )
    return {
        "package_id": "pkg_demo",
        "sample_id": "sample_demo",
        "scenario_id": "scenario_demo",
        "import_ready_artifacts": {
            "consumer_result_report_path": str(consumer_result_report_path),
            "preview_result_json_path": str(preview_action_path),
            "packet_manifest_path": str(manifest_path),
            "before_image_path": str(before_image_path),
            "after_image_path": str(after_image_path),
        },
    }


def test_evaluate_package_quality_accepts_green_package(tmp_path: Path):
    result = evaluate_package_quality(_make_green_package(tmp_path))

    assert result["status"] == "pass"
    assert result["retarget_success"] is True
    assert result["native_pose_changed"] is True


def test_evaluate_package_quality_flags_quality_regressions(tmp_path: Path):
    package_result = _make_green_package(tmp_path)
    preview_action_path = Path(package_result["import_ready_artifacts"]["preview_result_json_path"])
    payload = json.loads(preview_action_path.read_text(encoding="utf-8"))
    payload["warnings"] = ["unexpected_warning"]
    payload["result"]["retarget_generation"]["exact_named_mapped_chain_names"] = ["root"]
    payload["result"]["native_animation_pose_evaluation"]["changed_bone_count"] = 0
    payload["result"]["native_animation_pose_evaluation"]["max_location_delta"] = 0.1
    _write_json(preview_action_path, payload)

    result = evaluate_package_quality(package_result)
    failed_ids = {item["id"] for item in result["failed_requirements"]}

    assert result["status"] == "fail"
    assert "m4_required_retarget_chains_missing" in failed_ids
    assert "m4_changed_bone_count_too_low" in failed_ids
    assert "m4_location_delta_too_low" in failed_ids
    assert "m4_unexpected_action_warnings" in failed_ids
