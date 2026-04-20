from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = REPO_ROOT / "workflows" / "pmx_pipeline"


def _load_q4_module():
    sys.modules.pop("_bootstrap", None)
    workflow_root_text = str(WORKFLOW_ROOT)
    if workflow_root_text not in sys.path:
        sys.path.insert(0, workflow_root_text)
    spec = importlib.util.spec_from_file_location(
        "aiue_test_run_multi_slot_quality_gate_q4",
        WORKFLOW_ROOT / "run_multi_slot_quality_gate_q4.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_Q4 = _load_q4_module()
evaluate_package = _Q4.evaluate_package
strict_shot_checks = _Q4.strict_shot_checks


def test_q4_strict_shot_checks_ignores_clothing_visibility_at_shot_level():
    shot = {
        "status": "pass",
        "quality_gate": {
            "weapon_visible": True,
            "subject_visible": True,
            "line_of_sight_clear": True,
            "capture_succeeded": True,
        },
        "subject_screen_coverage": 0.12,
        "weapon_screen_coverage": 0.02,
        "tracked_slot_coverages": {
            "clothing": {"coverage_ratio": 0.0},
            "fx": {"coverage_ratio": 0.08},
        },
        "image_path": "C:/tmp/front.png",
    }

    result, failures = strict_shot_checks("front", shot)

    assert result["status"] == "pass"
    assert not any(str(item.get("id") or "") == "q4_clothing_visibility_insufficient" for item in failures)


def test_q4_evaluate_package_requires_clothing_visible_in_at_least_one_strict_shot():
    runtime_check = {
        "package_id": "pkg_alpha",
        "sample_id": "sample_alpha",
        "status": "pass",
        "clothing_attach_state": {"resolved_attach_socket_exists": True},
        "fx_attach_state": {"resolved_attach_socket_exists": True},
    }
    visual_check = {
        "package_id": "pkg_alpha",
        "sample_id": "sample_alpha",
        "status": "pass",
        "shots": [
            {
                "shot_id": "front",
                "status": "pass",
                "quality_gate": {
                    "weapon_visible": True,
                    "subject_visible": True,
                    "line_of_sight_clear": True,
                    "capture_succeeded": True,
                },
                "subject_screen_coverage": 0.12,
                "weapon_screen_coverage": 0.02,
                "tracked_slot_coverages": {
                    "clothing": {"coverage_ratio": 0.0},
                    "fx": {"coverage_ratio": 0.08},
                },
                "image_path": "C:/tmp/front.png",
            },
            {
                "shot_id": "side",
                "status": "pass",
                "quality_gate": {
                    "weapon_visible": True,
                    "subject_visible": True,
                    "line_of_sight_clear": True,
                    "capture_succeeded": True,
                },
                "subject_screen_coverage": 0.12,
                "weapon_screen_coverage": 0.02,
                "tracked_slot_coverages": {
                    "clothing": {"coverage_ratio": 0.0},
                    "fx": {"coverage_ratio": 0.08},
                },
                "image_path": "C:/tmp/side.png",
            },
            {
                "shot_id": "hero",
                "status": "pass",
                "quality_gate": {
                    "weapon_visible": True,
                    "subject_visible": True,
                    "line_of_sight_clear": True,
                    "capture_succeeded": True,
                },
                "subject_screen_coverage": 0.12,
                "weapon_screen_coverage": 0.02,
                "tracked_slot_coverages": {
                    "clothing": {"coverage_ratio": 0.004},
                    "fx": {"coverage_ratio": 0.08},
                },
                "image_path": "C:/tmp/hero.png",
            },
        ],
    }

    result, failures = evaluate_package(runtime_check, visual_check)

    assert result["status"] == "fail"
    assert result["strict_clothing_visible_shot_ids"] == []
    assert any(str(item.get("id") or "") == "q4_clothing_visibility_insufficient" for item in failures)
