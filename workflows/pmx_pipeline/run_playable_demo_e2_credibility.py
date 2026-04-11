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


GATE_ID = "playable_demo_e2_credibility"
DEFAULT_SESSION_MANIFEST_NAME = "playable_demo_e2_session.json"
DEFAULT_CONTROL_STATE_NAME = "playable_demo_e2_control_state.json"
FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "required_package_count": 2,
    "request_kinds": ["action_preview", "animation_preview"],
    "action_preset_selection": "first",
    "animation_preset_selection": "first",
    "driver": "t2_native_control_surface",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE E2A native-control credibility gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--session-manifest-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def default_session_manifest_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "demo" / "e2" / "latest" / DEFAULT_SESSION_MANIFEST_NAME


def default_control_state_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "demo" / "e2" / "latest" / DEFAULT_CONTROL_STATE_NAME


def parse_json_from_stdout(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"t2_dump_payload_missing:{stdout.strip()}")
    return json.loads(stdout[start : end + 1])


def selected_preset_id(package_payload: dict[str, Any], preset_key: str) -> str:
    presets = list(package_payload.get(preset_key) or [])
    if not presets:
        return ""
    return str(presets[0].get("preset_id") or "")


def invoke_t2_request(
    *,
    repo_root: Path,
    workspace_config_path: Path,
    session_manifest_path: Path,
    package_id: str,
    action_preset_id: str,
    animation_preset_id: str,
    request_kind: str,
    output_root: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any], Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    dump_path = output_root / f"{package_id}_{request_kind}_t2_dump.json"
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
        "-PackageId",
        package_id,
        "-ActionPresetId",
        action_preset_id,
        "-AnimationPresetId",
        animation_preset_id,
        "-DemoRequestKind",
        request_kind,
        "-DemoRequestInvoke",
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
        timeout=1800,
        env=env,
    )
    payload = parse_json_from_stdout(completed.stdout)
    write_json(dump_path, payload)
    return completed, payload, dump_path


def evaluate_invoke(
    *,
    package_id: str,
    request_kind: str,
    completed: subprocess.CompletedProcess[str],
    dump_payload: dict[str, Any],
    dump_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failed_requirements: list[dict[str, Any]] = []
    demo_request_control = dict(dump_payload.get("demo_request_control") or {})
    demo_control_state = dict(dump_payload.get("demo_control_state") or {})
    package_runs = dict((demo_control_state.get("last_runs_by_package") or {}).get(package_id) or {})
    last_run = dict(package_runs.get(request_kind) or {})
    credibility_summary = dict(last_run.get("credibility_summary") or {})
    request_json_path = str(last_run.get("request_json_path") or demo_request_control.get("request_json_path") or "")
    result_json_path = str(last_run.get("result_json_path") or demo_request_control.get("result_json_path") or "")
    result_status = str(last_run.get("result_status") or demo_request_control.get("result_status") or "")

    if completed.returncode != 0:
        failed_requirements.append(
            make_failed_requirement(
                "e2a_t2_invoke_failed",
                "E2A requires the T2 native control invoke to exit cleanly.",
                package_id=package_id,
                request_kind=request_kind,
                returncode=completed.returncode,
                stderr=completed.stderr[-4000:],
                dump_path=str(dump_path.resolve()),
            )
        )
    if demo_control_state.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2a_t2_control_state_missing",
                "E2A requires T2 to read back a passing latest demo control-state.",
                package_id=package_id,
                request_kind=request_kind,
                control_state_status=demo_control_state.get("status"),
                dump_path=str(dump_path.resolve()),
            )
        )
    if demo_request_control.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2a_demo_request_control_failed",
                "E2A requires the T2 demo request control operation to report pass.",
                package_id=package_id,
                request_kind=request_kind,
                control_status=demo_request_control.get("status"),
                control_errors=list(demo_request_control.get("errors") or []),
            )
        )
    if not request_json_path or not Path(request_json_path).exists():
        failed_requirements.append(
            make_failed_requirement(
                "e2a_request_json_missing",
                "E2A requires each native-controlled invoke to leave behind a request JSON artifact.",
                package_id=package_id,
                request_kind=request_kind,
                request_json_path=request_json_path,
            )
        )
    if not result_json_path or not Path(result_json_path).exists():
        failed_requirements.append(
            make_failed_requirement(
                "e2a_result_json_missing",
                "E2A requires each native-controlled invoke to leave behind a result JSON artifact.",
                package_id=package_id,
                request_kind=request_kind,
                result_json_path=result_json_path,
            )
        )
    if result_status != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2a_result_status_not_pass",
                "E2A requires each invoked preview result to pass.",
                package_id=package_id,
                request_kind=request_kind,
                result_status=result_status,
                result_json_path=result_json_path,
            )
        )

    required_flag = "action_motion_verified" if request_kind == "action_preview" else "animation_pose_verified"
    if not bool(credibility_summary.get(required_flag)):
        failed_requirements.append(
            make_failed_requirement(
                "e2a_credibility_not_verified",
                "E2A requires each invoked preview to satisfy its credibility evidence rule.",
                package_id=package_id,
                request_kind=request_kind,
                required_flag=required_flag,
                credibility_summary=credibility_summary,
            )
        )

    return (
        {
            "status": "pass" if not failed_requirements else "fail",
            "request_kind": request_kind,
            "request_json_path": request_json_path,
            "result_json_path": result_json_path,
            "result_status": result_status,
            "host_key": str(last_run.get("host_key") or demo_request_control.get("host_key") or ""),
            "generated_at_utc": str(last_run.get("generated_at_utc") or ""),
            "key_image_paths": dict(last_run.get("key_image_paths") or {}),
            "credibility_summary": credibility_summary,
            "warning_flags": list(credibility_summary.get("warning_flags") or []),
            "t2_dump_path": str(dump_path.resolve()),
            "control_state_status": str(demo_control_state.get("status") or ""),
        },
        failed_requirements,
    )


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
                "e2a_session_manifest_missing",
                "E2A requires the latest playable demo E2 session manifest.",
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
                "e2a_required_package_count_mismatch",
                "E2A requires exactly two ready bundles from the latest E2 session manifest.",
                required_package_count=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                resolved_package_ids=[str(item.get("package_id") or "") for item in resolved_packages],
            )
        )

    per_package_results: list[dict[str, Any]] = []
    t2_dump_paths: list[str] = []
    for package_payload in resolved_packages:
        package_id = str(package_payload.get("package_id") or "")
        action_preset_id = selected_preset_id(package_payload, "action_presets")
        animation_preset_id = selected_preset_id(package_payload, "animation_presets")
        package_errors: list[dict[str, Any]] = []
        if not action_preset_id:
            package_errors.append(
                make_failed_requirement(
                    "e2a_action_preset_missing",
                    "E2A requires the first action preset for each package.",
                    package_id=package_id,
                )
            )
        if not animation_preset_id:
            package_errors.append(
                make_failed_requirement(
                    "e2a_animation_preset_missing",
                    "E2A requires the first animation preset for each package.",
                    package_id=package_id,
                )
            )
        action_invoke = {"status": "fail"}
        animation_invoke = {"status": "fail"}
        if not package_errors:
            for request_kind in FIXED_EXECUTION_PROFILE["request_kinds"]:
                completed, dump_payload, dump_path = invoke_t2_request(
                    repo_root=repo_root,
                    workspace_config_path=workspace_config_path,
                    session_manifest_path=session_manifest_path,
                    package_id=package_id,
                    action_preset_id=action_preset_id,
                    animation_preset_id=animation_preset_id,
                    request_kind=request_kind,
                    output_root=output_root / "t2_dumps",
                )
                t2_dump_paths.append(str(dump_path.resolve()))
                invoke_result, invoke_failures = evaluate_invoke(
                    package_id=package_id,
                    request_kind=request_kind,
                    completed=completed,
                    dump_payload=dump_payload,
                    dump_path=dump_path,
                )
                if request_kind == "action_preview":
                    action_invoke = invoke_result
                else:
                    animation_invoke = invoke_result
                package_errors.extend(invoke_failures)

        per_package_results.append(
            {
                "package_id": package_id,
                "selected_action_preset_id": action_preset_id,
                "selected_animation_preset_id": animation_preset_id,
                "action_invoke": action_invoke,
                "animation_invoke": animation_invoke,
                "status": "pass" if not package_errors else "fail",
                "errors": package_errors,
            }
        )
        failed_requirements.extend(package_errors)

    control_state_path = default_control_state_path(repo_root)
    t2_consumption_status = "pass" if control_state_path.exists() and not failed_requirements else "fail"
    counts = {
        "resolved_package_count": len(resolved_packages),
        "invoke_count": len(resolved_packages) * len(FIXED_EXECUTION_PROFILE["request_kinds"]),
        "action_invokes_passed": sum(1 for item in per_package_results if dict(item.get("action_invoke") or {}).get("status") == "pass"),
        "animation_invokes_passed": sum(1 for item in per_package_results if dict(item.get("animation_invoke") or {}).get("status") == "pass"),
        "action_motion_verified": sum(
            1
            for item in per_package_results
            if dict(dict(item.get("action_invoke") or {}).get("credibility_summary") or {}).get("action_motion_verified")
        ),
        "animation_pose_verified": sum(
            1
            for item in per_package_results
            if dict(dict(item.get("animation_invoke") or {}).get("credibility_summary") or {}).get("animation_pose_verified")
        ),
    }
    status = "pass" if not failed_requirements and counts["resolved_package_count"] == int(FIXED_EXECUTION_PROFILE["required_package_count"]) else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        first_pass_reason="first_complete_playable_demo_e2_credibility_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "source_session_manifest": str(session_manifest_path.resolve()),
            "workspace_config": str(workspace_config_path),
            "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
            "counts": counts,
            "per_package_results": per_package_results,
            "t2_consumption": {
                "status": t2_consumption_status,
                "control_state_path": str(control_state_path.resolve()),
                "latest_manifest_path": str((repo_root / "Saved" / "tooling" / "t1" / "latest" / "manifest.json").resolve()),
            },
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "t2_dump_paths": t2_dump_paths,
            },
        },
        "aiue_playable_demo_e2_credibility_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_playable_demo_e2_credibility_report",
            notes=[
                "internal_e2a_native_control_loop",
                "t2_native_invoke_required",
                "evidence_first_demo_credibility",
            ],
        ),
    )
    report_path = output_root / "playable_demo_e2_credibility_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
