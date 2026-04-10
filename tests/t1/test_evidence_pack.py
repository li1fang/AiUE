from __future__ import annotations

import json
from pathlib import Path

from aiue_core.schema_utils import load_json, write_json
from aiue_t1.evidence_pack import build_evidence_pack


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
REPORT_FIXTURES = FIXTURE_ROOT / "reports"


def _materialize_reports(target_root: Path) -> Path:
    target_root.mkdir(parents=True, exist_ok=True)
    placeholder_root = str(FIXTURE_ROOT).replace("\\", "/")
    for report_path in REPORT_FIXTURES.glob("*.json"):
        payload = load_json(report_path)
        serialized = json.dumps(payload)
        serialized = serialized.replace("__FIXTURE_ROOT__", placeholder_root)
        write_json(target_root / report_path.name, json.loads(serialized))
    return target_root


def test_build_evidence_pack_generates_static_bundle(tmp_path: Path):
    verification_root = _materialize_reports(tmp_path / "verification")
    output_root = tmp_path / "tooling" / "run"
    latest_root = tmp_path / "tooling" / "latest"
    manifest = build_evidence_pack(
        verification_root=verification_root,
        output_root=output_root,
        latest_root=latest_root,
        repo_root=tmp_path,
    )
    assert (output_root / "index.html").exists()
    assert (output_root / "manifest.json").exists()
    assert (latest_root / "index.html").exists()
    assert manifest["slot_debugger"]["package_count"] == 1
    assert len(manifest["artifacts"]["preview_images"]) >= 4
