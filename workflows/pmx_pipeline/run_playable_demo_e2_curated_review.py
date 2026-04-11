from __future__ import annotations

import argparse
import json
import os
import subprocess
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
from aiue_core.schema_utils import load_json, load_workspace_config, write_json  # noqa: E402


GATE_ID = "playable_demo_e2_curated_review"
DEFAULT_SESSION_MANIFEST_NAME = "playable_demo_e2_session.json"
FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "required_package_count": 2,
    "driver": "t2_native_curated_review",
    "request_kinds": ["action_preview", "animation_preview"],
    "review_artifact_name": "playable_demo_e2_review_state.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE E2C curated review gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--session-manifest-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def default_session_manifest_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "demo" / "e2" / "latest" / DEFAULT_SESSION_MANIFEST_NAME


def parse_json_from_stdout(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"t2_dump_payload_missing:{stdout.strip()}")
    return json.loads(stdout[start : end + 1])


def run_t2(
    *,
    repo_root: Path,
    workspace_config_path: Path,
    session_manifest_path: Path,
    output_root: Path,
    invoke_round: bool,
    dump_name: str,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any], Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    dump_path = output_root / dump_name
    script_path = repo_root / "tools" / "run_t2_workbench.ps1"
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-Latest",
        "-SessionManifest",
        str(session_manifest_path),
        "-WorkspaceConfig",
        str(workspace_config_path),
        "-DumpStateJson",
        "-ExitAfterLoad",
    ]
    if invoke_round:
        command.append("-DemoSessionRoundInvoke")
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QT_API"] = "pyside6"
    completed = subprocess.run(
        command,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=2400,
        env=env,
    )
    payload = parse_json_from_stdout(completed.stdout)
    write_json(dump_path, payload)
    return completed, payload, dump_path


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    workspace_config_path = Path(args.workspace_config).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    session_manifest_path = Path(args.session_manifest_path).expanduser().resolve() if args.session_manifest_path else default_session_manifest_path(repo_root)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict[str, Any]] = []
    if not session_manifest_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "e2c_session_manifest_missing",
                "E2C curated review requires the latest playable demo E2 session manifest.",
                session_manifest_path=str(session_manifest_path.resolve()),
            )
        )
        session_payload = {}
    else:
        session_payload = load_json(session_manifest_path)

    resolved_packages = [dict(item) for item in list(session_payload.get("packages") or [])]
    if len(resolved_packages) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
        failed_requirements.append(
            make_failed_requirement(
                "e2c_required_package_count_mismatch",
                "E2C curated review requires exactly two ready bundles in the E2 session manifest.",
                required_package_count=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                resolved_package_ids=[str(item.get("package_id") or "") for item in resolved_packages],
            )
        )

    invoke_dump_path = output_root / "t2_invoke_round_dump.json"
    fresh_dump_path = output_root / "t2_fresh_review_dump.json"
    review_state: dict[str, Any] = {"status": "missing", "package_reviews": [], "summary": {}}
    t2_consumption = {"status": "fail"}
    if not failed_requirements:
        invoke_completed, invoke_payload, invoke_dump_path = run_t2(
            repo_root=repo_root,
            workspace_config_path=workspace_config_path,
            session_manifest_path=session_manifest_path,
            output_root=output_root,
            invoke_round=True,
            dump_name="t2_invoke_round_dump.json",
        )
        if invoke_completed.returncode != 0:
            failed_requirements.append(
                make_failed_requirement(
                    "e2c_t2_round_invoke_failed",
                    "E2C curated review requires the native session-round invoke to exit cleanly.",
                    returncode=invoke_completed.returncode,
                    stderr=invoke_completed.stderr[-4000:],
                    dump_path=str(invoke_dump_path.resolve()),
                )
            )
        if dict(invoke_payload.get("demo_round_control") or {}).get("status") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "e2c_t2_round_control_failed",
                    "E2C curated review requires demo_round_control.status = pass during the session round.",
                    round_control=invoke_payload.get("demo_round_control"),
                    dump_path=str(invoke_dump_path.resolve()),
                )
            )

        fresh_completed, fresh_payload, fresh_dump_path = run_t2(
            repo_root=repo_root,
            workspace_config_path=workspace_config_path,
            session_manifest_path=session_manifest_path,
            output_root=output_root,
            invoke_round=False,
            dump_name="t2_fresh_review_dump.json",
        )
        review_state = dict(fresh_payload.get("demo_review_state") or {})
        if fresh_completed.returncode != 0:
            failed_requirements.append(
                make_failed_requirement(
                    "e2c_t2_fresh_load_failed",
                    "E2C curated review requires a fresh native workbench load after the round invoke.",
                    returncode=fresh_completed.returncode,
                    stderr=fresh_completed.stderr[-4000:],
                    dump_path=str(fresh_dump_path.resolve()),
                )
            )
        if str(review_state.get("status") or "") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "e2c_review_state_not_pass",
                    "E2C curated review requires demo_review_state.status = pass on a fresh T2 load.",
                    review_state=review_state,
                )
            )

        summary = dict(review_state.get("summary") or {})
        required_count = int(FIXED_EXECUTION_PROFILE["required_package_count"])
        if int(summary.get("package_count") or 0) != required_count:
            failed_requirements.append(
                make_failed_requirement(
                    "e2c_review_package_count_failed",
                    "E2C curated review requires both ready bundles to appear in the review state.",
                    summary=summary,
                )
            )
        if int(summary.get("passing_packages") or 0) != required_count:
            failed_requirements.append(
                make_failed_requirement(
                    "e2c_review_passing_packages_failed",
                    "E2C curated review requires both packages to pass the curated review summary.",
                    summary=summary,
                )
            )
        if int(summary.get("action_review_passed") or 0) != required_count:
            failed_requirements.append(
                make_failed_requirement(
                    "e2c_action_review_failed",
                    "E2C curated review requires both action reviews to pass.",
                    summary=summary,
                )
            )
        if int(summary.get("animation_review_passed") or 0) != required_count:
            failed_requirements.append(
                make_failed_requirement(
                    "e2c_animation_review_failed",
                    "E2C curated review requires both animation reviews to pass.",
                    summary=summary,
                )
            )

        for package_review in list(review_state.get("package_reviews") or []):
            package_id = str(package_review.get("package_id") or "")
            if str(package_review.get("status") or "") != "pass":
                failed_requirements.append(
                    make_failed_requirement(
                        "e2c_package_review_failed",
                        "E2C curated review requires every package review to pass.",
                        package_id=package_id,
                        package_review=package_review,
                    )
                )

        review_state_path = str(review_state.get("review_state_path") or "")
        if not review_state_path or not Path(review_state_path).exists():
            failed_requirements.append(
                make_failed_requirement(
                    "e2c_review_artifact_missing",
                    "E2C curated review requires a persisted latest review-state artifact.",
                    review_state_path=review_state_path,
                )
            )

        t2_consumption = {
            "status": "pass" if not failed_requirements else "fail",
            "invoke_dump_path": str(invoke_dump_path.resolve()),
            "fresh_dump_path": str(fresh_dump_path.resolve()),
            "review_state_path": str(review_state.get("review_state_path") or ""),
        }

    per_package_results = [dict(item) for item in list(review_state.get("package_reviews") or [])]
    counts = {
        "resolved_package_count": len(resolved_packages),
        "reviewed_package_count": len(per_package_results),
        "passing_packages": sum(1 for item in per_package_results if str(item.get("status") or "") == "pass"),
        "action_review_passed": sum(1 for item in per_package_results if str(dict(item.get("action_review") or {}).get("status") or "") == "pass"),
        "animation_review_passed": sum(1 for item in per_package_results if str(dict(item.get("animation_review") or {}).get("status") or "") == "pass"),
    }
    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        first_pass_reason="first_complete_playable_demo_e2_curated_review_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": str(workspace_config_path),
            "source_session_manifest": str(session_manifest_path.resolve()),
            "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
            "counts": counts,
            "per_package_results": per_package_results,
            "review_state": review_state,
            "t2_consumption": t2_consumption,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "invoke_dump_path": str(invoke_dump_path.resolve()),
                "fresh_dump_path": str(fresh_dump_path.resolve()),
                "review_state_path": str(review_state.get("review_state_path") or ""),
            },
        },
        "aiue_playable_demo_e2_curated_review_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_playable_demo_e2_curated_review_report",
            notes=[
                "internal_e2c_curated_review",
                "t2_review_surface_required",
                "native_review_after_roundtrip",
            ],
        ),
    )
    report_path = output_root / "playable_demo_e2_curated_review_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
