from __future__ import annotations

from aiue_t1.q5b_volumetric_fit import analyze_volumetric_fit


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


def test_volumetric_fit_passes_with_expected_fixture_geometry():
    result = analyze_volumetric_fit(host_result=_host_result_fixture())

    assert result["status"] == "pass"
    assert result["failed_requirements"] == []
    assert 0.85 <= result["metrics"]["anchor_vertical_ratio"] <= 1.05
    assert result["metrics"]["anchor_lateral_ratio_max"] <= 1.05


def test_volumetric_fit_detects_lateral_envelope_failure():
    host_result = _host_result_fixture()
    host_result["slot_component"]["attach"]["world_transform"]["location"]["y"] = 30.0

    result = analyze_volumetric_fit(host_result=host_result)

    assert result["status"] == "fail"
    assert "anchor_outside_lateral_envelope" in result["failed_requirements"]


def test_volumetric_fit_detects_surface_gap_failure():
    host_result = _host_result_fixture()
    host_result["slot_component"]["attach"]["world_transform"]["location"]["z"] = 210.0

    result = analyze_volumetric_fit(host_result=host_result)

    assert result["status"] == "fail"
    assert "anchor_surface_gap_out_of_range" in result["failed_requirements"]


def test_volumetric_fit_detects_slot_offset_failure():
    host_result = _host_result_fixture()
    host_result["slot_component"]["bounds"]["origin"]["z"] = 290.0

    result = analyze_volumetric_fit(host_result=host_result)

    assert result["status"] == "fail"
    assert "slot_offset_out_of_range" in result["failed_requirements"]


def test_volumetric_fit_reports_missing_input():
    result = analyze_volumetric_fit(host_result={"body_component": {}, "slot_component": {}})

    assert result["status"] == "fail"
    assert "body_bounds_missing" in result["failed_requirements"]
    assert "slot_bounds_missing" in result["failed_requirements"]
    assert "attach_transform_missing" in result["failed_requirements"]
