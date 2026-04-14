from __future__ import annotations

import json
import sys
from pathlib import Path


PMX_PIPELINE_ROOT = Path(__file__).resolve().parents[2] / "workflows" / "pmx_pipeline"
if str(PMX_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PMX_PIPELINE_ROOT))

from run_motion_roundtrip_handoff_m4_5 import (  # noqa: E402
    build_roundtrip_signal,
    classify_roundtrip_owner,
    evaluate_package_handoff,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_text(path: Path, content: str = "ok") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_green_package(tmp_path: Path) -> tuple[dict, dict]:
    required_paths = {
        "packet_manifest_path": _write_text(tmp_path / "packet" / "manifest.json"),
        "consumer_result_report_path": _write_json(tmp_path / "reports" / "consumer_result_report.json", {}),
        "preview_result_json_path": _write_json(tmp_path / "reports" / "animation_preview.action.json", {}),
        "before_image_path": _write_text(tmp_path / "preview" / "before.png"),
        "after_image_path": _write_text(tmp_path / "preview" / "after.png"),
        "import_action_path": _write_text(tmp_path / "actions" / "import.action.json"),
        "preview_action_path": _write_text(tmp_path / "actions" / "preview.action.json"),
        "motion_import_report_path": _write_text(tmp_path / "packet" / "motion_import_report.local.json"),
        "motion_preview_report_path": _write_text(tmp_path / "packet" / "motion_preview_report.local.json"),
        "motion_consumer_request_path": _write_json(
            tmp_path / "packet" / "motion_consumer_request_v0.json",
            {
                "schema_version": "motion_consumer_request_v0",
                "host_key": "demo",
                "motion_asset_root": "/Game/PMXPipeline/MotionPackets",
                "preview_level_path": "/Game/Levels/DefaultLevel",
                "runtime_ready_only": True,
            },
        ),
        "motion_consumer_result_path": _write_json(
            tmp_path / "packet" / "motion_consumer_result_v0.json",
            {
                "schema_version": "motion_consumer_result_v0",
                "operation": "animation_preview",
                "communication_signal": {
                    "owner": "none",
                },
                "generated_assets": {
                    "animation_asset_path": "/Game/A",
                    "retargeted_animation_asset_path": "/Game/B",
                },
                "host_resolution": {
                    "host_key": "demo",
                },
            },
        ),
        "motion_consumer_context_path": _write_text(tmp_path / "packet" / "motion_consumer_context.json"),
        "motion_consumer_state_path": _write_text(tmp_path / "packet" / "motion_consumer_state.json"),
    }

    m2_5_package = {
        "package_id": "pkg_demo",
        "sample_id": "sample_demo",
        "scenario_id": "scenario_demo",
        "status": "pass",
        "import_ready_artifacts": {key: str(value) for key, value in required_paths.items()},
    }
    m4_package = {
        "package_id": "pkg_demo",
        "status": "pass",
        "resolved_animation_compatible": True,
        "retarget_success": True,
        "native_pose_changed": True,
        "native_changed_bone_count": 2,
        "native_max_location_delta": 16.4,
        "required_chain_coverage": ["root", "Spine"],
    }
    return m2_5_package, m4_package


def test_build_roundtrip_signal_pass_case():
    signal = build_roundtrip_signal("pass", "none")

    assert signal["handoff_ready"] is True
    assert signal["owner"] == "none"
    assert signal["recommended_next_node"] == "toyyard_import_aiue_motion_results"


def test_classify_roundtrip_owner_prefers_candidate_problem_owner():
    owner = classify_roundtrip_owner(
        {"status": "pass"},
        {
            "status": "pass",
            "candidate_snapshot": {
                "problem_owner": "toy-yard",
            },
        },
    )

    assert owner == "toy-yard"


def test_evaluate_package_handoff_accepts_green_package(tmp_path: Path):
    m2_5_package, m4_package = _make_green_package(tmp_path)

    result = evaluate_package_handoff(m2_5_package, m4_package)

    assert result["status"] == "pass"
    assert result["import_ready"] is True
    assert result["owner"] == "none"


def test_evaluate_package_handoff_flags_missing_artifact_and_owner(tmp_path: Path):
    m2_5_package, m4_package = _make_green_package(tmp_path)
    consumer_result_path = Path(m2_5_package["import_ready_artifacts"]["motion_consumer_result_path"])
    payload = json.loads(consumer_result_path.read_text(encoding="utf-8"))
    payload["communication_signal"]["owner"] = "aiue"
    _write_json(consumer_result_path, payload)
    Path(m2_5_package["import_ready_artifacts"]["motion_preview_report_path"]).unlink()

    result = evaluate_package_handoff(m2_5_package, m4_package)
    failed_ids = {item["id"] for item in result["failed_requirements"]}

    assert result["status"] == "fail"
    assert "m4_5_required_artifact_missing_motion_preview_report_path" in failed_ids
    assert "m4_5_consumer_owner_not_none" in failed_ids
