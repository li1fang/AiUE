from __future__ import annotations

import argparse
import subprocess
import sys
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


GATE_ID = "motion_fixture_diversity_m2"
READINESS_GATE_ID = "motion_fixture_diversity_readiness_m2"
SOURCE_GATE_ID = "motion_shadow_packet_trial_m0_5"
ALLOWED_M0_5_BASELINE_FAILURE_IDS = {"m0_5_candidate_scope_mismatch"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE M2 motion fixture diversity gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--source-report")
    parser.add_argument("--output-root")
    parser.add_argument("--state-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def resolve_source_report_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Source report path does not exist: {candidate}")
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    candidate = repo_root / "Saved" / "verification" / f"latest_{READINESS_GATE_ID}_report.json"
    if candidate.exists():
        return candidate.resolve()
    raise FileNotFoundError(f"Latest M2 readiness report is missing: {candidate}")


def _safe_segment(text: str) -> str:
    sanitized = "".join(ch if ch.isalnum() else "_" for ch in str(text or ""))
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
    return sanitized.strip("_") or "package"


def make_package_paths(output_root: Path, state_root: Path, package_id: str) -> dict[str, Path]:
    label = _safe_segment(package_id)
    return {
        "output_root": output_root / label,
        "state_root": state_root / label,
        "latest_report_path": output_root / f"{label}_latest_{SOURCE_GATE_ID}_report.json",
    }


def run_m0_5_for_package(workspace_config: Path, package_paths: dict[str, Path], package_id: str) -> tuple[int, dict[str, Any] | None, list[str]]:
    script_path = REPO_ROOT / "workflows" / "pmx_pipeline" / "run_motion_shadow_packet_trial_m0_5.py"
    command = [
        sys.executable,
        str(script_path),
        "--workspace-config",
        str(workspace_config),
        "--target-package-id",
        package_id,
        "--output-root",
        str(package_paths["output_root"]),
        "--state-root",
        str(package_paths["state_root"]),
        "--latest-report-path",
        str(package_paths["latest_report_path"]),
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    report_payload = None
    if package_paths["latest_report_path"].exists():
        report_payload = load_json(package_paths["latest_report_path"])
        report_payload["_report_path"] = str(package_paths["latest_report_path"])
    stdio = []
    if completed.stdout.strip():
        stdio.append(completed.stdout.strip())
    if completed.stderr.strip():
        stdio.append(completed.stderr.strip())
    return int(completed.returncode), report_payload, stdio


def evaluate_package_result(entry: dict[str, Any], report_payload: dict[str, Any] | None, returncode: int, stdio: list[str]) -> dict[str, Any]:
    report_payload = report_payload or {}
    consumer_result = dict(report_payload.get("consumer_result") or {})
    communication_signal = dict(consumer_result.get("communication_signal") or {})
    preview_evidence = dict(consumer_result.get("preview_evidence") or {})
    source_failed_requirements = list(report_payload.get("failed_requirements") or [])
    source_failed_ids = {
        str(item.get("id") or "")
        for item in source_failed_requirements
        if isinstance(item, dict) and str(item.get("id") or "")
    }
    source_failure_ids_without_scope = {
        item_id for item_id in source_failed_ids if item_id not in ALLOWED_M0_5_BASELINE_FAILURE_IDS
    }
    scope_mismatch_only = bool(source_failed_ids) and not source_failure_ids_without_scope
    package_id = str(entry.get("package_id") or "")
    scenario_id = str(entry.get("scenario_id") or "")
    sample_id = str(entry.get("sample_id") or "")

    failed_requirements: list[dict[str, Any]] = []
    if returncode != 0 and not scope_mismatch_only:
        failed_requirements.append(
            make_failed_requirement(
                "m2_package_process_failed",
                f"M0.5 execution failed for package {package_id}.",
                package_id=package_id,
                returncode=returncode,
            )
        )
    if str(report_payload.get("status") or "") != "pass" and not scope_mismatch_only:
        failed_requirements.append(
            make_failed_requirement(
                "m2_package_gate_failed",
                f"M0.5 gate did not pass for package {package_id}.",
                package_id=package_id,
                gate_status=str(report_payload.get("status") or ""),
            )
        )
    if str(consumer_result.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "m2_package_consumer_result_failed",
                f"Consumer result failed for package {package_id}.",
                package_id=package_id,
                consumer_result_status=str(consumer_result.get("status") or ""),
            )
        )
    if str(communication_signal.get("owner") or "") != "none":
        failed_requirements.append(
            make_failed_requirement(
                "m2_package_owner_not_none",
                f"Owner routing was not none for package {package_id}.",
                package_id=package_id,
                owner=str(communication_signal.get("owner") or ""),
            )
        )
    if not bool(preview_evidence.get("subject_visible")):
        failed_requirements.append(
            make_failed_requirement(
                "m2_package_subject_not_visible",
                f"Subject was not visible for package {package_id}.",
                package_id=package_id,
            )
        )
    if not bool(preview_evidence.get("pose_changed")):
        failed_requirements.append(
            make_failed_requirement(
                "m2_package_pose_not_changed",
                f"Pose change evidence was missing for package {package_id}.",
                package_id=package_id,
            )
        )

    return {
        "package_id": package_id,
        "scenario_id": scenario_id,
        "sample_id": sample_id,
        "status": "pass" if not failed_requirements else "fail",
        "gate_status": str(report_payload.get("status") or ""),
        "consumer_result_status": str(consumer_result.get("status") or ""),
        "owner": str(communication_signal.get("owner") or ""),
        "scope_mismatch_only": scope_mismatch_only,
        "subject_visible": bool(preview_evidence.get("subject_visible")),
        "pose_changed": bool(preview_evidence.get("pose_changed")),
        "warnings": [str(item) for item in list(consumer_result.get("warnings") or []) if str(item)],
        "errors": [str(item) for item in list(consumer_result.get("errors") or []) if str(item)],
        "failed_requirements": failed_requirements,
        "artifacts": {
            "report_path": str(report_payload.get("_report_path") or ""),
            "result_json_path": str(preview_evidence.get("result_json_path") or ""),
            "before_image_path": str(preview_evidence.get("before_image_path") or ""),
            "after_image_path": str(preview_evidence.get("after_image_path") or ""),
        },
        "stdio": stdio,
    }


def summarize_packages(package_results: list[dict[str, Any]], expected_packages: list[str], expected_scenarios: list[str]) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    failed_requirements = [req for item in package_results for req in list(item.get("failed_requirements") or [])]
    actual_packages = [str(item.get("package_id") or "") for item in package_results]
    actual_scenarios = sorted({str(item.get("scenario_id") or "") for item in package_results if str(item.get("scenario_id") or "")})
    if sorted(expected_packages) != sorted(actual_packages):
        failed_requirements.append(
            make_failed_requirement(
                "m2_package_set_mismatch",
                "Resolved package set does not match the readiness profile.",
                expected_packages=expected_packages,
                actual_packages=actual_packages,
            )
        )
    if sorted(expected_scenarios) != actual_scenarios:
        failed_requirements.append(
            make_failed_requirement(
                "m2_scenario_set_mismatch",
                "Resolved scenario set does not match the readiness profile.",
                expected_scenarios=expected_scenarios,
                actual_scenarios=actual_scenarios,
            )
        )
    counts = {
        "package_count": len(package_results),
        "package_passes": sum(1 for item in package_results if item["status"] == "pass"),
        "package_failures": sum(1 for item in package_results if item["status"] != "pass"),
        "subject_visible_passes": sum(1 for item in package_results if item["subject_visible"]),
        "pose_changed_passes": sum(1 for item in package_results if item["pose_changed"]),
        "owner_none_passes": sum(1 for item in package_results if item["owner"] == "none"),
        "distinct_scenarios_executed": len(actual_scenarios),
    }
    status = "pass" if not failed_requirements else "fail"
    return status, failed_requirements, counts


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    state_root = Path(args.state_root).expanduser().resolve() if args.state_root else repo_root / "Saved" / "demo" / "m2" / "latest"
    output_root.mkdir(parents=True, exist_ok=True)
    state_root.mkdir(parents=True, exist_ok=True)

    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    source_report_path = resolve_source_report_path(workspace, args.source_report)
    source_report = load_json(source_report_path)

    if str(source_report.get("status") or "") != "pass":
        raise SystemExit(f"M2 readiness report is not pass: {source_report_path}")

    diversity_snapshot = dict(source_report.get("diversity_snapshot") or {})
    registry_path = Path(str((source_report.get("artifacts") or {}).get("registry_path") or "")).expanduser().resolve()
    registry_payload = load_json(registry_path)
    package_index = dict(registry_payload.get("package_index") or {})
    package_entries = []
    for package_id in list(diversity_snapshot.get("selection_ready_packages") or []):
        entry = dict(package_index.get(str(package_id)) or {})
        clip_entry = next((dict(item) for item in list(registry_payload.get("clips") or []) if str(item.get("package_id") or "") == str(package_id)), {})
        merged = {**entry, **clip_entry}
        package_entries.append(merged)

    workspace_config_path = Path(args.workspace_config).expanduser().resolve()
    package_results: list[dict[str, Any]] = []
    for entry in package_entries:
        package_id = str(entry.get("package_id") or "")
        package_paths = make_package_paths(output_root, state_root, package_id)
        package_paths["output_root"].mkdir(parents=True, exist_ok=True)
        package_paths["state_root"].mkdir(parents=True, exist_ok=True)
        returncode, report_payload, stdio = run_m0_5_for_package(workspace_config_path, package_paths, package_id)
        package_results.append(evaluate_package_result(entry, report_payload, returncode, stdio))

    status, failed_requirements, counts = summarize_packages(
        package_results,
        [str(item.get("package_id") or "") for item in package_entries],
        [str(item) for item in list(diversity_snapshot.get("distinct_scenario_ids") or [])],
    )
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        latest_report_path if latest_report_path.exists() else None,
        "m2_motion_fixture_diversity_first_pass",
    )
    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "workspace_config": str(workspace_config_path),
            "source_report": str(source_report_path),
            "source_gate_id": READINESS_GATE_ID,
            "fixed_execution_profile": {
                "baseline_mode": "per_package_m0_5",
                "required_package_count": len(package_entries),
                "required_distinct_scenarios": len(list(diversity_snapshot.get("distinct_scenario_ids") or [])),
                "acceptance_requirements": [
                    "m0_5_gate_pass_each_package",
                    "consumer_result_pass_each_package",
                    "owner_none_each_package",
                    "subject_visible_each_package",
                    "pose_changed_each_package",
                ],
            },
            "counts": counts,
            "diversity_snapshot": diversity_snapshot,
            "package_results": package_results,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "source_report_path": str(source_report_path),
                "package_report_paths": [item["artifacts"]["report_path"] for item in package_results if item["artifacts"]["report_path"]],
            },
        },
        "motion_fixture_diversity_m2_report",
        workflow_pack="pmx_pipeline",
        tool_name="AiUE",
        compatibility=make_compatibility_block(
            schema_family="motion_fixture_diversity_m2_report",
            notes=["internal_gate_runner", "motion_fixture_diversity", "per_package_m0_5"],
        ),
    )
    report_path = output_root / f"{GATE_ID}_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(f"M2 motion fixture diversity report written to: {report_path}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
