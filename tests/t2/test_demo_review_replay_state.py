from __future__ import annotations

from pathlib import Path

from aiue_t2.demo_review_replay_state import load_demo_review_replay_state, write_demo_review_replay_run

from tests.t2.helpers import build_fixture_pack


def _invocation(tmp_path: Path, *, request_kind: str) -> dict:
    before_image = tmp_path / f"{request_kind}_before.png"
    after_image = tmp_path / f"{request_kind}_after.png"
    before_image.write_text("fixture", encoding="utf-8")
    after_image.write_text("fixture", encoding="utf-8")
    return {
        "request_json_path": str((tmp_path / f"{request_kind}_request.json").resolve()),
        "result_json_path": str((tmp_path / f"{request_kind}_result.json").resolve()),
        "host_key": "demo",
        "payload": {
            "status": "pass",
            "generated_at_utc": "2026-04-11T09:00:00+00:00",
            "result": {
                "status": "pass",
                "shots": [
                    {
                        "before": {
                            "image_path": str(before_image.resolve()),
                            "subject_screen_coverage": 0.08,
                            "weapon_screen_coverage": 0.01,
                            "line_of_sight_clear": True,
                            "tracked_slot_coverages": {"fx": {"coverage_ratio": 0.0}},
                        },
                        "after": {
                            "image_path": str(after_image.resolve()),
                            "subject_screen_coverage": 0.07,
                            "weapon_screen_coverage": 0.01,
                            "line_of_sight_clear": True,
                            "tracked_slot_coverages": {"fx": {"coverage_ratio": 0.0}},
                        },
                    }
                ],
                "transform_delta": {"distance_delta": 85.0, "yaw_delta": 24.0},
                "native_animation_pose_evaluation": {"pose_changed": True, "changed_bone_count": 7},
                "pose_probe_delta": {"moving_bone_count": 5, "max_location_delta": 123.0},
            },
        },
    }


def test_write_and_load_demo_review_replay_state_roundtrip(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    write_demo_review_replay_run(
        session_manifest_path=pack["session_manifest_path"],
        source_review_state_path=str((tmp_path / "review.json").resolve()),
        session_id="playable_demo_e2_bootstrap",
        selected_package_id="pkg_alpha",
        selected_action_preset_id="showcase_root_translate_and_turn",
        selected_animation_preset_id="MM_Attack_01",
        request_kind="action_preview",
        invocation=_invocation(tmp_path, request_kind="action_preview"),
    )
    loaded = load_demo_review_replay_state(pack["session_manifest_path"])
    assert loaded["status"] == "pass"
    assert loaded["selected_package_id"] == "pkg_alpha"
    assert loaded["last_replay_kind"] == "action_preview"
    assert loaded["package_replay_counts"]["pkg_alpha"] == 1
    assert loaded["last_replays_by_package"]["pkg_alpha"]["action_preview"]["credibility_summary"]["action_motion_verified"] is True


def test_load_demo_review_replay_state_returns_missing_for_absent_file(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    loaded = load_demo_review_replay_state(pack["session_manifest_path"])
    assert loaded["status"] == "missing"
    assert loaded["package_replay_counts"] == {}
