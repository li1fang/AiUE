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
from aiue_t1.body_platform import build_parametric_body_contract  # noqa: E402


GATE_ID = "parametric_body_contract_c1"
SOURCE_GATE_ID = "modular_morphology_inventory_c0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the C1 parametric body contract from the latest C0 body inventory.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--source-report")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def resolve_source_report_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Source report path does not exist: {candidate}")
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    candidate = repo_root / "Saved" / "verification" / f"latest_{SOURCE_GATE_ID}_report.json"
    if candidate.exists():
        return candidate.resolve()
    raise FileNotFoundError(f"Latest C0 report is missing: {candidate}")


def evaluate_contract(contract: dict, *, source_report: dict, source_report_path: Path) -> tuple[str, list[dict]]:
    failed_requirements: list[dict] = []
    if str(source_report.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "c1_source_c0_not_pass",
                "C1 requires a passing C0 modular morphology inventory report.",
                source_report=str(source_report_path),
                source_status=str(source_report.get("status") or ""),
            )
        )
    if not str(contract.get("body_family_id") or ""):
        failed_requirements.append(
            make_failed_requirement(
                "c1_body_family_missing",
                "C1 could not resolve a canonical body family from the C0 inventory.",
                source_report=str(source_report_path),
            )
        )
    if not str(contract.get("core_module_id") or ""):
        failed_requirements.append(
            make_failed_requirement(
                "c1_core_module_missing",
                "C1 requires a fixed core_torso_arm module.",
                body_family_id=str(contract.get("body_family_id") or ""),
            )
        )
    if not list(contract.get("supported_head_ids") or []):
        failed_requirements.append(
            make_failed_requirement(
                "c1_supported_heads_missing",
                "C1 requires at least one supported head module.",
                body_family_id=str(contract.get("body_family_id") or ""),
            )
        )
    if not list(contract.get("supported_bust_classes") or []):
        failed_requirements.append(
            make_failed_requirement(
                "c1_supported_bust_classes_missing",
                "C1 requires at least one supported bust module.",
                body_family_id=str(contract.get("body_family_id") or ""),
            )
        )
    if not list(contract.get("supported_leg_length_profiles") or []):
        failed_requirements.append(
            make_failed_requirement(
                "c1_supported_leg_profiles_missing",
                "C1 requires at least one supported leg-length profile.",
                body_family_id=str(contract.get("body_family_id") or ""),
            )
        )
    return ("pass" if not failed_requirements else "fail", failed_requirements)


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)

    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    source_report_path = resolve_source_report_path(workspace, args.source_report)
    source_report = load_json(source_report_path)
    contract = build_parametric_body_contract(source_report)
    status, failed_requirements = evaluate_contract(contract, source_report=source_report, source_report_path=source_report_path)

    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        latest_report_path if latest_report_path.exists() else None,
        "c1_parametric_body_contract_first_pass",
    )

    report_payload = with_report_envelope(
        {
            "gate_id": GATE_ID,
            "status": status,
            "generated_at_utc": now_utc(),
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_report": str(source_report_path),
            "body_family_id": str(contract.get("body_family_id") or ""),
            "contract_id": str(contract.get("contract_id") or ""),
            "parametric_body_contract": contract,
            "counts": {
                "supported_head_count": len(list(contract.get("supported_head_ids") or [])),
                "supported_bust_class_count": len(list(contract.get("supported_bust_classes") or [])),
                "supported_leg_length_profile_count": len(list(contract.get("supported_leg_length_profiles") or [])),
                "compatible_hair_count": len(list(contract.get("compatible_hair_ids") or [])),
            },
            "source_inventory_summary": {
                "source_root": str(source_report.get("source_root") or ""),
                "counts": dict(source_report.get("counts") or {}),
                "module_kind_counts": dict(source_report.get("module_kind_counts") or {}),
                "canonical_fixture_family_id": str(source_report.get("canonical_fixture_family_id") or ""),
                "per_family_results": list(source_report.get("per_family_results") or []),
            },
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "report_root": str(output_root),
                "latest_report_path": str(latest_report_path),
            },
        },
        schema_family="body_platform.parametric_body_contract.c1",
        workflow_pack="body_platform",
        compatibility=make_compatibility_block(
            "body_platform.parametric_body_contract.c1",
            notes=[
                "internal body-platform contract report",
                "derived from the selected canonical family in C0",
            ],
        ),
    )

    report_path = output_root / "parametric_body_contract_report.json"
    latest_alias_path = output_root / "parametric_body_contract_latest.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    write_json(latest_alias_path, report_payload)
    print(f"C1 parametric body contract report written to: {report_path}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
