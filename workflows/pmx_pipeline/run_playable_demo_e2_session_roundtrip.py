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


GATE_ID = "playable_demo_e2_session_roundtrip"
DEFAULT_SESSION_MANIFEST_NAME = "playable_demo_e2_session.json"
FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "required_package_count": 2,
    "driver": "t2_native_session_round",
    "request_kinds": ["action_preview", "animation_preview"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE E2 session roundtrip gate.")
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


def invoke_t2_session_round(
    *,
    repo_root: Path,
    workspace_config_path: Path,
    session_manifest_path: Path,
    output_root: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any], Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    dump_path = output_root / "t2_session_round_dump.json"
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
        "-DemoSessionRoundInvoke",
        "-DumpStateJson",
        "-ExitAfterLoad",
    ]
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
                "e2_roundtrip_session_manifest_missing",
                "E2 session roundtrip requires the latest playable demo E2 session manifest.",
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
                "e2_roundtrip_required_package_count_mismatch",
                "E2 session roundtrip requires exactly two ready bundles in the session manifest.",
                required_package_count=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                resolved_package_ids=[str(item.get("package_id") or "") for item in resolved_packages],
            )
        )

    per_package_results: list[dict[str, Any]] = []
    t2_consumption = {"status": "fail"}
    dump_path = output_root / "t2_session_round_dump.json"
    if not failed_requirements:
        completed, dump_payload, dump_path = invoke_t2_session_round(
            repo_root=repo_root,
            workspace_config_path=workspace_config_path,
            session_manifest_path=session_manifest_path,
            output_root=output_root,
        )
        demo_round_control = dict(dump_payload.get("demo_round_control") or {})
        demo_round_state = dict(dump_payload.get("demo_round_state") or {})
        demo_control_state = dict(dump_payload.get("demo_control_state") or {})
        per_package_results = [dict(item) for item in list(demo_round_state.get("package_results") or [])]

        if completed.returncode != 0:
            failed_requirements.append(
                make_failed_requirement(
                    "e2_roundtrip_t2_process_failed",
                    "E2 session roundtrip requires the T2 native session round process to exit cleanly.",
                    returncode=completed.returncode,
                    stderr=completed.stderr[-4000:],
                    dump_path=str(dump_path.resolve()),
                )
            )
        if demo_round_control.get("status") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "e2_roundtrip_control_failed",
                    "E2 session roundtrip requires demo_round_control.status = pass.",
                    round_control=demo_round_control,
                )
            )
        if demo_round_state.get("status") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "e2_roundtrip_round_state_failed",
                    "E2 session roundtrip requires demo_round_state.status = pass.",
                    round_state=demo_round_state,
                )
            )
        round_counts = dict(demo_round_state.get("counts") or {})
        if int(round_counts.get("package_count") or 0) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
            failed_requirements.append(
                make_failed_requirement(
                    "e2_roundtrip_package_count_failed",
                    "E2 session roundtrip requires both packages to be present in the latest round state.",
                    round_counts=round_counts,
                )
            )
        if int(round_counts.get("action_motion_verified") or 0) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
            failed_requirements.append(
                make_failed_requirement(
                    "e2_roundtrip_action_motion_failed",
                    "E2 session roundtrip requires action motion verification for both packages.",
                    round_counts=round_counts,
                )
            )
        if int(round_counts.get("animation_pose_verified") or 0) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
            failed_requirements.append(
                make_failed_requirement(
                    "e2_roundtrip_animation_pose_failed",
                    "E2 session roundtrip requires animation pose verification for both packages.",
                    round_counts=round_counts,
                )
            )
        t2_consumption = {
            "status": "pass" if demo_control_state.get("status") == "pass" and demo_round_state.get("status") == "pass" else "fail",
            "dump_path": str(dump_path.resolve()),
            "round_state_path": str(demo_round_state.get("round_state_path") or ""),
            "control_state_path": str(demo_control_state.get("control_state_path") or ""),
        }

    counts = {
        "resolved_package_count": len(resolved_packages),
        "round_package_count": len(per_package_results),
        "invoke_count": len(per_package_results) * 2,
        "passing_packages": sum(1 for item in per_package_results if str(item.get("status") or "") == "pass"),
        "action_motion_verified": sum(
            1
            for item in per_package_results
            if bool(dict(dict(item.get("action_invoke") or {}).get("credibility_summary") or {}).get("action_motion_verified"))
        ),
        "animation_pose_verified": sum(
            1
            for item in per_package_results
            if bool(dict(dict(item.get("animation_invoke") or {}).get("credibility_summary") or {}).get("animation_pose_verified"))
        ),
    }
    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        first_pass_reason="first_complete_playable_demo_e2_session_roundtrip_pass",
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
            "t2_consumption": t2_consumption,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "t2_dump_path": str(dump_path.resolve()),
            },
        },
        "aiue_playable_demo_e2_session_roundtrip_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_playable_demo_e2_session_roundtrip_report",
            notes=[
                "internal_e2b_native_session_round",
                "t2_session_round_required",
                "session_level_demo_control",
            ],
        ),
    )
    report_path = output_root / "playable_demo_e2_session_roundtrip_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
