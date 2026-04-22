from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, now_utc, verification_named_report_path, write_report_pair  # noqa: E402
from aiue_core.report_writer import make_compatibility_block, with_report_envelope  # noqa: E402
from aiue_core.schema_utils import load_json, load_workspace_config, write_json  # noqa: E402
from aiue_t1.base_mesh_trial import (  # noqa: E402
    build_fixture_identity,
    discover_base_mesh_items,
    extract_archive_entry,
    parse_base_mesh_inventory,
    render_feedback_markdown,
    render_ue_suitability_markdown,
    ue_suitability_signal,
)


GATE_ID = "base_mesh_trial_bm0"
DEFAULT_INVENTORY_PATH = Path(r"C:\Projects\toy-yard\_reports\base_mesh_batch_inventory_2026-04-22.md")
DEFAULT_RUNBOOK_PATH = Path(r"C:\Projects\toy-yard\docs\aiue_base_mesh_trial_runbook_v0.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the first AiUE base mesh batch trial against the toy-yard admitted archive set.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--inventory-path", default=str(DEFAULT_INVENTORY_PATH))
    parser.add_argument("--runbook-path", default=str(DEFAULT_RUNBOOK_PATH))
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def _python_executable() -> str:
    return sys.executable


def _run_python_script(script_path: Path, arguments: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(
        [_python_executable(), str(script_path), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode, completed.stdout, completed.stderr


def _build_script(name: str) -> Path:
    return REPO_ROOT / "workflows" / "pmx_pipeline" / name


def _latest_markdown_path(workspace: dict, file_name: str) -> Path:
    return verification_named_report_path(workspace, REPO_ROOT, file_name)


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    inventory_path = Path(args.inventory_path).expanduser().resolve()
    runbook_path = Path(args.runbook_path).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    latest_report_path.parent.mkdir(parents=True, exist_ok=True)

    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None

    inventory_rows = parse_base_mesh_inventory(inventory_path)
    build_script = _build_script("run_build_provider_ready_source_handoff_sample.py")
    check_script = _build_script("run_check_c2_provider_ready_source_handoff.py")
    per_item_results: list[dict[str, object]] = []

    for row in inventory_rows:
        archive_id = str(row.get("archive_id") or "")
        archive_path = Path(str(row.get("source_archive") or "")).expanduser().resolve()
        if not archive_path.exists():
            per_item_results.append(
                {
                    "item_id": f"{archive_id.lower()}::missing_archive",
                    "archive_id": archive_id,
                    "source_archive": str(archive_path),
                    "variant_id": "",
                    "attempted_format": "",
                    "status": "blocked",
                    "failure_class": "source_archive_missing",
                    "normalized_output_path": "",
                    "normalized_mesh_path": "",
                    "handoff_zip_path": "",
                    "ue_suitability_signal": "blocked_candidate",
                    "bodypaint_handoff_candidate": False,
                    "notes": [f"missing_source_archive:{archive_path}"],
                }
            )
            continue

        for item in discover_base_mesh_items(archive_id, archive_path):
            item_id = str(item.get("item_id") or "")
            attempted_format = str(item.get("attempted_format") or "")
            item_output_root = output_root / "items" / item_id.replace("::", "__")
            item_output_root.mkdir(parents=True, exist_ok=True)
            result: dict[str, object] = {
                "item_id": item_id,
                "archive_id": archive_id,
                "source_archive": str(archive_path),
                "variant_id": str(item.get("variant_id") or ""),
                "mesh_entry": str(item.get("mesh_entry") or ""),
                "attempted_format": attempted_format,
                "format_fallback_used": bool(item.get("format_fallback_used")),
                "status": "blocked",
                "failure_class": "",
                "normalized_output_path": "",
                "normalized_mesh_path": "",
                "handoff_zip_path": "",
                "ue_suitability_signal": "",
                "bodypaint_handoff_candidate": False,
                "provider_ready_status": "",
                "provider_preview_path": "",
                "provider_ready_report_path": "",
                "source_mesh_path": "",
                "notes": [],
            }

            if attempted_format == "c4d":
                result["status"] = "blocked"
                result["failure_class"] = "external_converter_required"
                result["ue_suitability_signal"] = ue_suitability_signal(
                    attempted_format=attempted_format,
                    status=str(result["status"]),
                    bodypaint_handoff_candidate=False,
                    provider_ready_status="",
                )
                result["notes"] = ["c4d_currently_has_no_direct_aiue_consumer"]
                per_item_results.append(result)
                continue

            extracted_mesh_path = extract_archive_entry(archive_path, str(item.get("mesh_entry") or ""), item_output_root / "source_mesh")
            result["source_mesh_path"] = str(extracted_mesh_path)
            fixture_identity = build_fixture_identity(
                archive_id,
                str(item.get("variant_id") or ""),
                item_id=item_id,
            )
            build_output_root = item_output_root / "build"
            build_args = [
                "--source-mesh",
                str(extracted_mesh_path),
                "--output-root",
                str(build_output_root),
                "--fixture-id",
                fixture_identity["fixture_id"],
                "--body-family-id",
                fixture_identity["body_family_id"],
                "--fixture-scope",
                "full_body",
                "--source-module-id",
                archive_id,
                "--source-module-id",
                str(item.get("variant_id") or ""),
                "--exporter-tool",
                "aiue_base_mesh_trial",
                "--exporter-version",
                "0.1",
                "--fusion-recipe-id",
                fixture_identity["fusion_recipe_id"],
                "--rig-profile-id",
                "rig_profile::base_mesh_trial::pending",
                "--material-profile-id",
                fixture_identity["material_profile_id"],
                "--mesh-output-name",
                extracted_mesh_path.name,
                "--notes",
                f"archive_id={archive_id}",
                "--notes",
                f"variant_id={result['variant_id']}",
            ]
            build_code, build_stdout, build_stderr = _run_python_script(build_script, build_args)
            result["build_stdout"] = build_stdout.strip()
            result["build_stderr"] = build_stderr.strip()
            if build_code != 0:
                result["status"] = "fail"
                result["failure_class"] = "provider_ready_source_handoff_build_failed"
                result["ue_suitability_signal"] = ue_suitability_signal(
                    attempted_format=attempted_format,
                    status=str(result["status"]),
                    bodypaint_handoff_candidate=False,
                    provider_ready_status="",
                )
                result["notes"] = ["provider_ready_source_handoff_build_failed"]
                per_item_results.append(result)
                continue

            build_summary_path = build_output_root / "build_provider_ready_source_handoff_summary.json"
            build_summary = load_json(build_summary_path) if build_summary_path.exists() else {}
            result["build_summary_path"] = str(build_summary_path)
            result["normalized_output_path"] = str(build_summary.get("zip_path") or "")
            result["normalized_mesh_path"] = str(build_summary.get("packaged_mesh_path") or "")
            result["handoff_zip_path"] = str(build_summary.get("zip_path") or "")
            result["manifest_path"] = str(build_summary.get("manifest_path") or "")

            check_output_root = item_output_root / "check"
            check_args = [
                "--workspace-config",
                str(Path(args.workspace_config).expanduser().resolve()),
                "--fixture-zip",
                str(result["handoff_zip_path"]),
                "--output-root",
                str(check_output_root),
                "--latest-report-path",
                str(check_output_root / "latest_provider_ready_check.json"),
                "--latest-provider-path",
                str(check_output_root / "latest_provider_preview.json"),
            ]
            check_code, check_stdout, check_stderr = _run_python_script(check_script, check_args)
            result["check_stdout"] = check_stdout.strip()
            result["check_stderr"] = check_stderr.strip()
            if check_code != 0:
                result["status"] = "fail"
                result["failure_class"] = "provider_ready_source_handoff_check_failed"
                result["ue_suitability_signal"] = ue_suitability_signal(
                    attempted_format=attempted_format,
                    status=str(result["status"]),
                    bodypaint_handoff_candidate=False,
                    provider_ready_status="",
                )
                result["notes"] = ["provider_ready_source_handoff_check_failed"]
                per_item_results.append(result)
                continue

            check_report_path = check_output_root / "c2_provider_ready_source_handoff_report.json"
            provider_preview_path = check_output_root / "converted_model_provider_preview.json"
            check_report = load_json(check_report_path) if check_report_path.exists() else {}
            provider_preview = load_json(provider_preview_path) if provider_preview_path.exists() else {}
            bodypaint_ready = bool(((provider_preview.get("consumer_hints") or {}).get("ready_for_bodypaint")))
            result["status"] = "pass"
            result["failure_class"] = ""
            result["bodypaint_handoff_candidate"] = bodypaint_ready
            result["provider_ready_status"] = str(check_report.get("status") or "")
            result["provider_preview_path"] = str(provider_preview_path)
            result["provider_ready_report_path"] = str(check_report_path)
            result["provider_preview"] = provider_preview
            result["failed_requirements"] = list(check_report.get("failed_requirements") or [])
            result["ue_suitability_signal"] = ue_suitability_signal(
                attempted_format=attempted_format,
                status=str(result["status"]),
                bodypaint_handoff_candidate=bodypaint_ready,
                provider_ready_status=str(result["provider_ready_status"]),
            )
            result["notes"] = [
                str(item.get("id") or "")
                for item in list(result.get("failed_requirements") or [])
                if str(item.get("id") or "")
            ]
            per_item_results.append(result)

    counts = {
        "archive_count": len(inventory_rows),
        "item_count": len(per_item_results),
        "passing_items": sum(1 for item in per_item_results if item.get("status") == "pass"),
        "failed_items": sum(1 for item in per_item_results if item.get("status") == "fail"),
        "blocked_items": sum(1 for item in per_item_results if item.get("status") == "blocked"),
        "bodypaint_handoff_candidate_count": sum(1 for item in per_item_results if item.get("bodypaint_handoff_candidate")),
    }
    failed_requirements: list[dict[str, object]] = []
    if counts["item_count"] == 0:
        failed_requirements.append({"id": "no_trial_items", "message": "No base mesh trial items were discovered from the admitted batch."})
    if counts["passing_items"] == 0:
        failed_requirements.append({"id": "no_successful_trial_items", "message": "BM0 did not produce any successfully classified trial items."})

    status = "pass" if counts["passing_items"] > 0 else "attention"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        latest_report_path if previous_report else None,
        "bm0_first_complete_pass",
    )

    report_payload = with_report_envelope(
        {
            "gate_id": GATE_ID,
            "status": status,
            "generated_at_utc": now_utc(),
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "inventory_path": str(inventory_path),
            "runbook_path": str(runbook_path),
            "counts": counts,
            "failed_requirements": failed_requirements,
            "per_item_results": per_item_results,
            "artifacts": {
                "report_root": str(output_root),
                "latest_report_path": str(latest_report_path),
            },
            "discussion_signal": discussion_signal,
        },
        schema_family="body_platform.base_mesh_trial.bm0",
        workflow_pack="body_platform",
        compatibility=make_compatibility_block(
            "body_platform.base_mesh_trial.bm0",
            notes=[
                "base mesh trial for toy-yard admitted source archives",
                "classifies format behavior honestly before promoting any subset to bodypaint handoff",
            ],
        ),
    )
    report_path = output_root / "base_mesh_trial_bm0_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)

    feedback_path = output_root / "toy_yard_base_mesh_trial_feedback.md"
    suitability_path = output_root / "base_mesh_ue_suitability_review.md"
    feedback_latest_path = _latest_markdown_path(workspace, "latest_toy_yard_base_mesh_trial_feedback.md")
    suitability_latest_path = _latest_markdown_path(workspace, "latest_base_mesh_ue_suitability_review.md")
    feedback_text = render_feedback_markdown(
        runbook_path=runbook_path,
        inventory_path=inventory_path,
        bm0_report=report_payload,
    )
    suitability_text = render_ue_suitability_markdown(bm0_report=report_payload)
    feedback_path.write_text(feedback_text + "\n", encoding="utf-8")
    suitability_path.write_text(suitability_text + "\n", encoding="utf-8")
    feedback_latest_path.write_text(feedback_text + "\n", encoding="utf-8")
    suitability_latest_path.write_text(suitability_text + "\n", encoding="utf-8")

    print(f"BM0 base mesh trial report written to: {report_path}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
