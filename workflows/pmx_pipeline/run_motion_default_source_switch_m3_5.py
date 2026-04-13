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
from run_motion_shadow_packet_trial_m0_5 import PREFERRED_PACKAGE_ID  # noqa: E402
from toy_yard_view import resolve_toy_yard_motion_default_source_context  # noqa: E402


GATE_ID = "motion_default_source_switch_m3_5"
SOURCE_GATE_ID = "motion_default_source_readiness_m3"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply and verify the toy-yard motion default-source switch.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--source-report")
    parser.add_argument("--output-root")
    parser.add_argument("--state-root")
    parser.add_argument("--latest-report-path")
    parser.add_argument("--target-package-id")
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
    raise FileNotFoundError(f"Latest M3 report is missing: {candidate}")


def select_cutover_package_id(candidate_snapshot: dict[str, Any], explicit_package_id: str | None = None) -> str:
    package_ids = [str(item) for item in list(candidate_snapshot.get("package_ids") or []) if str(item)]
    if explicit_package_id:
        return str(explicit_package_id)
    if PREFERRED_PACKAGE_ID in package_ids:
        return PREFERRED_PACKAGE_ID
    package_ids.sort()
    return package_ids[0] if package_ids else ""


def run_m0_5_cutover(workspace_config: Path, output_root: Path, state_root: Path, latest_report_path: Path, target_package_id: str) -> tuple[int, dict[str, Any] | None, list[str]]:
    script_path = REPO_ROOT / "workflows" / "pmx_pipeline" / "run_motion_shadow_packet_trial_m0_5.py"
    command = [
        sys.executable,
        str(script_path),
        "--workspace-config",
        str(workspace_config),
        "--output-root",
        str(output_root),
        "--state-root",
        str(state_root),
        "--latest-report-path",
        str(latest_report_path),
        "--target-package-id",
        str(target_package_id),
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    payload = load_json(latest_report_path) if latest_report_path.exists() else None
    stdio = []
    if completed.stdout.strip():
        stdio.append(completed.stdout.strip())
    if completed.stderr.strip():
        stdio.append(completed.stderr.strip())
    return int(completed.returncode), payload, stdio


def evaluate_cutover_report(
    target_package_id: str,
    report_payload: dict[str, Any] | None,
    returncode: int,
    expected_view_root: str,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    report_payload = report_payload or {}
    consumer_result = dict(report_payload.get("consumer_result") or {})
    communication_signal = dict(consumer_result.get("communication_signal") or {})
    preview_evidence = dict(consumer_result.get("preview_evidence") or {})
    failed_requirements: list[dict[str, Any]] = []

    if returncode != 0:
        failed_requirements.append(
            make_failed_requirement(
                "m3_5_cutover_process_failed",
                f"M3.5 cutover run failed for package {target_package_id}.",
                package_id=target_package_id,
                returncode=returncode,
            )
        )
    if str(report_payload.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "m3_5_cutover_gate_failed",
                f"M3.5 cutover gate did not pass for package {target_package_id}.",
                package_id=target_package_id,
                gate_status=str(report_payload.get("status") or ""),
            )
        )
    if str(consumer_result.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "m3_5_consumer_result_not_pass",
                f"Consumer result did not pass for cutover package {target_package_id}.",
                package_id=target_package_id,
                consumer_result_status=str(consumer_result.get("status") or ""),
            )
        )
    if str(communication_signal.get("owner") or "") != "none":
        failed_requirements.append(
            make_failed_requirement(
                "m3_5_owner_not_none",
                f"Owner routing was not none for cutover package {target_package_id}.",
                package_id=target_package_id,
                owner=str(communication_signal.get("owner") or ""),
            )
        )
    if bool(communication_signal.get("should_contact_toy_yard")):
        failed_requirements.append(
            make_failed_requirement(
                "m3_5_should_contact_toy_yard_true",
                f"Cutover package {target_package_id} still requests toy-yard contact.",
                package_id=target_package_id,
            )
        )
    if not bool(preview_evidence.get("subject_visible")):
        failed_requirements.append(
            make_failed_requirement(
                "m3_5_subject_not_visible",
                f"Subject visibility evidence is false for cutover package {target_package_id}.",
                package_id=target_package_id,
            )
        )
    if not bool(preview_evidence.get("pose_changed")):
        failed_requirements.append(
            make_failed_requirement(
                "m3_5_pose_not_changed",
                f"Pose change evidence is false for cutover package {target_package_id}.",
                package_id=target_package_id,
            )
        )
    if expected_view_root and str(report_payload.get("toy_yard_motion_view_root") or "") != expected_view_root:
        failed_requirements.append(
            make_failed_requirement(
                "m3_5_view_root_drift",
                f"Resolved motion view root drifted during cutover for package {target_package_id}.",
                package_id=target_package_id,
                expected_view_root=expected_view_root,
                actual_view_root=str(report_payload.get("toy_yard_motion_view_root") or ""),
            )
        )

    status = "pass" if not failed_requirements else "fail"
    return (
        status,
        failed_requirements,
        {
            "consumer_result_status": str(consumer_result.get("status") or ""),
            "owner": str(communication_signal.get("owner") or ""),
            "subject_visible": bool(preview_evidence.get("subject_visible")),
            "pose_changed": bool(preview_evidence.get("pose_changed")),
            "before_image_path": str(preview_evidence.get("before_image_path") or ""),
            "after_image_path": str(preview_evidence.get("after_image_path") or ""),
        },
    )


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    state_root = Path(args.state_root).expanduser().resolve() if args.state_root else repo_root / "Saved" / "demo" / "m3_5" / "latest"
    output_root.mkdir(parents=True, exist_ok=True)
    state_root.mkdir(parents=True, exist_ok=True)

    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    source_report_path = resolve_source_report_path(workspace, args.source_report)
    source_report = load_json(source_report_path)
    candidate_snapshot = dict(source_report.get("candidate_snapshot") or {})

    failed_requirements: list[dict[str, Any]] = []
    if str(source_report.get("status") or "") != "pass" or not bool(source_report.get("default_source_candidate")):
        failed_requirements.append(
            make_failed_requirement(
                "m3_5_source_m3_not_ready",
                "M3 source report is not ready for default-source cutover.",
                source_report=str(source_report_path),
                source_status=str(source_report.get("status") or ""),
                default_source_candidate=bool(source_report.get("default_source_candidate")),
            )
        )

    motion_context = resolve_toy_yard_motion_default_source_context(workspace)
    if motion_context is None:
        failed_requirements.append(
            make_failed_requirement(
                "m3_5_motion_default_source_context_missing",
                "Workspace could not resolve a complete toy-yard motion default-source context.",
                workspace_config=str(Path(args.workspace_config).expanduser().resolve()),
            )
        )
        motion_context = {}

    target_package_id = select_cutover_package_id(candidate_snapshot, args.target_package_id)
    if not target_package_id:
        failed_requirements.append(
            make_failed_requirement(
                "m3_5_target_package_missing",
                "No target package could be selected for motion default-source cutover.",
            )
        )
    elif target_package_id not in [str(item) for item in list(candidate_snapshot.get("package_ids") or [])]:
        failed_requirements.append(
            make_failed_requirement(
                "m3_5_target_package_outside_candidate_set",
                "Selected cutover package is not part of the M3 candidate snapshot.",
                target_package_id=target_package_id,
                candidate_package_ids=list(candidate_snapshot.get("package_ids") or []),
            )
        )

    cutover_report_path = output_root / f"{target_package_id}_latest_motion_shadow_packet_trial_m0_5_report.json"
    cutover_payload: dict[str, Any] | None = None
    cutover_status = "fail"
    cutover_summary: dict[str, Any] = {}
    stdio: list[str] = []
    if not failed_requirements:
        returncode, cutover_payload, stdio = run_m0_5_cutover(
            Path(args.workspace_config).expanduser().resolve(),
            output_root / "cutover_run",
            state_root / "cutover_run",
            cutover_report_path,
            target_package_id,
        )
        cutover_status, cutover_failed_requirements, cutover_summary = evaluate_cutover_report(
            target_package_id,
            cutover_payload,
            returncode,
            str(motion_context.get("view_root") or ""),
        )
        failed_requirements.extend(cutover_failed_requirements)

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        latest_report_path if latest_report_path.exists() else None,
        "m3_5_motion_default_source_switch_first_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_report": str(source_report_path),
            "source_gate_id": SOURCE_GATE_ID,
            "fixed_execution_profile": {
                "source_mode": "toy_yard_motion_default_source",
                "default_source_required": True,
                "raw_motion_discovery_allowed": False,
                "toy_yard_sqlite_required": False,
                "cutover_validation_mode": "targeted_m0_5_replay",
            },
            "default_source_applied": status == "pass",
            "selected_package_id": target_package_id,
            "motion_default_source_context": {key: str(value) for key, value in motion_context.items()},
            "cutover_run": {
                "status": cutover_status,
                **cutover_summary,
            },
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "m3_report_path": str(source_report_path),
                "m2_5_report_path": str(source_report.get("source_report") or ""),
                "cutover_report_path": str(cutover_report_path) if cutover_report_path.exists() else "",
            },
            "stdio": stdio,
        },
        "motion_default_source_switch_m3_5_report",
        workflow_pack="pmx_pipeline",
        tool_name="AiUE",
        compatibility=make_compatibility_block(
            schema_family="motion_default_source_switch_m3_5_report",
            notes=["internal_gate_runner", "motion_default_source_switch", "targeted_replay"],
        ),
    )
    report_path = output_root / f"{GATE_ID}_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(f"M3.5 motion default-source switch report written to: {report_path}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
