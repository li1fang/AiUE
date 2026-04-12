from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from aiue_t1.a1_candidate_provider import build_a1_candidate_provider_summary
from aiue_t1.report_index import build_report_index
from tests.t2.helpers import build_fixture_pack


def _load_a1_module():
    module_path = Path(__file__).resolve().parents[2] / "workflows" / "pmx_pipeline" / "run_action_candidate_provider_a1.py"
    workflow_dir = str(module_path.parent)
    if workflow_dir not in sys.path:
        sys.path.insert(0, workflow_dir)
    sys.modules.pop("_bootstrap", None)
    spec = importlib.util.spec_from_file_location("run_action_candidate_provider_a1_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_a1_candidate_provider_summary_reads_latest_report(tmp_path: Path):
    pack = build_fixture_pack(tmp_path, include_a1=True)
    report_index = build_report_index(pack["verification_root"])
    summary = build_a1_candidate_provider_summary(report_index)
    assert summary["status"] == "pass"
    assert summary["counts"]["passing_candidates"] == 1
    assert summary["candidate_sources"][0]["provider_name"] == "fixture_provider_v1"
    assert summary["packages"][0]["candidate_id"] == "candidate_MM_Attack_01"


def test_fixture_candidate_manifest_prefers_non_idle_animation():
    module = _load_a1_module()
    package_payload = {
        "package_id": "pkg_alpha",
        "sample_id": "fixture_alpha",
        "slot_bindings": [{"slot_name": "weapon"}, {"slot_name": "clothing"}],
        "evidence": {"hero_before_image_path": "before.png", "hero_after_image_path": "after.png"},
        "action_presets": [{"preset_id": "showcase_root_translate_and_turn"}],
        "animation_presets": [
            {"preset_id": "MM_Idle", "family": "idle", "status": "pass"},
            {"preset_id": "MM_Attack_01", "family": "attack", "status": "pass"},
        ],
    }
    candidate_payload = module._derive_fixture_candidate_for_package(package_payload)
    assert candidate_payload["selected_animation_preset_id"] == "MM_Attack_01"
    assert candidate_payload["candidate_payload_kind"] == "session_animation_preset_ref"
