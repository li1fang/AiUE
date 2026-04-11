from __future__ import annotations

from aiue_t1.q5c_lite import (
    analyze_q5c_lite,
    closest_margin_info,
    margin_to_failure_by_metric,
    risk_band_for_q5c_lite,
    risk_reason_for_q5c_lite,
)


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
    assert result["fit_diagnostic_class"] == "pass_stable"
    assert result["embedding_ratio"] >= 0.82
    assert result["floating_ratio"] <= 0.18
    assert result["penetration_clusters"] == []
    assert result["body_bounds_world"]["source"] == "fixture_body"
    assert result["local_fit_intersection"]["volume"] > 0.0
    assert result["penetration_intersection"]["volume"] == 0.0
    assert result["diagnostic_signals"]["penetration_ratio_exceeded"] is False


def test_q5c_lite_detects_penetration_cluster():
    host_result = _host_result_fixture()
    host_result["slot_component"]["bounds"]["origin"]["z"] = 170.0

    result = analyze_q5c_lite(host_result=host_result)

    assert result["status"] == "fail"
    assert result["quality_class"] == "fail"
    assert result["penetration_clusters"]
    assert result["fit_diagnostic_class"] == "mixed_penetration_and_floating"
    assert result["diagnostic_signals"]["penetration_ratio_exceeded"] is True
    assert result["diagnostic_signals"]["floating_ratio_exceeded"] is True
    assert result["penetration_clusters"][0]["cluster_class"] == "body_keepout_overlap"
    assert result["penetration_clusters"][0]["excess_ratio"] > 0.0


def test_q5c_lite_detects_floating_fit():
    host_result = _host_result_fixture()
    host_result["slot_component"]["bounds"]["origin"]["z"] = 430.0

    result = analyze_q5c_lite(host_result=host_result)

    assert result["status"] == "fail"
    assert result["fit_diagnostic_class"] == "floating_fit_out_of_range"
    assert result["diagnostic_signals"]["penetration_ratio_exceeded"] is False
    assert "fit_envelope_mismatch" in result["failed_requirements"] or "floating_ratio_exceeded" in result["failed_requirements"]


def test_q5c_lite_detects_input_invalid():
    host_result = _host_result_fixture()
    host_result["slot_component"]["attach"] = {}

    result = analyze_q5c_lite(host_result=host_result)

    assert result["status"] == "fail"
    assert result["fit_diagnostic_class"] == "input_invalid"
    assert "anchor_frame_missing" in result["failed_requirements"]


def test_q5c_lite_risk_helpers_classify_watch_margin():
    result = analyze_q5c_lite(host_result=_host_result_fixture())
    margin_map = margin_to_failure_by_metric(threshold_deltas=result["threshold_deltas"])
    closest_metric, closest_value = closest_margin_info(threshold_deltas=result["threshold_deltas"])
    risk_band = risk_band_for_q5c_lite(
        status=result["status"],
        fit_diagnostic_class=result["fit_diagnostic_class"],
        closest_margin_value=closest_value,
    )
    risk_reason = risk_reason_for_q5c_lite(
        risk_band=risk_band,
        fit_diagnostic_class=result["fit_diagnostic_class"],
        closest_margin_metric=closest_metric,
        closest_margin_value=closest_value,
    )

    assert margin_map["penetration_ratio_margin_to_failure"] == 0.02
    assert closest_metric == "penetration_ratio_margin_to_failure"
    assert closest_value == 0.02
    assert risk_band == "watch"
    assert risk_reason == "penetration_ratio_margin_to_failure:0.0200"
