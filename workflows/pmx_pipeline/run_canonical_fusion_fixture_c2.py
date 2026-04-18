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
from aiue_t1.canonical_fusion import inspect_canonical_fusion_fixture, stage_canonical_fusion_source  # noqa: E402
from aiue_t1.converted_model_provider import (  # noqa: E402
    build_converted_model_provider_from_c2_report,
    default_latest_converted_model_provider_path,
    write_converted_model_provider,
)


GATE_ID = "canonical_fusion_fixture_c2"
SOURCE_GATE_ID = "parametric_body_contract_c1"
ALLOWED_FIXTURE_SCOPES = {
    "canonical_fused_body",
    "full_body",
    "lower_body_core",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect and validate the first Houdini canonical fusion fixture handoff.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--source-report")
    parser.add_argument("--fixture-zip")
    parser.add_argument("--fixture-root")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    parser.add_argument("--latest-provider-path")
    return parser.parse_args()


def resolve_source_report_path(workspace: dict, explicit_path: str | None) -> Path | None:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Source report path does not exist: {candidate}")
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    candidate = repo_root / "Saved" / "verification" / f"latest_{SOURCE_GATE_ID}_report.json"
    return candidate.resolve() if candidate.exists() else None


def resolve_fixture_input_path(workspace: dict, *, explicit_zip: str | None, explicit_root: str | None) -> Path:
    if explicit_zip:
        candidate = Path(explicit_zip).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Fixture zip does not exist: {candidate}")
    if explicit_root:
        candidate = Path(explicit_root).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Fixture root does not exist: {candidate}")
    configured_path = str(((workspace.get("paths") or {}).get("body_fusion_fixture_root")) or "")
    if not configured_path:
        raise FileNotFoundError("No fixture input was provided and workspace.paths.body_fusion_fixture_root is not configured.")
    candidate = Path(configured_path).expanduser().resolve()
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Configured body_fusion_fixture_root does not exist: {candidate}")


def evaluate_fixture(fixture: dict, *, c1_report: dict | None, source_report_path: Path | None) -> tuple[str, list[dict]]:
    failed_requirements: list[dict] = []
    source_status = str((c1_report or {}).get("status") or "")
    source_body_family_id = str((c1_report or {}).get("body_family_id") or "")
    fixture_body_family_id = str(fixture.get("body_family_id") or "")

    if c1_report is None:
        failed_requirements.append(
            make_failed_requirement(
                "c2_source_c1_missing",
                "C2 prefers a latest C1 parametric body contract report so the Houdini fixture can inherit a stable family contract.",
                source_report=str(source_report_path or ""),
            )
        )
    elif source_status != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "c2_source_c1_not_pass",
                "C2 requires a passing C1 parametric body contract report.",
                source_report=str(source_report_path or ""),
                source_status=source_status,
            )
        )

    if not bool(fixture.get("manifest_present")):
        failed_requirements.append(
            make_failed_requirement(
                "c2_manifest_missing",
                "A qualified C2 handoff requires a canonical fusion manifest beside the Houdini mesh export.",
                source_root=str(fixture.get("source_root") or ""),
            )
        )
    if not str(fixture.get("primary_mesh_abs_path") or ""):
        failed_requirements.append(
            make_failed_requirement(
                "c2_primary_mesh_missing",
                "C2 requires exactly one resolvable primary mesh file.",
                source_root=str(fixture.get("source_root") or ""),
            )
        )

    fixture_scope = str(fixture.get("fixture_scope") or "")
    if not fixture_scope:
        failed_requirements.append(
            make_failed_requirement(
                "c2_fixture_scope_missing",
                "C2 requires an explicit fixture_scope in the Houdini manifest.",
            )
        )
    elif fixture_scope not in ALLOWED_FIXTURE_SCOPES:
        failed_requirements.append(
            make_failed_requirement(
                "c2_fixture_scope_invalid",
                "C2 only accepts the current narrow body scopes.",
                fixture_scope=fixture_scope,
                allowed_scopes=sorted(ALLOWED_FIXTURE_SCOPES),
            )
        )

    if not fixture_body_family_id:
        failed_requirements.append(
            make_failed_requirement(
                "c2_body_family_missing",
                "C2 requires a body_family_id so the Houdini output can be routed back into the body-platform line.",
            )
        )
    elif source_body_family_id and fixture_body_family_id != source_body_family_id:
        failed_requirements.append(
            make_failed_requirement(
                "c2_body_family_mismatch",
                "C2 fixture body_family_id must match the selected C1 contract family.",
                fixture_body_family_id=fixture_body_family_id,
                c1_body_family_id=source_body_family_id,
            )
        )

    if not list(fixture.get("source_module_ids") or []):
        failed_requirements.append(
            make_failed_requirement(
                "c2_source_module_ids_missing",
                "C2 requires source_module_ids so the fused artifact can be traced back to modular inputs.",
            )
        )

    exporter = dict(fixture.get("exporter") or {})
    exporter_tool = str(exporter.get("tool") or "").lower()
    if exporter_tool != "houdini":
        failed_requirements.append(
            make_failed_requirement(
                "c2_exporter_not_houdini",
                "The first C2 handoff must be authored and exported by Houdini.",
                exporter_tool=exporter_tool,
            )
        )

    coordinate_system = dict(fixture.get("coordinate_system") or {})
    linear_unit = str(coordinate_system.get("linear_unit") or "").lower()
    up_axis = str(coordinate_system.get("up_axis") or "").lower()
    if linear_unit not in {"cm", "centimeter", "centimeters"}:
        failed_requirements.append(
            make_failed_requirement(
                "c2_linear_unit_invalid",
                "C2 requires UE-facing centimeter export metadata.",
                linear_unit=linear_unit,
            )
        )
    if up_axis != "z":
        failed_requirements.append(
            make_failed_requirement(
                "c2_up_axis_invalid",
                "C2 requires explicit Z-up export metadata for the qualified handoff package.",
                up_axis=up_axis,
            )
        )

    manifest = dict(fixture.get("manifest") or {})
    if not str(manifest.get("fusion_recipe_id") or ""):
        failed_requirements.append(
            make_failed_requirement(
                "c2_fusion_recipe_missing",
                "C2 requires a fusion_recipe_id so Linux Houdini automation can replay the same recipe deterministically.",
            )
        )

    return ("pass" if not failed_requirements else "attention", failed_requirements)


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    latest_provider_path = (
        Path(args.latest_provider_path).expanduser().resolve()
        if args.latest_provider_path
        else default_latest_converted_model_provider_path(REPO_ROOT)
    )
    output_root.mkdir(parents=True, exist_ok=True)
    latest_provider_path.parent.mkdir(parents=True, exist_ok=True)

    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None

    source_report_path = resolve_source_report_path(workspace, args.source_report)
    c1_report = load_json(source_report_path) if source_report_path and source_report_path.exists() else None

    fixture_input_path = resolve_fixture_input_path(
        workspace,
        explicit_zip=args.fixture_zip,
        explicit_root=args.fixture_root,
    )
    staging = stage_canonical_fusion_source(fixture_input_path, output_root=output_root)
    fixture = inspect_canonical_fusion_fixture(staging["staged_root"])

    manifest = dict(fixture.get("manifest") or {})
    canonical_fusion_fixture = {
        **fixture,
        "fusion_recipe_id": str(manifest.get("fusion_recipe_id") or ""),
        "rig_profile_id": str(manifest.get("rig_profile_id") or ""),
        "material_profile_id": str(manifest.get("material_profile_id") or ""),
    }

    status, failed_requirements = evaluate_fixture(
        canonical_fusion_fixture,
        c1_report=c1_report,
        source_report_path=source_report_path,
    )

    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        latest_report_path if latest_report_path.exists() else None,
        "c2_canonical_fusion_fixture_first_pass",
    )

    source_inventory_summary = dict((c1_report or {}).get("source_inventory_summary") or {})
    body_family_id = str(canonical_fusion_fixture.get("body_family_id") or source_inventory_summary.get("canonical_fixture_family_id") or "")
    report_payload = with_report_envelope(
        {
            "gate_id": GATE_ID,
            "status": status,
            "generated_at_utc": now_utc(),
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_report": str(source_report_path or ""),
            "source_input_path": str(fixture_input_path),
            "body_family_id": body_family_id,
            "fixture_id": str(canonical_fusion_fixture.get("fixture_id") or ""),
            "canonical_fusion_fixture": canonical_fusion_fixture,
            "counts": dict(canonical_fusion_fixture.get("counts") or {}),
            "source_inventory_summary": source_inventory_summary,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "report_root": str(output_root),
                "latest_report_path": str(latest_report_path),
                "staged_root": str(staging.get("staged_root") or ""),
            },
        },
        schema_family="body_platform.canonical_fusion_fixture.c2",
        workflow_pack="body_platform",
        compatibility=make_compatibility_block(
            "body_platform.canonical_fusion_fixture.c2",
            notes=[
                "internal body-platform fusion fixture report",
                "qualifies the first Houdini handoff package rather than a runtime-ready avatar",
            ],
        ),
    )

    report_path = output_root / "canonical_fusion_fixture_report.json"
    latest_alias_path = output_root / "canonical_fusion_fixture_latest.json"
    provider_path = output_root / "converted_model_provider.json"
    provider_latest_alias_path = output_root / "converted_model_provider_latest.json"
    report_payload["artifacts"]["converted_model_provider_path"] = str(provider_path)
    report_payload["artifacts"]["latest_provider_path"] = str(latest_provider_path)
    write_report_pair(report_payload, report_path, latest_report_path)
    write_json(latest_alias_path, report_payload)
    provider_payload = build_converted_model_provider_from_c2_report(
        report_payload,
        report_source_path=report_path,
    )
    write_converted_model_provider(provider_path, provider_payload)
    write_converted_model_provider(provider_latest_alias_path, provider_payload)
    write_converted_model_provider(latest_provider_path, provider_payload)
    print(f"C2 canonical fusion fixture report written to: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
