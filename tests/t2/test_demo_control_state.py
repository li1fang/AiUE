from __future__ import annotations

from pathlib import Path

from aiue_t2.demo_control_state import (
    build_control_run_summary,
    build_credibility_summary,
    load_demo_control_state,
    write_demo_control_run,
)

from tests.t2.helpers import FIXTURE_ROOT, build_fixture_e2_session


def _image_path(name: str) -> str:
    return str((FIXTURE_ROOT / "images" / name).resolve())


def _host_payload(*, request_kind: str) -> dict:
    shot = {
        "before": {
            "image_path": _image_path("front.ppm"),
            "subject_screen_coverage": 0.08,
            "weapon_screen_coverage": 0.01,
            "line_of_sight_clear": True,
            "tracked_slot_coverages": {"fx": {"coverage_ratio": 0.005}},
        },
        "after": {
            "image_path": _image_path("side.ppm"),
            "subject_screen_coverage": 0.07,
            "weapon_screen_coverage": 0.01,
            "line_of_sight_clear": True,
            "tracked_slot_coverages": {"fx": {"coverage_ratio": 0.004}},
        },
    }
    if request_kind == "action_preview":
        result = {
            "status": "pass",
            "shots": [shot],
            "transform_delta": {"distance_delta": 85.0, "yaw_delta": 24.0},
        }
    else:
        result = {
            "status": "pass",
            "shots": [shot],
            "native_animation_pose_evaluation": {"pose_changed": True, "changed_bone_count": 12},
            "pose_probe_delta": {"moving_bone_count": 8, "max_location_delta": 123.0},
        }
    return {"status": "pass", "generated_at_utc": "2026-04-11T07:00:00+00:00", "result": result}


def test_build_credibility_summary_verifies_action_and_animation():
    action_summary = build_credibility_summary(
        request_kind="action_preview",
        host_payload=_host_payload(request_kind="action_preview"),
    )
    animation_summary = build_credibility_summary(
        request_kind="animation_preview",
        host_payload=_host_payload(request_kind="animation_preview"),
    )

    assert action_summary["subject_visible"] is True
    assert action_summary["action_motion_verified"] is True
    assert action_summary["animation_pose_verified"] is False
    assert animation_summary["subject_visible"] is True
    assert animation_summary["action_motion_verified"] is False
    assert animation_summary["animation_pose_verified"] is True


def test_build_control_run_summary_collects_key_paths_and_credibility():
    summary = build_control_run_summary(
        request_kind="action_preview",
        operation="invoke",
        selected_package_id="pkg_alpha",
        selected_action_preset_id="showcase_root_translate_and_turn",
        selected_animation_preset_id="MM_Attack_01",
        invocation={
            "request_json_path": str(Path("C:/tmp/action_request.json")),
            "result_json_path": str(Path("C:/tmp/action_result.json")),
            "host_key": "demo",
            "payload": _host_payload(request_kind="action_preview"),
        },
    )

    assert summary["request_kind"] == "action_preview"
    assert summary["operation"] == "invoke"
    assert summary["host_key"] == "demo"
    assert summary["key_image_paths"]["primary_before"].endswith("front.ppm")
    assert summary["credibility_summary"]["action_motion_verified"] is True


def test_write_and_load_demo_control_state_roundtrip(tmp_path: Path):
    session_manifest_path = build_fixture_e2_session(tmp_path)
    control_state = write_demo_control_run(
        session_manifest_path=session_manifest_path,
        session_id="playable_demo_e2_bootstrap",
        selected_package_id="pkg_alpha",
        selected_action_preset_id="showcase_root_translate_and_turn",
        selected_animation_preset_id="MM_Attack_01",
        request_kind="animation_preview",
        operation="invoke",
        invocation={
            "request_json_path": str((tmp_path / "animation_request.json").resolve()),
            "result_json_path": str((tmp_path / "animation_result.json").resolve()),
            "host_key": "demo",
            "payload": _host_payload(request_kind="animation_preview"),
        },
    )

    assert control_state["status"] == "pass"
    assert control_state["selected_package_id"] == "pkg_alpha"
    assert control_state["package_run_counts"]["pkg_alpha"] == 1

    loaded = load_demo_control_state(session_manifest_path)
    assert loaded["status"] == "pass"
    assert loaded["selected_animation_preset_id"] == "MM_Attack_01"
    assert loaded["last_runs_by_package"]["pkg_alpha"]["animation_preview"]["credibility_summary"]["animation_pose_verified"] is True


def test_load_demo_control_state_returns_missing_for_absent_file(tmp_path: Path):
    session_manifest_path = build_fixture_e2_session(tmp_path)
    loaded = load_demo_control_state(session_manifest_path)
    assert loaded["status"] == "missing"
    assert loaded["last_runs_by_package"] == {}
