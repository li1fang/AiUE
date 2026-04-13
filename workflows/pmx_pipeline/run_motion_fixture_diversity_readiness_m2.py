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
    make_failed_requirement,
    now_utc,
    repo_root_from_workspace,
    write_report_pair,
)
from aiue_core.report_writer import make_compatibility_block, with_report_envelope  # noqa: E402
from aiue_core.schema_utils import load_json, load_workspace_config  # noqa: E402
from toy_yard_view import (  # noqa: E402
    resolve_toy_yard_motion_registry_path,
    resolve_toy_yard_motion_summary_path,
    resolve_toy_yard_motion_view_root,
)


GATE_ID = "motion_fixture_diversity_readiness_m2"
MIN_DISTINCT_SCENARIOS = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether the current toy-yard motion export is ready for M2 fixture diversity.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--summary-path")
    parser.add_argument("--registry-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def resolve_summary_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Summary path does not exist: {candidate}")
    candidate = resolve_toy_yard_motion_summary_path(workspace)
    if candidate:
        return candidate
    raise FileNotFoundError("No toy-yard motion summary path could be resolved.")


def resolve_registry_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Registry path does not exist: {candidate}")
    candidate = resolve_toy_yard_motion_registry_path(workspace)
    if candidate:
        return candidate
    raise FileNotFoundError("No toy-yard motion registry path could be resolved.")


def classify_selection_ready_clips(registry_payload: dict[str, Any]) -> dict[str, Any]:
    clips = list(registry_payload.get("clips") or [])
    selection_ready = [dict(item) for item in clips if bool(item.get("selection_ready"))]
    distinct_scenarios = sorted({str(item.get("scenario_id") or "").strip() for item in selection_ready if str(item.get("scenario_id") or "").strip()})
    distinct_samples = sorted({str(item.get("sample_id") or "").strip() for item in selection_ready if str(item.get("sample_id") or "").strip()})
    by_scenario: dict[str, list[str]] = {}
    for item in selection_ready:
        scenario_id = str(item.get("scenario_id") or "").strip() or "<missing>"
        by_scenario.setdefault(scenario_id, []).append(str(item.get("package_id") or ""))
    return {
        "selection_ready_count": len(selection_ready),
        "distinct_scenario_ids": distinct_scenarios,
        "distinct_sample_ids": distinct_samples,
        "packages_by_scenario": by_scenario,
        "selection_ready_packages": [str(item.get("package_id") or "") for item in selection_ready],
    }


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)

    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    summary_path = resolve_summary_path(workspace, args.summary_path)
    registry_path = resolve_registry_path(workspace, args.registry_path)
    summary_payload = load_json(summary_path)
    registry_payload = load_json(registry_path)
    diversity = classify_selection_ready_clips(registry_payload)

    failed_requirements: list[dict[str, Any]] = []
    if diversity["selection_ready_count"] < MIN_DISTINCT_SCENARIOS:
        failed_requirements.append(
            make_failed_requirement(
                "m2_selection_ready_clip_count_insufficient",
                "Current motion export does not contain enough selection-ready clips for M2.",
                selection_ready_count=diversity["selection_ready_count"],
                required_minimum=MIN_DISTINCT_SCENARIOS,
            )
        )
    if len(diversity["distinct_scenario_ids"]) < MIN_DISTINCT_SCENARIOS:
        failed_requirements.append(
            make_failed_requirement(
                "m2_distinct_scenarios_insufficient",
                "Current motion export does not contain two distinct ready scenarios.",
                distinct_scenario_ids=diversity["distinct_scenario_ids"],
                required_minimum=MIN_DISTINCT_SCENARIOS,
            )
        )

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        latest_report_path if latest_report_path.exists() else None,
        "m2_motion_fixture_diversity_readiness_first_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "toy_yard_motion_view_root": str(resolve_toy_yard_motion_view_root(workspace) or ""),
            "resolved_summary_path": str(summary_path),
            "resolved_registry_path": str(registry_path),
            "fixed_execution_profile": {
                "readiness_focus": "m2_fixture_diversity",
                "minimum_distinct_scenarios": MIN_DISTINCT_SCENARIOS,
                "selection_ready_required": True,
            },
            "summary_profile": {
                "profile": str(summary_payload.get("profile") or ""),
                "sample_id": str(summary_payload.get("sample_id") or ""),
                "counts": dict(summary_payload.get("counts") or {}),
            },
            "diversity_snapshot": diversity,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "summary_path": str(summary_path),
                "registry_path": str(registry_path),
            },
        },
        "motion_fixture_diversity_readiness_m2_report",
        workflow_pack="pmx_pipeline",
        tool_name="AiUE",
        compatibility=make_compatibility_block(
            schema_family="motion_fixture_diversity_readiness_m2_report",
            notes=["internal_gate_runner", "motion_fixture_diversity_readiness", "pre_m2_gate"],
        ),
    )
    report_path = output_root / f"{GATE_ID}_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(f"M2 motion fixture diversity readiness report written to: {report_path}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
