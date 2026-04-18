from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from aiue_core.schema_utils import load_json, load_workspace_config  # noqa: E402
from aiue_t1.converted_model_provider import (  # noqa: E402
    build_converted_model_provider_from_c2_report,
    default_latest_converted_model_provider_path,
    PROVIDER_NAME,
    PROVIDER_VERSION,
    write_converted_model_provider,
)


DEFAULT_C2_REPORT_NAME = "latest_canonical_fusion_fixture_c2_report.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve the AiUE converted model provider JSON from the latest C2 body-platform report.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--c2-report")
    parser.add_argument("--output-path")
    parser.add_argument("--latest-output-path")
    return parser.parse_args()


def _default_c2_report_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "verification" / DEFAULT_C2_REPORT_NAME


def _not_found_provider(*, note: str) -> dict:
    return {
        "version": PROVIDER_VERSION,
        "status": "not_found",
        "provider": PROVIDER_NAME,
        "consumer_hints": {
            "ready_for_bodypaint": False,
            "ready_for_ue": False,
        },
        "identity": {
            "sample_id": "",
            "package_id": "",
            "profile": "",
            "body_family_id": "",
            "fixture_id": "",
        },
        "primary_asset": {
            "path": "",
            "format": "",
            "role": "converted_model",
        },
        "companions": [],
        "lineage": {},
        "conversion": {
            "tool": "",
            "tool_version": "",
            "generated_at_utc": "",
            "source_gate_id": "canonical_fusion_fixture_c2",
        },
        "body_platform": {
            "source_gate_id": "canonical_fusion_fixture_c2",
            "body_family_id": "",
            "fixture_id": "",
            "fixture_scope": "",
            "fusion_recipe_id": "",
            "rig_profile_id": "",
            "material_profile_id": "",
        },
        "warnings": [],
        "notes": [note],
    }


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = Path((workspace.get("paths") or {}).get("aiue_repo_root") or REPO_ROOT).expanduser().resolve()
    c2_report_path = Path(args.c2_report).expanduser().resolve() if args.c2_report else _default_c2_report_path(repo_root)
    latest_output_path = (
        Path(args.latest_output_path).expanduser().resolve()
        if args.latest_output_path
        else default_latest_converted_model_provider_path(repo_root)
    )
    output_path = Path(args.output_path).expanduser().resolve() if args.output_path else latest_output_path

    if c2_report_path.exists():
        c2_report = load_json(c2_report_path)
        provider_payload = build_converted_model_provider_from_c2_report(
            c2_report,
            report_source_path=c2_report_path,
        )
    else:
        provider_payload = _not_found_provider(note=f"c2 report not found: {c2_report_path}")

    write_converted_model_provider(output_path, provider_payload)
    if output_path != latest_output_path:
        write_converted_model_provider(latest_output_path, provider_payload)
    print(f"Converted model provider JSON written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
