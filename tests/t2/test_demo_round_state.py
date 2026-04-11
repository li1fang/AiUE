from __future__ import annotations

from aiue_t2.demo_round_state import load_demo_round_state, write_demo_round_state

from tests.t2.helpers import build_fixture_e2_session


def test_write_and_load_demo_round_state_roundtrip(tmp_path):
    session_manifest_path = build_fixture_e2_session(tmp_path)
    round_state = write_demo_round_state(
        session_manifest_path=session_manifest_path,
        session_id="playable_demo_e2_bootstrap",
        operation="invoke_session_round",
        package_results=[
            {
                "package_id": "pkg_alpha",
                "status": "pass",
                "action_invoke": {"credibility_summary": {"action_motion_verified": True}},
                "animation_invoke": {"credibility_summary": {"animation_pose_verified": True}},
            }
        ],
    )
    assert round_state["status"] == "pass"
    assert round_state["counts"]["package_count"] == 1
    assert round_state["counts"]["action_motion_verified"] == 1
    assert round_state["counts"]["animation_pose_verified"] == 1

    loaded = load_demo_round_state(session_manifest_path)
    assert loaded["status"] == "pass"
    assert loaded["operation"] == "invoke_session_round"
    assert loaded["package_ids"] == ["pkg_alpha"]


def test_load_demo_round_state_returns_missing_for_absent_file(tmp_path):
    session_manifest_path = build_fixture_e2_session(tmp_path)
    loaded = load_demo_round_state(session_manifest_path)
    assert loaded["status"] == "missing"
    assert loaded["package_results"] == []
