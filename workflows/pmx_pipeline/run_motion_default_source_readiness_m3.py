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


GATE_ID = "motion_default_source_readiness_m3"
SOURCE_GATE_ID = "motion_mixed_profile_result_import_readiness_m2_5"
MIN_PACKAGE_COUNT = 3
MIN_DISTINCT_SCENARIOS = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check whether the current toy-yard motion export is ready to be treated as an AiUE default-source candidate."
    )
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
    raise FileNotFoundError(f"Latest M2.5 report is missing: {candidate}")


def resolve_communication_signal_path(readiness_report: dict[str, Any]) -> Path:
    artifact_path = str(((readiness_report.get("artifacts") or {}).get("communication_signal_path")) or "").strip()
    if artifact_path:
        candidate = Path(artifact_path).expanduser().resolve()
        if candidate.exists():
            return candidate
    view_root = str(readiness_report.get("toy_yard_motion_view_root") or "").strip()
    if view_root:
        candidate = Path(view_root).expanduser().resolve() / "summary" / "communication_signal.json"
        if candidate.exists():
            return candidate
    summary_path = str(readiness_report.get("resolved_summary_path") or "").strip()
    if summary_path:
        candidate = Path(summary_path).expanduser().resolve().parent / "communication_signal.json"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Could not resolve motion communication_signal.json for M3.")


def evaluate_default_source_readiness(
    m2_5_report: dict[str, Any],
    m2_report: dict[str, Any],
    readiness_report: dict[str, Any],
    summary_payload: dict[str, Any],
    registry_payload: dict[str, Any],
    communication_signal: dict[str, Any],
) -> dict[str, Any]:
    failed_requirements: list[dict[str, Any]] = []
    mixed_profile_snapshot = dict(m2_5_report.get("mixed_profile_snapshot") or {})
    package_results = list(m2_5_report.get("package_results") or [])

    if str(m2_5_report.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "m3_source_m2_5_not_pass",
                "M2.5 source report is not pass.",
                source_status=str(m2_5_report.get("status") or ""),
            )
        )
    if str(m2_report.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "m3_source_m2_not_pass",
                "M2 source report is not pass.",
                source_status=str(m2_report.get("status") or ""),
            )
        )
    if str(readiness_report.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "m3_source_readiness_not_pass",
                "M2 readiness source report is not pass.",
                source_status=str(readiness_report.get("status") or ""),
            )
        )

    if len(package_results) < MIN_PACKAGE_COUNT:
        failed_requirements.append(
            make_failed_requirement(
                "m3_package_count_insufficient",
                "Default-source candidate does not expose enough package results.",
                package_count=len(package_results),
                required_minimum=MIN_PACKAGE_COUNT,
            )
        )
    if len(list(mixed_profile_snapshot.get("scenario_ids") or [])) < MIN_DISTINCT_SCENARIOS:
        failed_requirements.append(
            make_failed_requirement(
                "m3_distinct_scenarios_insufficient",
                "Default-source candidate does not expose enough distinct scenarios.",
                scenario_ids=list(mixed_profile_snapshot.get("scenario_ids") or []),
                required_minimum=MIN_DISTINCT_SCENARIOS,
            )
        )
    if str(summary_payload.get("source") or "") != "toy-yard export":
        failed_requirements.append(
            make_failed_requirement(
                "m3_summary_source_invalid",
                "Motion summary source is not toy-yard export.",
                source=str(summary_payload.get("source") or ""),
            )
        )
    if not str(summary_payload.get("export_contract_version") or "").strip():
        failed_requirements.append(
            make_failed_requirement(
                "m3_summary_export_contract_missing",
                "Motion summary is missing export_contract_version.",
            )
        )
    if not str(registry_payload.get("export_contract_version") or "").strip():
        failed_requirements.append(
            make_failed_requirement(
                "m3_registry_export_contract_missing",
                "Motion registry is missing export_contract_version.",
            )
        )
    if str(summary_payload.get("sample_id") or ""):
        failed_requirements.append(
            make_failed_requirement(
                "m3_summary_sample_id_not_empty",
                "Mixed summary should not collapse to a single sample_id.",
                sample_id=str(summary_payload.get("sample_id") or ""),
            )
        )
    if str(summary_payload.get("scenario_id") or ""):
        failed_requirements.append(
            make_failed_requirement(
                "m3_summary_scenario_id_not_empty",
                "Mixed summary should not collapse to a single scenario_id.",
                scenario_id=str(summary_payload.get("scenario_id") or ""),
            )
        )

    if not bool(communication_signal.get("handoff_ready")):
        failed_requirements.append(
            make_failed_requirement(
                "m3_handoff_not_ready",
                "Producer communication signal is not handoff-ready.",
                handoff_ready=bool(communication_signal.get("handoff_ready")),
            )
        )
    if bool(communication_signal.get("needs_counterparty_contact")):
        failed_requirements.append(
            make_failed_requirement(
                "m3_needs_counterparty_contact_true",
                "Producer communication signal still requests counterparty contact.",
            )
        )
    if str(communication_signal.get("problem_owner") or "") != "none":
        failed_requirements.append(
            make_failed_requirement(
                "m3_problem_owner_not_none",
                "Producer communication signal still reports a problem owner.",
                problem_owner=str(communication_signal.get("problem_owner") or ""),
            )
        )

    package_ids = [str(item.get("package_id") or "") for item in package_results if str(item.get("package_id") or "")]
    counts = {
        "package_count": len(package_results),
        "package_passes": sum(1 for item in package_results if str(item.get("status") or "") == "pass"),
        "distinct_samples": len(list(mixed_profile_snapshot.get("sample_ids") or [])),
        "distinct_scenarios": len(list(mixed_profile_snapshot.get("scenario_ids") or [])),
        "subject_visible_packages": sum(1 for item in package_results if bool(item.get("subject_visible"))),
        "pose_changed_packages": sum(1 for item in package_results if bool(item.get("pose_changed"))),
        "owner_none_packages": sum(1 for item in package_results if str(item.get("owner") or "") == "none"),
    }
    default_source_candidate = not failed_requirements and len(package_ids) >= MIN_PACKAGE_COUNT

    return {
        "status": "pass" if not failed_requirements else "fail",
        "counts": counts,
        "package_ids": package_ids,
        "default_source_candidate": default_source_candidate,
        "failed_requirements": failed_requirements,
        "candidate_snapshot": {
            "profile": str(summary_payload.get("profile") or ""),
            "package_ids": package_ids,
            "sample_ids": [str(item) for item in list(mixed_profile_snapshot.get("sample_ids") or []) if str(item)],
            "scenario_ids": [str(item) for item in list(mixed_profile_snapshot.get("scenario_ids") or []) if str(item)],
            "handoff_ready": bool(communication_signal.get("handoff_ready")),
            "problem_owner": str(communication_signal.get("problem_owner") or ""),
            "recommended_next_node": str(communication_signal.get("recommended_next_node") or ""),
        },
    }


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)

    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    source_report_path = resolve_source_report_path(workspace, args.source_report)
    source_report = load_json(source_report_path)

    m2_report = load_json(Path(str(source_report.get("source_report") or "")).expanduser())
    readiness_report = load_json(Path(str(m2_report.get("source_report") or "")).expanduser())
    summary_payload = load_json(Path(str(((readiness_report.get("artifacts") or {}).get("summary_path")) or "")).expanduser())
    registry_payload = load_json(Path(str(((readiness_report.get("artifacts") or {}).get("registry_path")) or "")).expanduser())
    communication_signal_path = resolve_communication_signal_path(readiness_report)
    communication_signal = load_json(communication_signal_path)

    evaluation = evaluate_default_source_readiness(
        source_report,
        m2_report,
        readiness_report,
        summary_payload,
        registry_payload,
        communication_signal,
    )
    discussion_signal = build_discussion_signal(
        evaluation["status"],
        evaluation["failed_requirements"],
        previous_report,
        latest_report_path if latest_report_path.exists() else None,
        "m3_motion_default_source_candidate_first_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": evaluation["status"],
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_report": str(source_report_path),
            "source_gate_id": SOURCE_GATE_ID,
            "fixed_execution_profile": {
                "source_mode": "report_only",
                "candidate_type": "toy_yard_motion_default_source",
                "package_count_required": MIN_PACKAGE_COUNT,
                "distinct_scenarios_required": MIN_DISTINCT_SCENARIOS,
                "acceptance_requirements": [
                    "m2_5_pass",
                    "m2_pass",
                    "readiness_pass",
                    "handoff_ready_true",
                    "problem_owner_none",
                    "mixed_profile_fields_stable",
                ],
            },
            "default_source_candidate": evaluation["default_source_candidate"],
            "candidate_snapshot": evaluation["candidate_snapshot"],
            "counts": evaluation["counts"],
            "failed_requirements": evaluation["failed_requirements"],
            "discussion_signal": discussion_signal,
            "artifacts": {
                "m2_5_report_path": str(source_report_path),
                "m2_report_path": str(source_report.get("source_report") or ""),
                "readiness_report_path": str(m2_report.get("source_report") or ""),
                "summary_path": str(((readiness_report.get("artifacts") or {}).get("summary_path")) or ""),
                "registry_path": str(((readiness_report.get("artifacts") or {}).get("registry_path")) or ""),
                "communication_signal_path": str(communication_signal_path),
            },
        },
        "motion_default_source_readiness_m3_report",
        workflow_pack="pmx_pipeline",
        tool_name="AiUE",
        compatibility=make_compatibility_block(
            schema_family="motion_default_source_readiness_m3_report",
            notes=["internal_gate_runner", "motion_default_source", "candidate_readiness"],
        ),
    )
    report_path = output_root / f"{GATE_ID}_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(f"M3 motion default-source readiness report written to: {report_path}")
    return 0 if evaluation["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
