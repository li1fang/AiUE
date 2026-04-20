from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import default_latest_report_path, now_utc, run_stamp  # noqa: E402
from aiue_core.report_writer import make_compatibility_block, with_report_envelope  # noqa: E402
from aiue_core.schema_utils import load_workspace_config, write_json  # noqa: E402
from aiue_t1.bodypaint_candidate_pool import (  # noqa: E402
    build_conversion_indexes,
    collect_local_conversion_entries,
    ensure_tag_rows,
    match_candidate_to_entry,
    normalize_token,
    query_toy_yard_character_candidates,
)


GATE_ID = "bodypaint_candidate_pool_trial"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a semi-automatic BodyPaint candidate pool from current toy-yard character packages and local AiUE conversion outputs.")
    parser.add_argument("--workspace-config", default=str(REPO_ROOT / "local" / "pipeline_workspace.local.json"))
    parser.add_argument("--toy-yard-db", default=r"C:\Projects\toy-yard\_db\toyyard.sqlite")
    parser.add_argument("--conversion-root", default="")
    parser.add_argument("--output-root", default="")
    parser.add_argument("--latest-report-path", default="")
    parser.add_argument("--tag", default="游戏_二次元游戏")
    parser.add_argument("--apply-tags", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args()


def _python_executable() -> str:
    return sys.executable


def _build_script_path(name: str) -> Path:
    return REPO_ROOT / "workflows" / "pmx_pipeline" / name


def _run_python_script(script_path: Path, arguments: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(
        [_python_executable(), str(script_path), *arguments],
        capture_output=True,
    )
    def _decode(blob: bytes) -> str:
        for encoding in ("utf-8", "gbk", "cp936"):
            try:
                return blob.decode(encoding)
            except UnicodeDecodeError:
                continue
        return blob.decode("utf-8", errors="replace")

    return completed.returncode, _decode(completed.stdout), _decode(completed.stderr)


def _candidate_slug(candidate_display_name: str, package_db_id: int) -> str:
    token = normalize_token(candidate_display_name)
    return f"{package_db_id:03d}_{token or 'candidate'}"


def _make_fixture_identity(candidate_package_id: str, candidate_sample_id: str) -> tuple[str, str, str, str]:
    package_token = normalize_token(candidate_package_id)
    sample_token = normalize_token(candidate_sample_id)
    fixture_id = f"bodypaint_source::{package_token}::full_body::v1"
    body_family_id = f"bodypaint_source::{sample_token}"
    fusion_recipe_id = f"aiue_source_wrap::{package_token}::full_body_v1"
    material_profile_id = f"material_profile::{package_token}::source_scan_v1"
    return fixture_id, body_family_id, fusion_recipe_id, material_profile_id


def _backup_sqlite(sqlite_path: Path) -> Path:
    backup_root = sqlite_path.parent / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_path = backup_root / f"{sqlite_path.stem}_before_bodypaint_candidate_pool_{run_stamp()}{sqlite_path.suffix}"
    shutil.copy2(sqlite_path, backup_path)
    return backup_path


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "display_name",
        "canonical_package_id",
        "canonical_sample_id",
        "match_strategy",
        "source_mesh_path",
        "provider_ready_status",
        "ready_for_bodypaint",
        "handoff_zip_path",
        "provider_preview_path",
        "notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def main() -> int:
    args = parse_args()
    workspace_config_path = Path(args.workspace_config).expanduser().resolve()
    workspace = load_workspace_config(workspace_config_path)
    conversion_root = Path(args.conversion_root).expanduser().resolve() if args.conversion_root else Path((workspace.get("paths") or {}).get("conversion_root") or "").expanduser().resolve()
    if not conversion_root.exists():
        raise FileNotFoundError(f"Conversion root does not exist: {conversion_root}")

    toy_yard_db = Path(args.toy_yard_db).expanduser().resolve()
    if not toy_yard_db.exists():
        raise FileNotFoundError(f"toy-yard SQLite does not exist: {toy_yard_db}")

    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else REPO_ROOT / "local" / "body_platform" / "bodypaint_candidate_pool" / run_stamp()
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)
    latest_report_path.parent.mkdir(parents=True, exist_ok=True)

    candidates = query_toy_yard_character_candidates(toy_yard_db)
    if args.limit > 0:
        candidates = candidates[: args.limit]

    conversion_entries = collect_local_conversion_entries(conversion_root)
    conversion_indexes = build_conversion_indexes(conversion_entries)

    build_script = _build_script_path("run_build_provider_ready_source_handoff_sample.py")
    check_script = _build_script_path("run_check_c2_provider_ready_source_handoff.py")

    per_candidate_results: list[dict[str, object]] = []
    manual_pick_rows: list[dict[str, object]] = []
    tag_rows: list[tuple[str, int, str]] = []

    for candidate in candidates:
        matched_entry, match_strategy = match_candidate_to_entry(candidate, conversion_indexes)
        candidate_root = output_root / "candidates" / _candidate_slug(candidate.display_name, candidate.package_db_id)
        candidate_root.mkdir(parents=True, exist_ok=True)
        candidate_result: dict[str, object] = {
            "package_db_id": candidate.package_db_id,
            "sample_db_id": candidate.sample_db_id,
            "display_name": candidate.display_name,
            "canonical_package_id": candidate.canonical_package_id,
            "canonical_sample_id": candidate.canonical_sample_id,
            "package_role": candidate.package_role,
            "warehouse_status": candidate.warehouse_status,
            "match_strategy": match_strategy,
            "source_mesh_path": str(matched_entry.mesh_path) if matched_entry else "",
            "source_manifest_path": str(matched_entry.manifest_path) if matched_entry else "",
            "status": "unmatched" if matched_entry is None else "matched",
            "provider_ready_status": "not_built",
            "ready_for_bodypaint": False,
            "notes": [],
        }

        if matched_entry is None:
            candidate_result["notes"] = ["no_local_conversion_match"]
            per_candidate_results.append(candidate_result)
            continue

        fixture_id, body_family_id, fusion_recipe_id, material_profile_id = _make_fixture_identity(
            candidate.canonical_package_id,
            candidate.canonical_sample_id,
        )
        build_output_root = candidate_root / "build"
        build_args = [
            "--source-mesh",
            str(matched_entry.mesh_path),
            "--output-root",
            str(build_output_root),
            "--fixture-id",
            fixture_id,
            "--body-family-id",
            body_family_id,
            "--fixture-scope",
            "full_body",
            "--source-module-id",
            candidate.canonical_package_id,
            "--source-module-id",
            candidate.canonical_sample_id,
            "--exporter-tool",
            "aiue_source_wrap",
            "--exporter-version",
            "0.2",
            "--fusion-recipe-id",
            fusion_recipe_id,
            "--rig-profile-id",
            "rig_profile::bodypaint_source::pending",
            "--material-profile-id",
            material_profile_id,
            "--mesh-output-name",
            matched_entry.mesh_path.name,
            "--linear-unit",
            "cm",
            "--up-axis",
            "z",
            "--forward-axis",
            "x",
            "--notes",
            f"display_name={candidate.display_name}",
            "--notes",
            "semi-automatic bodypaint candidate pool trial",
        ]
        build_code, build_stdout, build_stderr = _run_python_script(build_script, build_args)
        candidate_result["build_stdout"] = build_stdout.strip()
        candidate_result["build_stderr"] = build_stderr.strip()
        if build_code != 0:
            candidate_result["status"] = "build_failed"
            candidate_result["notes"] = ["provider_ready_build_failed"]
            per_candidate_results.append(candidate_result)
            continue

        build_summary_path = build_output_root / "build_provider_ready_source_handoff_summary.json"
        if not build_summary_path.exists():
            candidate_result["status"] = "build_failed"
            candidate_result["notes"] = ["build_summary_missing"]
            per_candidate_results.append(candidate_result)
            continue

        build_summary = json.loads(build_summary_path.read_text(encoding="utf-8-sig"))
        zip_path = Path(str(build_summary.get("zip_path") or "")).expanduser().resolve()

        check_output_root = candidate_root / "check"
        check_args = [
            "--workspace-config",
            str(workspace_config_path),
            "--fixture-zip",
            str(zip_path),
            "--output-root",
            str(check_output_root),
            "--latest-report-path",
            str(check_output_root / "latest_bodypaint_candidate_check.json"),
            "--latest-provider-path",
            str(check_output_root / "latest_converted_model_provider.json"),
        ]
        check_code, check_stdout, check_stderr = _run_python_script(check_script, check_args)
        candidate_result["check_stdout"] = check_stdout.strip()
        candidate_result["check_stderr"] = check_stderr.strip()
        if check_code != 0:
            candidate_result["status"] = "check_failed"
            candidate_result["notes"] = ["provider_ready_check_failed"]
            per_candidate_results.append(candidate_result)
            continue

        check_report_path = check_output_root / "c2_provider_ready_source_handoff_report.json"
        provider_preview_path = check_output_root / "converted_model_provider_preview.json"
        if not check_report_path.exists():
            candidate_result["status"] = "check_failed"
            candidate_result["notes"] = ["provider_ready_report_missing"]
            per_candidate_results.append(candidate_result)
            continue

        check_report = json.loads(check_report_path.read_text(encoding="utf-8-sig"))
        provider_preview = json.loads(provider_preview_path.read_text(encoding="utf-8-sig")) if provider_preview_path.exists() else {}
        ready_for_bodypaint = bool(((provider_preview.get("consumer_hints") or {}).get("ready_for_bodypaint")))
        candidate_result.update(
            {
                "status": "pass" if ready_for_bodypaint else "attention",
                "handoff_zip_path": str(zip_path),
                "provider_ready_status": str(check_report.get("status") or ""),
                "ready_for_bodypaint": ready_for_bodypaint,
                "provider_preview_path": str(provider_preview_path),
                "failed_requirements": list(check_report.get("failed_requirements") or []),
            }
        )
        candidate_result["notes"] = [str(item.get("id") or "") for item in candidate_result["failed_requirements"]] if candidate_result["failed_requirements"] else []
        per_candidate_results.append(candidate_result)

        manual_pick_rows.append(
            {
                "display_name": candidate.display_name,
                "canonical_package_id": candidate.canonical_package_id,
                "canonical_sample_id": candidate.canonical_sample_id,
                "match_strategy": match_strategy,
                "source_mesh_path": str(matched_entry.mesh_path),
                "provider_ready_status": str(check_report.get("status") or ""),
                "ready_for_bodypaint": ready_for_bodypaint,
                "handoff_zip_path": str(zip_path),
                "provider_preview_path": str(provider_preview_path),
                "notes": ";".join(candidate_result["notes"]),
            }
        )
        tag_rows.append(("sample", candidate.sample_db_id, args.tag))
        tag_rows.append(("package", candidate.package_db_id, args.tag))

    sqlite_backup_path = ""
    inserted_tag_count = 0
    if args.apply_tags and tag_rows:
        sqlite_backup_path = str(_backup_sqlite(toy_yard_db))
        inserted_tag_count = ensure_tag_rows(toy_yard_db, tag_rows)

    manual_pick_rows.sort(
        key=lambda row: (
            0 if row.get("ready_for_bodypaint") else 1,
            str(row.get("display_name") or ""),
        )
    )
    manual_pick_json_path = output_root / "manual_pick_pool.json"
    manual_pick_csv_path = output_root / "manual_pick_pool.csv"
    write_json(manual_pick_json_path, {"generated_at_utc": now_utc(), "rows": manual_pick_rows})
    _write_csv(manual_pick_csv_path, manual_pick_rows)

    counts = {
        "candidate_count": len(candidates),
        "matched_local_conversion_count": sum(1 for item in per_candidate_results if item["status"] != "unmatched"),
        "handoff_built_count": sum(1 for item in per_candidate_results if item.get("handoff_zip_path")),
        "provider_ready_count": sum(1 for item in per_candidate_results if item.get("provider_ready_status") == "pass"),
        "ready_for_bodypaint_count": sum(1 for item in per_candidate_results if item.get("ready_for_bodypaint")),
        "unmatched_count": sum(1 for item in per_candidate_results if item["status"] == "unmatched"),
        "build_failed_count": sum(1 for item in per_candidate_results if item["status"] == "build_failed"),
        "check_failed_count": sum(1 for item in per_candidate_results if item["status"] == "check_failed"),
        "tagged_entity_count": inserted_tag_count,
    }

    failed_requirements: list[dict[str, object]] = []
    if counts["ready_for_bodypaint_count"] == 0:
        failed_requirements.append(
            {
                "id": "no_bodypaint_ready_candidates",
                "message": "No matched candidate completed the provider-ready handoff check.",
            }
        )
    if counts["unmatched_count"] > 0:
        failed_requirements.append(
            {
                "id": "candidate_discovery_incomplete",
                "message": "Some toy-yard character candidates could not be matched to current local conversion outputs.",
                "unmatched_count": counts["unmatched_count"],
            }
        )

    status = "pass" if not failed_requirements else "attention"
    report_payload = with_report_envelope(
        {
            "gate_id": GATE_ID,
            "status": status,
            "generated_at_utc": now_utc(),
            "workspace_config": str(workspace_config_path),
            "toy_yard_db": str(toy_yard_db),
            "conversion_root": str(conversion_root),
            "tag": args.tag,
            "apply_tags": bool(args.apply_tags),
            "counts": counts,
            "failed_requirements": failed_requirements,
            "per_candidate_results": per_candidate_results,
            "manual_pick_inventory": {
                "json_path": str(manual_pick_json_path),
                "csv_path": str(manual_pick_csv_path),
                "ready_candidates": [
                    {
                        "display_name": row["display_name"],
                        "canonical_package_id": row["canonical_package_id"],
                        "handoff_zip_path": row["handoff_zip_path"],
                        "provider_preview_path": row["provider_preview_path"],
                    }
                    for row in manual_pick_rows
                    if row.get("ready_for_bodypaint")
                ],
            },
            "artifacts": {
                "output_root": str(output_root),
                "latest_report_path": str(latest_report_path),
                "sqlite_backup_path": sqlite_backup_path,
            },
        },
        schema_family="body_platform.bodypaint_candidate_pool.trial",
        workflow_pack="body_platform",
        compatibility=make_compatibility_block(
            "body_platform.bodypaint_candidate_pool.trial",
            notes=[
                "semi-automatic candidate pool for manual BodyPaint selection",
                "uses local AiUE conversion outputs to build provider-ready handoff samples",
            ],
        ),
    )

    report_path = output_root / "bodypaint_candidate_pool_trial_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    print(f"BodyPaint candidate pool report written to: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
