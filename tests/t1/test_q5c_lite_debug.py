from __future__ import annotations

from pathlib import Path

from aiue_t1.q5c_lite import analyze_q5c_lite, closest_margin_info, margin_to_failure_by_metric, risk_band_for_q5c_lite, risk_reason_for_q5c_lite
from aiue_t1.q5c_lite_debug import render_q5c_lite_debug_image


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


def test_q5c_lite_debug_image_renders_png(tmp_path: Path):
    analysis = analyze_q5c_lite(host_result=_host_result_fixture())
    closest_metric, closest_value = closest_margin_info(threshold_deltas=analysis["threshold_deltas"])
    risk_band = risk_band_for_q5c_lite(
        status=analysis["status"],
        fit_diagnostic_class=analysis["fit_diagnostic_class"],
        closest_margin_value=closest_value,
    )
    risk_reason = risk_reason_for_q5c_lite(
        risk_band=risk_band,
        fit_diagnostic_class=analysis["fit_diagnostic_class"],
        closest_margin_metric=closest_metric,
        closest_margin_value=closest_value,
    )
    output_path = tmp_path / "q5c_debug.png"

    debug_artifact = render_q5c_lite_debug_image(
        package_id="fixture_pkg",
        analysis=analysis,
        risk_context={
            "risk_band": risk_band,
            "risk_reason": risk_reason,
            "closest_margin_metric": closest_metric,
            "closest_margin_value": closest_value,
            "margin_to_failure_by_metric": margin_to_failure_by_metric(threshold_deltas=analysis["threshold_deltas"]),
        },
        output_path=output_path,
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0
    assert Path(debug_artifact["image_path"]) == output_path.resolve()
    assert debug_artifact["risk_band"] == "watch"
    assert debug_artifact["closest_margin_metric"] == "penetration_ratio_margin_to_failure"
    assert debug_artifact["closest_margin_value"] == 0.02
    assert len(list(debug_artifact["panels"])) == 2
