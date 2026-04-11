from __future__ import annotations

from aiue_t1.q5bx_spatial_evidence import analyze_spatial_evidence


def _host_result_fixture() -> dict:
    return {
        "body_component": {
            "bounds": {
                "origin": {"x": 0.0, "y": 0.0, "z": 100.0},
                "extent": {"x": 50.0, "y": 20.0, "z": 80.0},
                "non_zero": True,
                "source": "fixture_body",
            }
        },
        "slot_component": {
            "bounds": {
                "origin": {"x": 0.0, "y": 0.0, "z": 327.6},
                "extent": {"x": 10.0, "y": 15.0, "z": 20.0},
                "non_zero": True,
                "source": "fixture_slot",
            },
            "attach": {
                "world_transform": {
                    "location": {"x": 0.0, "y": 18.0, "z": 184.0},
                }
            },
        },
        "clothing_attach_state": {
            "slot_name": "clothing",
            "resolved_attach_socket_name": "Head",
            "resolved_attach_socket_exists": True,
            "attach_resolution_mode": "fallback_bone_score",
        },
    }


def test_q5bx_passes_for_current_fixture_geometry():
    result = analyze_spatial_evidence(host_result=_host_result_fixture())

    assert result["status"] == "pass"
    assert result["spatial_failure_class"] is None
    assert result["anchor_frame"]["anchor_vertical_ratio"] >= 0.85
    assert result["slot_bounds_world"]["volume"] > 0.0
    assert result["evidence_confidence"]["score"] > 0.0


def test_q5bx_detects_clearance_failure():
    host_result = _host_result_fixture()
    host_result["slot_component"]["attach"]["world_transform"]["location"]["z"] = 220.0

    result = analyze_spatial_evidence(host_result=host_result)

    assert result["status"] == "fail"
    assert result["spatial_failure_class"] == "clearance_out_of_range"


def test_q5bx_detects_fit_envelope_mismatch():
    host_result = _host_result_fixture()
    host_result["slot_component"]["bounds"]["origin"]["z"] = 380.0

    result = analyze_spatial_evidence(host_result=host_result)

    assert result["status"] == "fail"
    assert "fit_envelope_mismatch" in result["failed_requirements"]


def test_q5bx_reports_missing_geometry_inputs():
    result = analyze_spatial_evidence(host_result={"body_component": {}, "slot_component": {}})

    assert result["status"] == "fail"
    assert "anchor_frame_missing" in result["failed_requirements"]
    assert "body_envelope_invalid" in result["failed_requirements"]
    assert "slot_relative_bounds_invalid" in result["failed_requirements"]
