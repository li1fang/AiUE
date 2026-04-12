from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_e2c_module():
    module_path = Path(__file__).resolve().parents[2] / "workflows" / "pmx_pipeline" / "run_playable_demo_e2c_credible_showcase_polish.py"
    workflow_dir = str(module_path.parent)
    if workflow_dir not in sys.path:
        sys.path.insert(0, workflow_dir)
    sys.modules.pop("_bootstrap", None)
    spec = importlib.util.spec_from_file_location("run_playable_demo_e2c_credible_showcase_polish_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_material_reference_ready_accepts_m1_style_reference():
    module = _load_e2c_module()
    material_reference = {
        "status": "pass",
        "m1_report_path": r"C:\AiUE\Saved\verification\latest_material_texture_proof_m1_report.json",
        "character_texture_counts": {"expected": 13, "imported": 13},
        "weapon_texture_counts": {"expected": 3, "imported": 3},
        "host_visual_material_evidence": {
            "main_mesh": {
                "material_slot_count": 30,
                "material_asset_paths": ["/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial"],
                "non_empty_material_asset_paths": ["/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial"],
            },
            "weapon_mesh": {
                "material_slot_count": 1,
                "material_asset_paths": ["/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial"],
                "non_empty_material_asset_paths": ["/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial"],
            },
        },
    }
    assert module._material_reference_ready(material_reference) is True


def test_material_reference_ready_rejects_missing_or_failed_reference():
    module = _load_e2c_module()
    assert module._material_reference_ready({}) is False
    assert module._material_reference_ready({"status": "fail"}) is False
