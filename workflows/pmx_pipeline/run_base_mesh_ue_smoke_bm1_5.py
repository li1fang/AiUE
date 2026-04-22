from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import (  # noqa: E402
    build_discussion_signal,
    default_latest_report_path,
    default_output_root,
    now_utc,
    verification_named_report_path,
    write_report_pair,
)
from aiue_core.report_writer import make_compatibility_block, with_report_envelope  # noqa: E402
from aiue_core.schema_utils import load_json, load_workspace_config  # noqa: E402
from aiue_t1.base_mesh_trial import render_feedback_markdown, render_ue_suitability_markdown, ue_suitability_signal  # noqa: E402
from aiue_unreal.execution_errors import ActionResultError  # noqa: E402
from aiue_unreal.host_bridge import run_host_auto_ue_cli  # noqa: E402


GATE_ID = "base_mesh_ue_smoke_bm1_5"
REQUIRED_SHOTS = ["front", "side", "top"]
FIXED_EXECUTION_PROFILE = {
    "host_key": "kernel",
    "mode": "editor_rendered",
    "capture_width": 1280,
    "capture_height": 720,
    "capture_delay_seconds": 0.2,
    "subject_min_screen_coverage": 0.00002,
    "requested_shot_ids": list(REQUIRED_SHOTS),
    "required_subject_pass_count": 1,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the base mesh BM1.5 kernel visual smoke on the bodypaint-ready handoff subset.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--bm0-report-path")
    parser.add_argument("--bm1-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def _latest_markdown_path(workspace: dict, file_name: str) -> Path:
    return verification_named_report_path(workspace, REPO_ROOT, file_name)


def _candidate_primary_mesh_path(candidate: dict[str, Any]) -> str:
    provider_preview = dict(candidate.get("provider_preview") or {})
    primary_asset = dict(provider_preview.get("primary_asset") or {})
    return str(primary_asset.get("path") or "")


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    bm0_report_path = Path(args.bm0_report_path).expanduser().resolve() if args.bm0_report_path else default_latest_report_path(workspace, REPO_ROOT, "base_mesh_trial_bm0")
    bm1_report_path = Path(args.bm1_report_path).expanduser().resolve() if args.bm1_report_path else default_latest_report_path(workspace, REPO_ROOT, "base_mesh_bodypaint_handoff_bm1")
    output_root.mkdir(parents=True, exist_ok=True)
    latest_report_path.parent.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None

    bm0_report = load_json(bm0_report_path)
    bm1_report = load_json(bm1_report_path)
    bm0_items_by_id = {
        str(item.get("item_id") or ""): dict(item)
        for item in list(bm0_report.get("per_item_results") or [])
        if str(item.get("item_id") or "")
    }

    per_candidate_results: list[dict[str, Any]] = []
    for candidate in list(bm1_report.get("per_candidate_results") or []):
        item_id = str(candidate.get("item_id") or "")
        if not bool(candidate.get("ready_for_bodypaint")):
            continue
        mesh_source_path = _candidate_primary_mesh_path(candidate)
        candidate_output_root = output_root / "candidates" / item_id.replace("::", "__")
        host_action_result_path = candidate_output_root / "inspect-source-handoff-mesh-visual.json"
        params = {
            "item_id": item_id,
            "package_id": str(candidate.get("item_id") or ""),
            "fixture_id": str(((candidate.get("provider_preview") or {}).get("identity") or {}).get("fixture_id") or item_id),
            "mesh_source_path": mesh_source_path,
            "asset_root": "/Game/PMXPipeline/BaseMeshTrial/BM1Smoke",
            "output_root": str(candidate_output_root / "capture"),
            "capture_width": FIXED_EXECUTION_PROFILE["capture_width"],
            "capture_height": FIXED_EXECUTION_PROFILE["capture_height"],
            "capture_delay_seconds": FIXED_EXECUTION_PROFILE["capture_delay_seconds"],
            "requested_shot_ids": list(REQUIRED_SHOTS),
            "subject_min_screen_coverage": FIXED_EXECUTION_PROFILE["subject_min_screen_coverage"],
            "required_subject_pass_count": FIXED_EXECUTION_PROFILE["required_subject_pass_count"],
            "require_weapon_visible": False,
        }
        result_payload: dict[str, Any]
        invocation_error = ""
        try:
            invocation = run_host_auto_ue_cli(
                workspace_or_config=workspace,
                mode="editor_rendered",
                command="inspect-source-handoff-mesh-visual",
                params=params,
                output_path=str(host_action_result_path),
                host_key="kernel",
            )
            payload = dict((invocation.get("payload") or {}).get("result") or {})
            payload.setdefault("warnings", list((invocation.get("payload") or {}).get("warnings") or []))
            payload.setdefault("errors", list((invocation.get("payload") or {}).get("errors") or []))
            result_payload = payload
        except ActionResultError as exc:
            result_payload = dict(exc.result or {})
            result_payload.setdefault("warnings", list(exc.warnings or []))
            result_payload.setdefault("errors", list(exc.errors or []))
            invocation_error = str(exc)
        except Exception as exc:  # pragma: no cover - real environment guard
            result_payload = {
                "status": "fail",
                "warnings": [],
                "errors": [str(exc)],
            }
            invocation_error = str(exc)

        material_evidence = dict(result_payload.get("material_evidence") or {})
        material_evidence_present = bool(
            int(material_evidence.get("material_slot_count") or 0) > 0
            or list(material_evidence.get("material_slot_names") or [])
        )
        smoke_status = str(result_payload.get("status") or "fail")
        bm0_item = bm0_items_by_id.get(item_id, {})
        per_candidate_results.append(
            {
                "item_id": item_id,
                "archive_id": str(candidate.get("archive_id") or ""),
                "variant_id": str(candidate.get("variant_id") or ""),
                "attempted_format": str(candidate.get("attempted_format") or ""),
                "status": smoke_status,
                "mesh_source_path": mesh_source_path,
                "host_action_result_path": str(host_action_result_path.resolve()),
                "character_mesh_asset": str(result_payload.get("character_mesh_asset") or ""),
                "main_mesh_component": dict(result_payload.get("main_mesh_component") or {}),
                "main_mesh_bounds": dict(result_payload.get("main_mesh_bounds") or {}),
                "main_mesh_world_transform": dict(result_payload.get("main_mesh_world_transform") or {}),
                "material_evidence": material_evidence,
                "material_evidence_present": material_evidence_present,
                "shots": list(result_payload.get("shots") or []),
                "failed_requirements": list(result_payload.get("failed_requirements") or result_payload.get("errors") or []),
                "warnings": list(result_payload.get("warnings") or []),
                "errors": list(result_payload.get("errors") or []),
                "invocation_error": invocation_error,
                "ue_suitability_signal": ue_suitability_signal(
                    attempted_format=str(candidate.get("attempted_format") or ""),
                    status=str(bm0_item.get("status") or "pass"),
                    bodypaint_handoff_candidate=bool(candidate.get("ready_for_bodypaint")),
                    provider_ready_status=str(candidate.get("provider_ready_status") or ""),
                    ue_smoke_status=smoke_status,
                ),
            }
        )

    counts = {
        "candidate_count": len(per_candidate_results),
        "passing_candidates": sum(1 for item in per_candidate_results if item.get("status") == "pass"),
        "material_evidence_pass_count": sum(1 for item in per_candidate_results if item.get("material_evidence_present")),
    }
    failed_requirements: list[dict[str, Any]] = []
    if counts["candidate_count"] == 0:
        failed_requirements.append(
            {
                "id": "no_bm1_ready_candidates",
                "message": "BM1 did not provide any ready-for-bodypaint FBX candidates for UE smoke.",
            }
        )
    if counts["passing_candidates"] < counts["candidate_count"]:
        failed_requirements.append(
            {
                "id": "ue_smoke_candidate_failures",
                "message": "At least one BM1 candidate did not complete the kernel visual smoke successfully.",
                "passing_candidates": counts["passing_candidates"],
                "candidate_count": counts["candidate_count"],
            }
        )
    if counts["material_evidence_pass_count"] < counts["candidate_count"]:
        failed_requirements.append(
            {
                "id": "ue_smoke_material_evidence_incomplete",
                "message": "At least one BM1 candidate did not expose minimal material evidence during the UE smoke.",
                "material_evidence_pass_count": counts["material_evidence_pass_count"],
                "candidate_count": counts["candidate_count"],
            }
        )

    status = "pass" if not failed_requirements else "attention"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        latest_report_path if previous_report else None,
        "bm1_5_first_complete_pass",
    )
    report_payload = with_report_envelope(
        {
            "gate_id": GATE_ID,
            "status": status,
            "generated_at_utc": now_utc(),
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_bm0_report_path": str(bm0_report_path),
            "source_bm1_report_path": str(bm1_report_path),
            "fixed_execution_profile": FIXED_EXECUTION_PROFILE,
            "counts": counts,
            "failed_requirements": failed_requirements,
            "per_candidate_results": per_candidate_results,
            "artifacts": {
                "report_root": str(output_root),
                "latest_report_path": str(latest_report_path),
            },
            "discussion_signal": discussion_signal,
        },
        schema_family="body_platform.base_mesh_ue_smoke.bm1_5",
        workflow_pack="body_platform",
        compatibility=make_compatibility_block(
            "body_platform.base_mesh_ue_smoke.bm1_5",
            notes=[
                "kernel-side visual smoke for bodypaint-ready base mesh handoff candidates",
                "proves that handoff meshes can enter UE and produce visible evidence without promoting them to the demo line",
            ],
        ),
    )
    report_path = output_root / "base_mesh_ue_smoke_bm1_5_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)

    feedback_path = output_root / "toy_yard_base_mesh_trial_feedback.md"
    suitability_path = output_root / "base_mesh_ue_suitability_review.md"
    feedback_latest_path = _latest_markdown_path(workspace, "latest_toy_yard_base_mesh_trial_feedback.md")
    suitability_latest_path = _latest_markdown_path(workspace, "latest_base_mesh_ue_suitability_review.md")
    feedback_text = render_feedback_markdown(
        runbook_path=Path(r"C:\Projects\toy-yard\docs\aiue_base_mesh_trial_runbook_v0.md"),
        inventory_path=Path(r"C:\Projects\toy-yard\_reports\base_mesh_batch_inventory_2026-04-22.md"),
        bm0_report=bm0_report,
        bm1_report=bm1_report,
        bm1_5_report=report_payload,
    )
    suitability_text = render_ue_suitability_markdown(
        bm0_report=bm0_report,
        bm1_report=bm1_report,
        bm1_5_report=report_payload,
    )
    feedback_path.write_text(feedback_text + "\n", encoding="utf-8")
    suitability_path.write_text(suitability_text + "\n", encoding="utf-8")
    feedback_latest_path.write_text(feedback_text + "\n", encoding="utf-8")
    suitability_latest_path.write_text(suitability_text + "\n", encoding="utf-8")

    print(f"BM1.5 base mesh UE smoke report written to: {report_path}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
