from __future__ import annotations

from aiue_t1.q5c_lite import analyze_q5c_lite


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
    }


def test_q5c_lite_passes_for_local_fit_fixture():
    result = analyze_q5c_lite(host_result=_host_result_fixture())

    assert result["status"] == "pass"
    assert result["quality_class"] == "pass"
    assert result["embedding_ratio"] >= 0.82
    assert result["floating_ratio"] <= 0.18
    assert result["penetration_clusters"] == []
    assert result["body_bounds_world"]["source"] == "fixture_body"
    assert result["local_fit_intersection"]["volume"] > 0.0
    assert result["penetration_intersection"]["volume"] == 0.0


def test_q5c_lite_detects_penetration_cluster():
    host_result = _host_result_fixture()
    host_result["slot_component"]["bounds"]["origin"]["z"] = 170.0

    result = analyze_q5c_lite(host_result=host_result)

    assert result["status"] == "fail"
    assert result["quality_class"] == "fail"
    assert result["penetration_clusters"]


def test_q5c_lite_detects_floating_fit():
    host_result = _host_result_fixture()
    host_result["slot_component"]["bounds"]["origin"]["z"] = 430.0

    result = analyze_q5c_lite(host_result=host_result)

    assert result["status"] == "fail"
    assert "fit_envelope_mismatch" in result["failed_requirements"] or "floating_ratio_exceeded" in result["failed_requirements"]
