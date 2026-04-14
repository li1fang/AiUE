from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PMX_PIPELINE_ROOT = REPO_ROOT / "workflows" / "pmx_pipeline"
T1_ROOT = REPO_ROOT / "tools" / "t1" / "python"
CORE_ROOT = REPO_ROOT / "core" / "python"
for candidate in (PMX_PIPELINE_ROOT, T1_ROOT, CORE_ROOT):
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)

from aiue_t1.body_platform import build_body_platform_quality_summary, build_modular_morphology_inventory, classify_module_kind  # noqa: E402
from aiue_t1.report_index import build_report_index  # noqa: E402


def _touch_mesh(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("o fixture\n", encoding="utf-8")
    return path


def test_classify_module_kind_understands_first_body_axes():
    assert classify_module_kind("family/head/head_nohair.obj") == "head"
    assert classify_module_kind("family/hair/front_hair.fbx") == "hair"
    assert classify_module_kind("family/bust/bust_large.obj") == "bust_variant"
    assert classify_module_kind("family/core/core_torso_arm.obj") == "core_torso_arm"
    assert classify_module_kind("family/legs/left_thigh.obj") == "leg_profile"
    assert classify_module_kind("family/raw/raw_scan_highpoly.obj") == "non_consumable_raw_scan"


def test_build_modular_morphology_inventory_finds_candidate_family(tmp_path: Path):
    source_root = tmp_path / "body_source"
    _touch_mesh(source_root / "family_alpha" / "head" / "head_nohair.obj")
    _touch_mesh(source_root / "family_alpha" / "hair" / "front_hair.fbx")
    _touch_mesh(source_root / "family_alpha" / "bust" / "bust_large.obj")
    _touch_mesh(source_root / "family_alpha" / "core" / "core_torso_arm.obj")
    _touch_mesh(source_root / "family_alpha" / "legs" / "left_thigh.obj")
    _touch_mesh(source_root / "family_beta" / "head" / "head_alt.obj")

    inventory = build_modular_morphology_inventory(source_root)

    assert inventory["counts"]["module_count"] == 6
    assert inventory["counts"]["candidate_fixture_family_count"] == 1
    assert inventory["canonical_fixture_family_id"] == "family_alpha"
    assert inventory["module_kind_counts"]["head"] == 2
    assert inventory["module_kind_counts"]["bust_variant"] == 1
    assert inventory["module_kind_counts"]["core_torso_arm"] == 1
    assert inventory["module_kind_counts"]["leg_profile"] == 1
    assert inventory["module_kind_counts"]["hair"] == 1


def test_modular_morphology_inventory_runner_writes_latest_report(tmp_path: Path):
    source_root = tmp_path / "body_source"
    _touch_mesh(source_root / "family_alpha" / "head" / "head_nohair.obj")
    _touch_mesh(source_root / "family_alpha" / "hair" / "front_hair.fbx")
    _touch_mesh(source_root / "family_alpha" / "bust" / "bust_large.obj")
    _touch_mesh(source_root / "family_alpha" / "core" / "core_torso_arm.obj")
    _touch_mesh(source_root / "family_alpha" / "legs" / "left_thigh.obj")

    workspace_path = tmp_path / "pipeline_workspace.local.json"
    workspace_path.write_text(
        json.dumps(
            {
                "version": "0.1.0",
                "schema_version": 1,
                "paths": {
                    "aiue_repo_root": str(REPO_ROOT),
                    "body_morphology_source_root": str(source_root),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    output_root = tmp_path / "verification" / "c0_run"
    latest_report_path = tmp_path / "verification" / "latest_modular_morphology_inventory_c0_report.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(PMX_PIPELINE_ROOT / "run_modular_morphology_inventory_c0.py"),
            "--workspace-config",
            str(workspace_path),
            "--output-root",
            str(output_root),
            "--latest-report-path",
            str(latest_report_path),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(latest_report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["canonical_fixture_family_id"] == "family_alpha"
    assert (output_root / "modular_morphology_inventory_report.json").exists()
    assert (output_root / "modular_morphology_inventory_latest.json").exists()


def test_body_platform_quality_summary_reads_c0_report(tmp_path: Path):
    from tests.t2.helpers import write_fixture_c0_report

    verification_root = tmp_path / "verification"
    write_fixture_c0_report(verification_root)
    report_index = build_report_index(verification_root)
    summary = build_body_platform_quality_summary(report_index)

    assert summary["status"] == "pass"
    assert summary["family_count"] == 2
    assert summary["candidate_fixture_family_count"] == 1
    assert summary["canonical_fixture_family_id"] == "family_alpha"
    assert summary["module_kind_counts"]["head"] == 2
