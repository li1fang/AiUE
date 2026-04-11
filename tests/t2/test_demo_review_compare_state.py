from __future__ import annotations

from pathlib import Path

from aiue_t2.demo_review_compare_state import (
    build_demo_review_compare_focus,
    load_demo_review_compare_state,
    write_demo_review_compare_state,
)
from aiue_t2.demo_review_history_state import load_demo_review_history_state, write_demo_review_history_event

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
        "generated_at_utc": "2026-04-11T10:00:00+00:00" if request_kind == "action_preview" else "2026-04-11T10:01:00+00:00",
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
            "warning_flags": ["fx_not_visible"] if request_kind == "animation_preview" else [],
        },
    }


def test_write_and_load_demo_review_compare_state_roundtrip(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    for request_kind in ("action_preview", "animation_preview"):
        write_demo_review_history_event(
            session_manifest_path=pack["session_manifest_path"],
            source_review_state_path=str((tmp_path / "review.json").resolve()),
            source_replay_state_path=str((tmp_path / "replay.json").resolve()),
            session_id="playable_demo_e2_bootstrap",
            selected_package_id="pkg_alpha",
            request_kind=request_kind,
            replay_run=_replay_run(tmp_path, request_kind=request_kind),
        )
    history_state = load_demo_review_history_state(pack["session_manifest_path"])
    write_demo_review_compare_state(
        session_manifest_path=pack["session_manifest_path"],
        demo_review_history_state=history_state,
    )
    loaded = load_demo_review_compare_state(pack["session_manifest_path"])
    assert loaded["status"] == "pass"
    assert loaded["counts"]["package_count"] == 1
    assert loaded["counts"]["packages_with_compare_pair"] == 1
    assert loaded["package_compares"][0]["compare_ready"] is True


def test_load_demo_review_compare_state_builds_from_history_when_artifact_missing(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    for request_kind in ("action_preview", "animation_preview"):
        write_demo_review_history_event(
            session_manifest_path=pack["session_manifest_path"],
            source_review_state_path=str((tmp_path / "review.json").resolve()),
            source_replay_state_path=str((tmp_path / "replay.json").resolve()),
            session_id="playable_demo_e2_bootstrap",
            selected_package_id="pkg_alpha",
            request_kind=request_kind,
            replay_run=_replay_run(tmp_path, request_kind=request_kind),
        )
    history_state = load_demo_review_history_state(pack["session_manifest_path"])
    loaded = load_demo_review_compare_state(
        pack["session_manifest_path"],
        demo_review_history_state=history_state,
    )
    assert loaded["status"] == "pass"
    assert loaded["persisted"] is False
    assert loaded["counts"]["packages_with_compare_pair"] == 1


def test_build_demo_review_compare_focus_prefers_selected_package(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    for request_kind in ("action_preview", "animation_preview"):
        write_demo_review_history_event(
            session_manifest_path=pack["session_manifest_path"],
            source_review_state_path=str((tmp_path / "review.json").resolve()),
            source_replay_state_path=str((tmp_path / "replay.json").resolve()),
            session_id="playable_demo_e2_bootstrap",
            selected_package_id="pkg_alpha",
            request_kind=request_kind,
            replay_run=_replay_run(tmp_path, request_kind=request_kind),
        )
    history_state = load_demo_review_history_state(pack["session_manifest_path"])
    compare_state = load_demo_review_compare_state(
        pack["session_manifest_path"],
        demo_review_history_state=history_state,
    )
    focus = build_demo_review_compare_focus(compare_state, selected_package_id="pkg_alpha")
    assert focus["status"] == "pass"
    assert focus["compare_ready"] is True
    assert focus["replay_kinds"] == ["action_preview", "animation_preview"]
    assert focus["latest_action_event"]["request_kind"] == "action_preview"
    assert focus["latest_animation_event"]["request_kind"] == "animation_preview"


def test_build_demo_review_compare_focus_can_select_older_pair(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    for generated_at_utc, request_kind in (
        ("2026-04-11T10:00:00+00:00", "action_preview"),
        ("2026-04-11T10:01:00+00:00", "animation_preview"),
        ("2026-04-11T10:02:00+00:00", "action_preview"),
        ("2026-04-11T10:03:00+00:00", "animation_preview"),
    ):
        replay_run = _replay_run(tmp_path, request_kind=request_kind)
        replay_run["generated_at_utc"] = generated_at_utc
        write_demo_review_history_event(
            session_manifest_path=pack["session_manifest_path"],
            source_review_state_path=str((tmp_path / "review.json").resolve()),
            source_replay_state_path=str((tmp_path / "replay.json").resolve()),
            session_id="playable_demo_e2_bootstrap",
            selected_package_id="pkg_alpha",
            request_kind=request_kind,
            replay_run=replay_run,
        )
    history_state = load_demo_review_history_state(pack["session_manifest_path"])
    compare_state = load_demo_review_compare_state(
        pack["session_manifest_path"],
        demo_review_history_state=history_state,
    )
    focus = build_demo_review_compare_focus(compare_state, selected_package_id="pkg_alpha", selected_pair_index=1)
    assert focus["status"] == "pass"
    assert focus["available_pair_count"] == 2
    assert focus["selected_pair_index"] == 1
    assert focus["latest_pair_generated_at_utc"] == "2026-04-11T10:01:00+00:00"
