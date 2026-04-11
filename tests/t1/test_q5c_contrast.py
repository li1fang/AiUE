from __future__ import annotations

from aiue_t1.q5c_contrast import generate_q5c_contrast_suite


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


def test_generate_q5c_contrast_suite_finds_pass_and_fail_references():
    suite = generate_q5c_contrast_suite(host_result=_host_result_fixture())
    case_ids = [str(item.get("case_id") or "") for item in list(suite.get("selected_cases") or [])]
    case_map = {str(item.get("case_id") or ""): dict(item) for item in list(suite.get("selected_cases") or [])}

    assert suite["baseline_case_id"] == "baseline_current"
    assert "baseline_current" in case_ids
    assert "best_pass_reference" in case_ids
    assert "closest_fail_reference" in case_ids
    assert suite["search_summary"]["explored_case_count"] >= 3
    assert suite["search_summary"]["best_pass_reference_found"] is True
    assert suite["search_summary"]["closest_fail_reference_found"] is True
    assert case_map["baseline_current"]["risk_band"] == "watch"
    assert case_map["best_pass_reference"]["status"] == "pass"
    assert abs(float(case_map["best_pass_reference"]["delta_z"])) > 0.0
    assert case_map["closest_fail_reference"]["status"] == "fail"
