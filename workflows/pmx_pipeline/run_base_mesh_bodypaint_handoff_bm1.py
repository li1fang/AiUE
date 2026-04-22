from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, now_utc, write_report_pair  # noqa: E402
from aiue_core.report_writer import make_compatibility_block, with_report_envelope  # noqa: E402
from aiue_core.schema_utils import load_json, load_workspace_config  # noqa: E402


GATE_ID = "base_mesh_bodypaint_handoff_bm1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote BM0 base mesh trial successes into the BodyPaint handoff subset.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--bm0-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def _copy_if_present(source_path: str | None, destination_path: Path) -> str:
    if not source_path:
        return ""
    source = Path(source_path).expanduser().resolve()
    if not source.exists():
        return ""
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination_path)
    return str(destination_path.resolve())


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    bm0_report_path = Path(args.bm0_report_path).expanduser().resolve() if args.bm0_report_path else default_latest_report_path(workspace, REPO_ROOT, "base_mesh_trial_bm0")
    output_root.mkdir(parents=True, exist_ok=True)
    latest_report_path.parent.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None

    bm0_report = load_json(bm0_report_path)
    per_candidate_results: list[dict[str, object]] = []
    for item in list(bm0_report.get("per_item_results") or []):
        if not bool(item.get("bodypaint_handoff_candidate")):
            continue
        item_id = str(item.get("item_id") or "")
        candidate_root = output_root / "candidates" / item_id.replace("::", "__")
        candidate_root.mkdir(parents=True, exist_ok=True)
        handoff_zip_path = _copy_if_present(str(item.get("handoff_zip_path") or ""), candidate_root / "handoff.zip")
        provider_preview_path = _copy_if_present(str(item.get("provider_preview_path") or ""), candidate_root / "converted_model_provider_preview.json")
        provider_check_report_path = _copy_if_present(str(item.get("provider_ready_report_path") or ""), candidate_root / "provider_ready_check.json")
        manifest_path = _copy_if_present(str(item.get("manifest_path") or ""), candidate_root / "canonical_fusion_fixture_manifest.json")
        per_candidate_results.append(
            {
                "item_id": item_id,
                "archive_id": str(item.get("archive_id") or ""),
                "variant_id": str(item.get("variant_id") or ""),
                "attempted_format": str(item.get("attempted_format") or ""),
                "status": "pass" if handoff_zip_path and provider_preview_path else "attention",
                "ready_for_bodypaint": bool(item.get("bodypaint_handoff_candidate")),
                "ue_suitability_signal": str(item.get("ue_suitability_signal") or ""),
                "source_mesh_path": str(item.get("source_mesh_path") or ""),
                "handoff_zip_path": handoff_zip_path,
                "provider_preview_path": provider_preview_path,
                "provider_ready_report_path": provider_check_report_path,
                "manifest_path": manifest_path,
                "provider_ready_status": str(item.get("provider_ready_status") or ""),
                "provider_preview": dict(item.get("provider_preview") or {}),
            }
        )

    counts = {
        "bm0_candidate_count": sum(1 for item in list(bm0_report.get("per_item_results") or []) if item.get("bodypaint_handoff_candidate")),
        "ready_candidate_count": len(per_candidate_results),
        "copied_handoff_count": sum(1 for item in per_candidate_results if item.get("handoff_zip_path")),
    }
    failed_requirements: list[dict[str, object]] = []
    if counts["ready_candidate_count"] == 0:
        failed_requirements.append(
            {
                "id": "no_bodypaint_ready_candidates",
                "message": "BM0 did not yield any bodypaint-ready base mesh handoff candidates.",
            }
        )

    status = "pass" if not failed_requirements else "attention"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        latest_report_path if previous_report else None,
        "bm1_first_complete_pass",
    )
    report_payload = with_report_envelope(
        {
            "gate_id": GATE_ID,
            "status": status,
            "generated_at_utc": now_utc(),
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_bm0_report_path": str(bm0_report_path),
            "counts": counts,
            "failed_requirements": failed_requirements,
            "per_candidate_results": per_candidate_results,
            "artifacts": {
                "report_root": str(output_root),
                "latest_report_path": str(latest_report_path),
            },
            "discussion_signal": discussion_signal,
        },
        schema_family="body_platform.base_mesh_bodypaint_handoff.bm1",
        workflow_pack="body_platform",
        compatibility=make_compatibility_block(
            "body_platform.base_mesh_bodypaint_handoff.bm1",
            notes=[
                "promotes BM0 bodypaint-ready successes into a stable AiUE-delivered handoff subset",
                "does not re-run provider schema generation; it consolidates successful BM0 artifacts",
            ],
        ),
    )
    report_path = output_root / "base_mesh_bodypaint_handoff_bm1_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(f"BM1 bodypaint handoff report written to: {report_path}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
