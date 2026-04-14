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

from aiue_t1.body_platform import build_parametric_body_contract, build_body_platform_quality_summary  # noqa: E402
from aiue_t1.report_index import build_report_index  # noqa: E402


def _source_report() -> dict:
    return {
        "gate_id": "modular_morphology_inventory_c0",
        "status": "pass",
        "source_root": "C:/fixture/body_source",
        "counts": {
            "module_count": 5,
            "classified_module_count": 5,
            "family_count": 1,
            "candidate_fixture_family_count": 1,
        },
        "module_kind_counts": {
            "head": 1,
            "hair": 1,
            "bust_variant": 1,
            "core_torso_arm": 1,
            "leg_profile": 1,
        },
        "canonical_fixture_family_id": "family_alpha",
        "per_family_results": [
            {
                "family_id": "family_alpha",
                "family_root": "C:/fixture/body_source/family_alpha",
                "module_count": 5,
                "classified_module_count": 5,
                "module_kind_counts": {
                    "head": 1,
                    "hair": 1,
                    "bust_variant": 1,
                    "core_torso_arm": 1,
                    "leg_profile": 1,
                },
                "module_ids_by_kind": {
                    "head": ["family_alpha/head/head_nohair"],
                    "hair": ["family_alpha/hair/front_hair"],
                    "bust_variant": ["family_alpha/bust/bust_large"],
                    "core_torso_arm": ["family_alpha/core/core_torso_arm"],
                    "leg_profile": ["family_alpha/legs/left_thigh"],
                },
                "required_axes_present": {
                    "head": True,
                    "bust_variant": True,
                    "leg_profile": True,
                    "core_torso_arm": True,
                },
                "optional_axes_present": {"hair": True},
                "candidate_fixture_family": True,
            }
        ],
    }


def test_build_parametric_body_contract_from_c0_report():
    contract = build_parametric_body_contract(_source_report())
    assert contract["body_family_id"] == "family_alpha"
    assert contract["core_module_id"] == "family_alpha/core/core_torso_arm"
    assert contract["supported_head_ids"] == ["family_alpha/head/head_nohair"]
    assert contract["supported_bust_classes"] == ["family_alpha/bust/bust_large"]
    assert contract["supported_leg_length_profiles"] == ["family_alpha/legs/left_thigh"]
    assert contract["compatible_hair_ids"] == ["family_alpha/hair/front_hair"]


def test_parametric_body_contract_runner_writes_latest_report(tmp_path: Path):
    source_report_path = tmp_path / "verification" / "latest_modular_morphology_inventory_c0_report.json"
    source_report_path.parent.mkdir(parents=True, exist_ok=True)
    source_report_path.write_text(json.dumps(_source_report(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    workspace_path = tmp_path / "pipeline_workspace.local.json"
    workspace_path.write_text(
        json.dumps(
            {
                "version": "0.1.0",
                "schema_version": 1,
                "paths": {
                    "aiue_repo_root": str(REPO_ROOT),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    output_root = tmp_path / "verification" / "c1_run"
    latest_report_path = tmp_path / "verification" / "latest_parametric_body_contract_c1_report.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(PMX_PIPELINE_ROOT / "run_parametric_body_contract_c1.py"),
            "--workspace-config",
            str(workspace_path),
            "--source-report",
            str(source_report_path),
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
    assert payload["body_family_id"] == "family_alpha"
    assert payload["parametric_body_contract"]["supported_head_ids"] == ["family_alpha/head/head_nohair"]
    assert (output_root / "parametric_body_contract_report.json").exists()
    assert (output_root / "parametric_body_contract_latest.json").exists()


def test_body_platform_quality_summary_prefers_c1_when_available(tmp_path: Path):
    from tests.t2.helpers import write_fixture_c0_report, write_fixture_c1_report

    verification_root = tmp_path / "verification"
    write_fixture_c0_report(verification_root)
    write_fixture_c1_report(verification_root)
    report_index = build_report_index(verification_root)
    summary = build_body_platform_quality_summary(report_index)

    assert summary["gate_id"] == "parametric_body_contract_c1"
    assert summary["status"] == "pass"
    assert summary["contract_id"] == "family_alpha::parametric_body_contract_c1"
    assert summary["core_module_id"] == "family_alpha/core/core_torso_arm"
    assert summary["supported_head_ids"] == ["family_alpha/head/head_nohair"]
