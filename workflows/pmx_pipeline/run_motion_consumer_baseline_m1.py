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
from run_motion_shadow_packet_trial_m0_5 import (  # noqa: E402
    EXPECTED_SAMPLE_ID,
    FIXED_EXECUTION_PROFILE as M0_5_PROFILE,
    GATE_ID as M0_5_GATE_ID,
    PREFERRED_PACKAGE_ID,
)


GATE_ID = "motion_consumer_baseline_m1"
DEFAULT_ITERATIONS = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE M1 motion consumer baseline rerun gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--output-root")
    parser.add_argument("--state-root")
    parser.add_argument("--latest-report-path")
    parser.add_argument("--target-package-id")
    return parser.parse_args()


def make_iteration_paths(output_root: Path, state_root: Path, iteration_index: int) -> dict[str, Path]:
    label = f"iteration_{iteration_index:02d}"
    return {
        "output_root": output_root / label,
        "state_root": state_root / label,
        "latest_report_path": output_root / f"{label}_latest_{M0_5_GATE_ID}_report.json",
    }


def run_m0_5_iteration(
    workspace_config: Path,
    iteration_paths: dict[str, Path],
    target_package_id: str | None,
) -> tuple[int, dict[str, Any] | None, list[str]]:
    script_path = REPO_ROOT / "workflows" / "pmx_pipeline" / "run_motion_shadow_packet_trial_m0_5.py"
    command = [
        sys.executable,
        str(script_path),
        "--workspace-config",
        str(workspace_config),
        "--output-root",
        str(iteration_paths["output_root"]),
        "--state-root",
        str(iteration_paths["state_root"]),
        "--latest-report-path",
        str(iteration_paths["latest_report_path"]),
    ]
    if target_package_id:
        command.extend(["--target-package-id", target_package_id])
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    report_payload = None
    if iteration_paths["latest_report_path"].exists():
        report_payload = load_json(iteration_paths["latest_report_path"])
    stdio = []
    if completed.stdout.strip():
        stdio.append(completed.stdout.strip())
    if completed.stderr.strip():
        stdio.append(completed.stderr.strip())
    return int(completed.returncode), report_payload, stdio


def evaluate_iteration_report(iteration_index: int, report_payload: dict[str, Any] | None, returncode: int, stdio: list[str]) -> dict[str, Any]:
    report_payload = report_payload or {}
    consumer_result = dict(report_payload.get("consumer_result") or {})
    communication_signal = dict(consumer_result.get("communication_signal") or {})
    preview_evidence = dict(consumer_result.get("preview_evidence") or {})
    iteration_status = "pass"
    errors: list[str] = []
    failed_requirements: list[dict[str, Any]] = []
    if returncode != 0:
        iteration_status = "fail"
        errors.append(f"iteration_process_failed:{returncode}")
        failed_requirements.append(
            make_failed_requirement(
                "m1_iteration_process_failed",
                f"M0.5 iteration {iteration_index} exited with return code {returncode}.",
                iteration_index=iteration_index,
                returncode=returncode,
            )
        )
    if str(report_payload.get("status") or "") != "pass":
        iteration_status = "fail"
        failed_requirements.append(
            make_failed_requirement(
                "m1_iteration_gate_failed",
                f"M0.5 iteration {iteration_index} did not pass.",
                iteration_index=iteration_index,
                gate_status=str(report_payload.get("status") or ""),
            )
        )
    if str(consumer_result.get("status") or "") != "pass":
        iteration_status = "fail"
        failed_requirements.append(
            make_failed_requirement(
                "m1_iteration_consumer_result_failed",
                f"Consumer result failed on iteration {iteration_index}.",
                iteration_index=iteration_index,
                consumer_result_status=str(consumer_result.get("status") or ""),
            )
        )
    if str(communication_signal.get("owner") or "") != "none":
        iteration_status = "fail"
        failed_requirements.append(
            make_failed_requirement(
                "m1_iteration_owner_not_none",
                f"Owner routing was not none on iteration {iteration_index}.",
                iteration_index=iteration_index,
                owner=str(communication_signal.get("owner") or ""),
            )
        )
    if not bool(preview_evidence.get("subject_visible")):
        iteration_status = "fail"
        failed_requirements.append(
            make_failed_requirement(
                "m1_iteration_subject_not_visible",
                f"Subject was not reliably visible on iteration {iteration_index}.",
                iteration_index=iteration_index,
            )
        )
    if not bool(preview_evidence.get("pose_changed")):
        iteration_status = "fail"
        failed_requirements.append(
            make_failed_requirement(
                "m1_iteration_pose_not_changed",
                f"Pose change evidence was missing on iteration {iteration_index}.",
                iteration_index=iteration_index,
            )
        )
    errors.extend(str(item) for item in list(consumer_result.get("errors") or []) if str(item))
    return {
        "iteration_index": iteration_index,
        "status": iteration_status,
        "gate_status": str(report_payload.get("status") or ""),
        "consumer_result_status": str(consumer_result.get("status") or ""),
        "owner": str(communication_signal.get("owner") or ""),
        "subject_visible": bool(preview_evidence.get("subject_visible")),
        "pose_changed": bool(preview_evidence.get("pose_changed")),
        "warnings": [str(item) for item in list(consumer_result.get("warnings") or []) if str(item)],
        "errors": sorted(set(errors)),
        "failed_requirements": failed_requirements,
        "artifacts": {
            "report_path": str(report_payload.get("_report_path") or ""),
            "result_json_path": str(preview_evidence.get("result_json_path") or ""),
            "before_image_path": str(preview_evidence.get("before_image_path") or ""),
            "after_image_path": str(preview_evidence.get("after_image_path") or ""),
        },
        "stdio": stdio,
    }


def summarize_iterations(iteration_results: list[dict[str, Any]], required_iterations: int) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    failed_requirements: list[dict[str, Any]] = []
    pass_count = 0
    subject_visible_count = 0
    pose_changed_count = 0
    owner_none_count = 0
    for result in iteration_results:
        if result["status"] == "pass":
            pass_count += 1
        if result["subject_visible"]:
            subject_visible_count += 1
        if result["pose_changed"]:
            pose_changed_count += 1
        if result["owner"] == "none":
            owner_none_count += 1
        failed_requirements.extend(list(result.get("failed_requirements") or []))
    if len(iteration_results) != required_iterations:
        failed_requirements.append(
            make_failed_requirement(
                "m1_iteration_count_mismatch",
                "M1 baseline did not collect the requested number of iterations.",
                expected_iterations=required_iterations,
                actual_iterations=len(iteration_results),
            )
        )
    status = "pass" if not failed_requirements else "fail"
    counts = {
        "iterations_requested": required_iterations,
        "iterations_completed": len(iteration_results),
        "iterations_passed": pass_count,
        "subject_visible_passes": subject_visible_count,
        "pose_changed_passes": pose_changed_count,
        "owner_none_passes": owner_none_count,
        "iteration_failures": len(iteration_results) - pass_count,
    }
    return status, failed_requirements, counts


def main() -> int:
    args = parse_args()
    if args.iterations <= 0:
        raise SystemExit("--iterations must be >= 1")

    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    state_root = Path(args.state_root).expanduser().resolve() if args.state_root else repo_root / "Saved" / "demo" / "m1" / "latest"
    output_root.mkdir(parents=True, exist_ok=True)
    state_root.mkdir(parents=True, exist_ok=True)

    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None

    iteration_results: list[dict[str, Any]] = []
    for iteration_index in range(1, args.iterations + 1):
        iteration_paths = make_iteration_paths(output_root, state_root, iteration_index)
        iteration_paths["output_root"].mkdir(parents=True, exist_ok=True)
        iteration_paths["state_root"].mkdir(parents=True, exist_ok=True)
        returncode, report_payload, stdio = run_m0_5_iteration(
            Path(args.workspace_config).expanduser().resolve(),
            iteration_paths,
            args.target_package_id,
        )
        if report_payload is not None:
            report_payload["_report_path"] = str(iteration_paths["latest_report_path"])
        iteration_results.append(evaluate_iteration_report(iteration_index, report_payload, returncode, stdio))

    status, failed_requirements, counts = summarize_iterations(iteration_results, args.iterations)
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        latest_report_path if latest_report_path.exists() else None,
        "m1_motion_consumer_baseline_first_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_gate_id": M0_5_GATE_ID,
            "target_package_id": str(args.target_package_id or PREFERRED_PACKAGE_ID),
            "expected_sample_id": EXPECTED_SAMPLE_ID,
            "fixed_execution_profile": {
                "baseline_mode": "rerun_m0_5",
                "iterations": int(args.iterations),
                "acceptance_requirements": [
                    "m0_5_gate_pass_each_iteration",
                    "consumer_result_pass_each_iteration",
                    "owner_none_each_iteration",
                    "subject_visible_each_iteration",
                    "pose_changed_each_iteration",
                ],
                "source_profile": dict(M0_5_PROFILE),
            },
            "counts": counts,
            "iteration_results": iteration_results,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "iteration_report_paths": [item["artifacts"]["report_path"] for item in iteration_results if item["artifacts"]["report_path"]],
                "latest_m0_5_report_paths": [
                    str(make_iteration_paths(output_root, state_root, item["iteration_index"])["latest_report_path"])
                    for item in iteration_results
                ],
            },
        },
        "motion_consumer_baseline_m1_report",
        workflow_pack="pmx_pipeline",
        tool_name="AiUE",
        compatibility=make_compatibility_block(
            schema_family="motion_consumer_baseline_m1_report",
            notes=["internal_gate_runner", "motion_consumer_baseline", "rerun_m0_5"],
        ),
    )
    report_path = output_root / f"{GATE_ID}_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(f"M1 motion consumer baseline report written to: {report_path}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
