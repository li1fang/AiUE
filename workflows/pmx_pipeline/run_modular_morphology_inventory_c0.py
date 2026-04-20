from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import (  # noqa: E402
    build_discussion_signal,
    default_latest_report_path,
    default_output_root,
    make_failed_requirement,
    now_utc,
    repo_root_from_workspace,
    write_report_pair,
)
from aiue_core.report_writer import make_compatibility_block, with_report_envelope  # noqa: E402
from aiue_core.schema_utils import load_json, load_workspace_config, write_json  # noqa: E402
from aiue_t1.body_platform import build_modular_morphology_inventory  # noqa: E402


GATE_ID = "modular_morphology_inventory_c0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventory modular morphology assets for the C0 body-platform line.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--source-root")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def resolve_source_root(workspace: dict, explicit_source_root: str | None) -> Path:
    if explicit_source_root:
        return Path(explicit_source_root).expanduser().resolve()
    paths = dict(workspace.get("paths") or {})
    for key in ("body_morphology_source_root", "parametric_body_source_root"):
        value = str(paths.get(key) or "")
        if value:
            return Path(value).expanduser().resolve()
    raise FileNotFoundError(
        "Workspace is missing 'paths.body_morphology_source_root' (or the legacy alias "
        "'paths.parametric_body_source_root')."
    )


def evaluate_inventory(inventory: dict, *, source_root_exists: bool) -> tuple[str, list[dict]]:
    failed_requirements: list[dict] = []
    counts = dict(inventory.get("counts") or {})
    if not source_root_exists:
        failed_requirements.append(
            make_failed_requirement(
                "c0_source_root_missing",
                "The configured body morphology source root does not exist.",
                source_root=str(inventory.get("source_root") or ""),
            )
        )
    if int(counts.get("module_count") or 0) <= 0:
        failed_requirements.append(
            make_failed_requirement(
                "c0_no_mesh_modules_found",
                "No supported mesh modules were discovered under the body morphology source root.",
                source_root=str(inventory.get("source_root") or ""),
            )
        )
    if int(counts.get("candidate_fixture_family_count") or 0) <= 0:
        failed_requirements.append(
            make_failed_requirement(
                "c0_no_candidate_fixture_family",
                "The modular inventory did not find a canonical fixture family with head, bust, leg, and core modules.",
                source_root=str(inventory.get("source_root") or ""),
                discovered_families=int(counts.get("family_count") or 0),
            )
        )
    return ("pass" if not failed_requirements else "fail", failed_requirements)


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)

    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    source_root_error = ""
    try:
        source_root = resolve_source_root(workspace, args.source_root)
        inventory = build_modular_morphology_inventory(source_root)
        status, failed_requirements = evaluate_inventory(inventory, source_root_exists=source_root.exists())
    except FileNotFoundError as exc:
        source_root = Path(args.source_root).expanduser().resolve() if args.source_root else Path()
        source_root_error = str(exc)
        inventory = {
            "source_root": str(source_root),
            "selection_policy": {},
            "counts": {
                "module_count": 0,
                "family_count": 0,
                "candidate_fixture_family_count": 0,
            },
            "module_kind_counts": {},
            "source_extension_counts": {},
            "module_examples_by_kind": {},
            "canonical_fixture_family_id": "",
            "candidate_fixture_family_ids": [],
            "per_family_results": [],
        }
        status = "fail"
        failed_requirements = [
            make_failed_requirement(
                "c0_source_root_unconfigured",
                "C0 requires a body-platform source root, but the current workspace does not provide one.",
                workspace_config=str(Path(args.workspace_config).expanduser().resolve()),
                source_root_error=source_root_error,
            )
        ]

    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        latest_report_path if latest_report_path.exists() else None,
        "c0_modular_morphology_inventory_first_pass",
    )

    report_payload = with_report_envelope(
        {
            "gate_id": GATE_ID,
            "status": status,
            "generated_at_utc": now_utc(),
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_root": str(source_root),
            "selection_policy": dict(inventory.get("selection_policy") or {}),
            "counts": dict(inventory.get("counts") or {}),
            "module_kind_counts": dict(inventory.get("module_kind_counts") or {}),
            "source_extension_counts": dict(inventory.get("source_extension_counts") or {}),
            "module_examples_by_kind": dict(inventory.get("module_examples_by_kind") or {}),
            "canonical_fixture_family_id": str(inventory.get("canonical_fixture_family_id") or ""),
            "candidate_fixture_family_ids": list(inventory.get("candidate_fixture_family_ids") or []),
            "per_family_results": list(inventory.get("per_family_results") or []),
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "report_root": str(output_root),
                "latest_report_path": str(latest_report_path),
            },
            "environment": {
                "source_root_error": source_root_error,
            },
        },
        schema_family="body_platform.modular_morphology_inventory.c0",
        workflow_pack="body_platform",
        compatibility=make_compatibility_block(
            "body_platform.modular_morphology_inventory.c0",
            notes=[
                "internal body-platform inventory report",
                "heuristic module classification over local source root",
            ],
        ),
    )

    report_path = output_root / "modular_morphology_inventory_report.json"
    latest_alias_path = output_root / "modular_morphology_inventory_latest.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    write_json(latest_alias_path, report_payload)
    print(f"C0 modular morphology inventory report written to: {report_path}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
