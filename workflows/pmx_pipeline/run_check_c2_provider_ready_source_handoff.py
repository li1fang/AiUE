from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _c2_handoff_common import build_provider_ready_checklist, evaluate_provider_ready_source_handoff  # noqa: E402
from _gate_common import default_latest_report_path, default_output_root, now_utc, repo_root_from_workspace  # noqa: E402
from aiue_core.report_writer import make_compatibility_block, with_report_envelope  # noqa: E402
from aiue_core.schema_utils import load_workspace_config, write_json  # noqa: E402
from aiue_t1.canonical_fusion import inspect_canonical_fusion_fixture, stage_canonical_fusion_source  # noqa: E402
from aiue_t1.converted_model_provider import build_converted_model_provider_from_c2_report, write_converted_model_provider  # noqa: E402


GATE_ID = "c2_provider_ready_source_handoff_check"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether a raw Houdini handoff zip or directory is provider-ready for BodyPaint intake.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--fixture-zip")
    parser.add_argument("--fixture-root")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    parser.add_argument("--latest-provider-path")
    return parser.parse_args()


def make_failed_requirement(requirement_id: str, reason: str, **details: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": requirement_id,
        "reason": reason,
    }
    for key, value in details.items():
        if value not in (None, "", [], {}):
            payload[key] = value
    return payload


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
    configured_path = str(((workspace.get('paths') or {}).get('body_fusion_fixture_root')) or "")
    if not configured_path:
        raise FileNotFoundError("No fixture input was provided and workspace.paths.body_fusion_fixture_root is not configured.")
    candidate = Path(configured_path).expanduser().resolve()
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Configured body_fusion_fixture_root does not exist: {candidate}")


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    latest_provider_path = Path(args.latest_provider_path).expanduser().resolve() if args.latest_provider_path else repo_root_from_workspace(workspace, REPO_ROOT) / "Saved" / "body_platform" / "c2" / "latest" / "converted_model_provider_provider_ready_check_v0_1.json"
    output_root.mkdir(parents=True, exist_ok=True)
    latest_provider_path.parent.mkdir(parents=True, exist_ok=True)

    fixture_input_path = resolve_fixture_input_path(
        workspace,
        explicit_zip=args.fixture_zip,
        explicit_root=args.fixture_root,
    )
    staging = stage_canonical_fusion_source(fixture_input_path, output_root=output_root)
    fixture = inspect_canonical_fusion_fixture(staging["staged_root"])

    manifest = dict(fixture.get("manifest") or {})
    fixture_payload = {
        **fixture,
        "fusion_recipe_id": str(manifest.get("fusion_recipe_id") or ""),
        "rig_profile_id": str(manifest.get("rig_profile_id") or ""),
        "material_profile_id": str(manifest.get("material_profile_id") or ""),
    }

    status, failed_requirements = evaluate_provider_ready_source_handoff(
        fixture_payload,
        make_failed_requirement=make_failed_requirement,
    )
    failed_ids = {str(item.get("id") or "") for item in failed_requirements}
    checklist = build_provider_ready_checklist(fixture_payload, failed_ids=failed_ids)

    provider_seed_report = {
        "gate_id": "canonical_fusion_fixture_c2",
        "status": "pass" if status == "pass" else "attention",
        "generated_at_utc": now_utc(),
        "body_family_id": str(fixture_payload.get("body_family_id") or ""),
        "fixture_id": str(fixture_payload.get("fixture_id") or ""),
        "canonical_fusion_fixture": fixture_payload,
        "failed_requirements": failed_requirements,
    }
    provider_preview_path = output_root / "converted_model_provider_preview.json"
    provider_payload = build_converted_model_provider_from_c2_report(
        provider_seed_report,
        report_source_path=output_root / "c2_provider_ready_source_handoff_report.json",
    )

    report_payload = with_report_envelope(
        {
            "gate_id": GATE_ID,
            "status": status,
            "generated_at_utc": now_utc(),
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_input_path": str(fixture_input_path),
            "provider_ready_source_handoff": fixture_payload,
            "provider_preview": provider_payload,
            "checklist": checklist,
            "failed_requirements": failed_requirements,
            "artifacts": {
                "report_root": str(output_root),
                "latest_report_path": str(latest_report_path),
                "staged_root": str(staging.get("staged_root") or ""),
                "provider_preview_path": str(provider_preview_path),
                "latest_provider_preview_path": str(latest_provider_path),
            },
        },
        schema_family="body_platform.provider_ready_source_handoff.c2",
        workflow_pack="body_platform",
        compatibility=make_compatibility_block(
            "body_platform.provider_ready_source_handoff.c2",
            notes=[
                "internal handoff preflight for upstream C2 source packages",
                "separates package-shape validation from the stricter repository-integrated C2 gate",
            ],
        ),
    )

    report_path = output_root / "c2_provider_ready_source_handoff_report.json"
    latest_alias_path = output_root / "c2_provider_ready_source_handoff_latest.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    write_json(latest_alias_path, report_payload)
    write_converted_model_provider(provider_preview_path, provider_payload)
    write_converted_model_provider(latest_provider_path, provider_payload)
    print(f"C2 provider-ready source handoff report written to: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
