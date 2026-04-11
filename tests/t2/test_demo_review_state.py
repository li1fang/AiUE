from __future__ import annotations

from pathlib import Path

from aiue_t2.demo_review_state import build_demo_review_focus, build_demo_review_state, load_demo_review_state, write_demo_review_state

from tests.t2.helpers import build_fixture_pack


def _run_summary(tmp_path: Path, *, request_kind: str) -> dict:
    before_image = tmp_path / f"{request_kind}_before.png"
    after_image = tmp_path / f"{request_kind}_after.png"
    before_image.write_text("fixture", encoding="utf-8")
    after_image.write_text("fixture", encoding="utf-8")
    return {
        "request_kind": request_kind,
        "operation": "invoke",
        "request_json_path": str((tmp_path / f"{request_kind}_request.json").resolve()),
        "result_json_path": str((tmp_path / f"{request_kind}_result.json").resolve()),
        "result_status": "pass",
        "host_key": "demo",
        "generated_at_utc": "2026-04-11T08:00:00+00:00",
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


def test_build_demo_review_state_passes_with_roundtrip_sources(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    action_run = _run_summary(tmp_path, request_kind="action_preview")
    animation_run = _run_summary(tmp_path, request_kind="animation_preview")
    review_state = build_demo_review_state(
        session_manifest_path=pack["session_manifest_path"],
        demo_control_state={
            "status": "pass",
            "control_state_path": str((tmp_path / "control.json").resolve()),
            "last_runs_by_package": {
                "pkg_alpha": {
                    "action_preview": action_run,
                    "animation_preview": animation_run,
                }
            },
        },
        demo_round_state={
            "status": "pass",
            "round_state_path": str((tmp_path / "round.json").resolve()),
            "package_results": [
                {
                    "package_id": "pkg_alpha",
                    "status": "pass",
                    "action_invoke": action_run,
                    "animation_invoke": animation_run,
                }
            ],
        },
    )
    assert review_state["status"] == "pass"
    assert review_state["summary"]["package_count"] == 1
    assert review_state["summary"]["passing_packages"] == 1
    assert review_state["summary"]["action_review_passed"] == 1
    assert review_state["summary"]["animation_review_passed"] == 1
    assert review_state["package_reviews"][0]["status"] == "pass"


def test_write_and_load_demo_review_state_roundtrip(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    action_run = _run_summary(tmp_path, request_kind="action_preview")
    animation_run = _run_summary(tmp_path, request_kind="animation_preview")
    written = write_demo_review_state(
        session_manifest_path=pack["session_manifest_path"],
        demo_control_state={
            "status": "pass",
            "control_state_path": str((tmp_path / "control.json").resolve()),
            "last_runs_by_package": {
                "pkg_alpha": {
                    "action_preview": action_run,
                    "animation_preview": animation_run,
                }
            },
        },
        demo_round_state={
            "status": "pass",
            "round_state_path": str((tmp_path / "round.json").resolve()),
            "package_results": [
                {
                    "package_id": "pkg_alpha",
                    "status": "pass",
                    "action_invoke": action_run,
                    "animation_invoke": animation_run,
                }
            ],
        },
    )
    loaded = load_demo_review_state(pack["session_manifest_path"])
    assert written["status"] == "pass"
    assert loaded["status"] == "pass"
    assert loaded["package_reviews"][0]["action_review"]["status"] == "pass"
    assert loaded["package_reviews"][0]["animation_review"]["status"] == "pass"


def test_build_demo_review_state_is_missing_without_review_sources(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    review_state = build_demo_review_state(session_manifest_path=pack["session_manifest_path"])
    assert review_state["status"] == "missing"
    assert review_state["summary"]["package_count"] == 1
    assert review_state["package_reviews"][0]["status"] == "fail"
    assert "action:run_missing" in review_state["package_reviews"][0]["failed_requirements"]


def test_build_demo_review_focus_prefers_selected_package(tmp_path: Path):
    pack = build_fixture_pack(tmp_path)
    action_run = _run_summary(tmp_path, request_kind="action_preview")
    animation_run = _run_summary(tmp_path, request_kind="animation_preview")
    review_state = build_demo_review_state(
        session_manifest_path=pack["session_manifest_path"],
        demo_control_state={
            "status": "pass",
            "control_state_path": str((tmp_path / "control.json").resolve()),
            "last_runs_by_package": {
                "pkg_alpha": {
                    "action_preview": action_run,
                    "animation_preview": animation_run,
                }
            },
        },
        demo_round_state={
            "status": "pass",
            "round_state_path": str((tmp_path / "round.json").resolve()),
            "package_results": [
                {
                    "package_id": "pkg_alpha",
                    "status": "pass",
                    "action_invoke": action_run,
                    "animation_invoke": animation_run,
                }
            ],
        },
    )
    focus = build_demo_review_focus(review_state, selected_package_id="pkg_alpha")
    assert focus["status"] == "pass"
    assert focus["selected_package_id"] == "pkg_alpha"
    assert focus["package_review_status"] == "pass"
    assert focus["action_review_status"] == "pass"
    assert focus["animation_review_status"] == "pass"
    assert focus["hero_before_image_path"]
