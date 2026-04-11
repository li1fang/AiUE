from __future__ import annotations

from pathlib import Path

from aiue_t2.demo_review_history_state import (
    build_demo_review_history_focus,
    load_demo_review_history_state,
    write_demo_review_history_event,
)

from tests.t2.helpers import build_fixture_pack


def _replay_run(tmp_path: Path, *, request_kind: str) -> dict:
    before_image = tmp_path / f"{request_kind}_before.png"
    after_image = tmp_path / f"{request_kind}_after.png"
    before_image.write_text("fixture", encoding="utf-8")
    after_image.write_text("fixture", encoding="utf-8")
    return {
        "request_kind": request_kind,
        "operation": "review_replay",
        "request_json_path": str((tmp_path / f"{request_kind}_request.json").resolve()),
        "result_json_path": str((tmp_path / f"{request_kind}_result.json").resolve()),
        "result_status": "pass",
        "host_key": "demo",
        "generated_at_utc": "2026-04-11T10:00:00+00:00",
        "selected_package_id": "pkg_alpha",
        "selected_action_preset_id": "showcase_root_translate_and_turn",
        "selected_animation_preset_id": "MM_Attack_01",
        "key_image_paths": {
            "primary_before": str(before_image.resolve()),
            "primary_after": str(after_image.resolve()),
        },
        "credibility_summary": {
            "subject_visible": True,
            "before_image_present": True,
            "after_image_present": True,
            "action_motion_verified": request_kind == "action_preview",
            "animation_pose_verified": request_kind == "animation_preview",
            "warning_flags": [],
        },
    }


def test_write_and_load_demo_review_history_state_roundtrip(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    write_demo_review_history_event(
        session_manifest_path=pack["session_manifest_path"],
        source_review_state_path=str((tmp_path / "review.json").resolve()),
        source_replay_state_path=str((tmp_path / "replay.json").resolve()),
        session_id="playable_demo_e2_bootstrap",
        selected_package_id="pkg_alpha",
        request_kind="action_preview",
        replay_run=_replay_run(tmp_path, request_kind="action_preview"),
    )
    loaded = load_demo_review_history_state(pack["session_manifest_path"])
    assert loaded["status"] == "pass"
    assert loaded["package_history_counts"]["pkg_alpha"] == 1
    assert loaded["request_kind_counts"]["action_preview"] == 1
    assert loaded["recent_events"][0]["operation"] == "review_replay"


def test_build_demo_review_history_focus_prefers_selected_package(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    write_demo_review_history_event(
        session_manifest_path=pack["session_manifest_path"],
        source_review_state_path=str((tmp_path / "review.json").resolve()),
        source_replay_state_path=str((tmp_path / "replay.json").resolve()),
        session_id="playable_demo_e2_bootstrap",
        selected_package_id="pkg_alpha",
        request_kind="action_preview",
        replay_run=_replay_run(tmp_path, request_kind="action_preview"),
    )
    write_demo_review_history_event(
        session_manifest_path=pack["session_manifest_path"],
        source_review_state_path=str((tmp_path / "review.json").resolve()),
        source_replay_state_path=str((tmp_path / "replay.json").resolve()),
        session_id="playable_demo_e2_bootstrap",
        selected_package_id="pkg_alpha",
        request_kind="animation_preview",
        replay_run=_replay_run(tmp_path, request_kind="animation_preview"),
    )
    loaded = load_demo_review_history_state(pack["session_manifest_path"])
    focus = build_demo_review_history_focus(loaded, selected_package_id="pkg_alpha")
    assert focus["status"] == "pass"
    assert focus["selected_package_id"] == "pkg_alpha"
    assert focus["event_count"] == 2
    assert focus["replay_kinds"] == ["action_preview", "animation_preview"]


def test_load_demo_review_history_state_returns_missing_for_absent_file(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    loaded = load_demo_review_history_state(pack["session_manifest_path"])
    assert loaded["status"] == "missing"
    assert loaded["recent_events"] == []
