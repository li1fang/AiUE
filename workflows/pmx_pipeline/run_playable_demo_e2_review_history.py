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


GATE_ID = "playable_demo_e2_review_history"
DEFAULT_SESSION_MANIFEST_NAME = "playable_demo_e2_session.json"
DEFAULT_REPLAY_REPORT_NAME = "latest_playable_demo_e2_review_replay_report.json"
FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "required_package_count": 2,
    "driver": "t2_native_review_history",
    "request_kinds": ["action_preview", "animation_preview"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE E2F review-history gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--session-manifest-path")
    parser.add_argument("--replay-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def default_session_manifest_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "demo" / "e2" / "latest" / DEFAULT_SESSION_MANIFEST_NAME


def default_replay_report_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "verification" / DEFAULT_REPLAY_REPORT_NAME


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


def run_t2(
    *,
    repo_root: Path,
    session_manifest_path: Path,
    workspace_config_path: Path,
    package_id: str,
    action_preset_id: str,
    animation_preset_id: str,
    request_kind: str | None,
    replay: bool,
    output_root: Path,
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
        "-PackageId",
        package_id,
        "-ActionPresetId",
        action_preset_id,
        "-AnimationPresetId",
        animation_preset_id,
        "-DumpStateJson",
        "-ExitAfterLoad",
    ]
    if request_kind:
        command += ["-DemoRequestKind", request_kind]
    if replay:
        command += ["-DemoReviewReplay"]
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


def evaluate_history_focus(
    *,
    package_id: str,
    completed: subprocess.CompletedProcess[str],
    dump_payload: dict[str, Any],
    dump_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failed_requirements: list[dict[str, Any]] = []
    history_state = dict(dump_payload.get("demo_review_history_state") or {})
    history_focus = dict(dump_payload.get("demo_review_history_focus") or {})

    if completed.returncode != 0:
        failed_requirements.append(
            make_failed_requirement(
                "e2f_t2_load_failed",
                "E2F review history requires the native workbench to exit cleanly on fresh readback.",
                package_id=package_id,
                returncode=completed.returncode,
                stderr=completed.stderr[-4000:],
                dump_path=str(dump_path.resolve()),
            )
        )
    if str(history_state.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2f_history_state_not_pass",
                "E2F review history requires demo_review_history_state.status = pass.",
                package_id=package_id,
                history_state=history_state,
            )
        )
    if str(history_focus.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2f_history_focus_not_pass",
                "E2F review history requires demo_review_history_focus.status = pass.",
                package_id=package_id,
                history_focus=history_focus,
            )
        )
    if str(history_focus.get("selected_package_id") or "") != package_id:
        failed_requirements.append(
            make_failed_requirement(
                "e2f_history_focus_package_mismatch",
                "E2F review history requires the selected history focus package to match the requested package.",
                package_id=package_id,
                history_focus=history_focus,
            )
        )
    replay_kinds = set(str(item) for item in list(history_focus.get("replay_kinds") or []))
    if not {"action_preview", "animation_preview"}.issubset(replay_kinds):
        failed_requirements.append(
            make_failed_requirement(
                "e2f_history_kinds_incomplete",
                "E2F review history requires both replay kinds in the focused package history.",
                package_id=package_id,
                history_focus=history_focus,
            )
        )
    if int(history_focus.get("event_count") or 0) < 2:
        failed_requirements.append(
            make_failed_requirement(
                "e2f_history_event_count_too_small",
                "E2F review history requires at least two recent events for each focused package.",
                package_id=package_id,
                history_focus=history_focus,
            )
        )

    return (
        {
            "status": "pass" if not failed_requirements else "fail",
            "package_id": package_id,
            "history_focus": history_focus,
            "history_state_path": str(history_state.get("history_state_path") or ""),
            "dump_path": str(dump_path.resolve()),
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
    replay_report_path = Path(args.replay_report_path).expanduser().resolve() if args.replay_report_path else default_replay_report_path(repo_root)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict[str, Any]] = []
    if not replay_report_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "e2f_replay_report_missing",
                "E2F review history requires the latest E2E review-replay report.",
                replay_report_path=str(replay_report_path.resolve()),
            )
        )
    else:
        replay_report = load_json(replay_report_path)
        if str(replay_report.get("status") or "") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "e2f_replay_report_not_pass",
                    "E2F review history requires the latest E2E review-replay report to pass.",
                    replay_report_path=str(replay_report_path.resolve()),
                    replay_report_status=replay_report.get("status"),
                )
            )

    if not session_manifest_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "e2f_session_manifest_missing",
                "E2F review history requires the latest playable demo E2 session manifest.",
                session_manifest_path=str(session_manifest_path.resolve()),
            )
        )
        session_payload = {}
    else:
        session_payload = load_json(session_manifest_path)

    resolved_packages = [dict(item) for item in list(session_payload.get("packages") or [])]
    package_ids = [str(item.get("package_id") or "") for item in resolved_packages]
    if len(package_ids) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
        failed_requirements.append(
            make_failed_requirement(
                "e2f_required_package_count_mismatch",
                "E2F review history requires exactly two ready bundles in the E2 session manifest.",
                required_package_count=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                resolved_package_ids=package_ids,
            )
        )

    per_package_results: list[dict[str, Any]] = []
    dump_paths: list[str] = []
    if not failed_requirements:
        for package_payload in resolved_packages:
            package_id = str(package_payload.get("package_id") or "")
            action_preset_id = selected_preset_id(package_payload, "action_presets")
            animation_preset_id = selected_preset_id(package_payload, "animation_presets")
            if not action_preset_id or not animation_preset_id:
                package_failure = make_failed_requirement(
                    "e2f_package_presets_missing",
                    "E2F review history requires both action and animation presets per package.",
                    package_id=package_id,
                )
                per_package_results.append(
                    {
                        "package_id": package_id,
                        "status": "fail",
                        "history_focus_result": {"status": "fail"},
                        "errors": [package_failure],
                    }
                )
                failed_requirements.append(package_failure)
                continue

            for request_kind in FIXED_EXECUTION_PROFILE["request_kinds"]:
                replay_completed, replay_payload, replay_dump_path = run_t2(
                    repo_root=repo_root,
                    session_manifest_path=session_manifest_path,
                    workspace_config_path=workspace_config_path,
                    package_id=package_id,
                    action_preset_id=action_preset_id,
                    animation_preset_id=animation_preset_id,
                    request_kind=request_kind,
                    replay=True,
                    output_root=output_root / "t2_review_history_dumps",
                    dump_name=f"{package_id}_{request_kind}_history_replay_dump.json",
                )
                dump_paths.append(str(replay_dump_path.resolve()))
                if replay_completed.returncode != 0:
                    failed_requirements.append(
                        make_failed_requirement(
                            "e2f_history_replay_failed",
                            "E2F review history requires the replay warmup operations to exit cleanly.",
                            package_id=package_id,
                            request_kind=request_kind,
                            returncode=replay_completed.returncode,
                            dump_path=str(replay_dump_path.resolve()),
                        )
                    )

            fresh_completed, fresh_payload, fresh_dump_path = run_t2(
                repo_root=repo_root,
                session_manifest_path=session_manifest_path,
                workspace_config_path=workspace_config_path,
                package_id=package_id,
                action_preset_id=action_preset_id,
                animation_preset_id=animation_preset_id,
                request_kind=None,
                replay=False,
                output_root=output_root / "t2_review_history_dumps",
                dump_name=f"{package_id}_history_focus_dump.json",
            )
            dump_paths.append(str(fresh_dump_path.resolve()))
            history_focus_result, history_failures = evaluate_history_focus(
                package_id=package_id,
                completed=fresh_completed,
                dump_payload=fresh_payload,
                dump_path=fresh_dump_path,
            )
            per_package_results.append(
                {
                    "package_id": package_id,
                    "status": "pass" if not history_failures else "fail",
                    "history_focus_result": history_focus_result,
                    "errors": history_failures,
                }
            )
            failed_requirements.extend(history_failures)

    counts = {
        "resolved_package_count": len(package_ids),
        "history_focus_package_count": len(per_package_results),
        "passing_packages": sum(1 for item in per_package_results if str(item.get("status") or "") == "pass"),
        "packages_with_two_kinds": sum(
            1
            for item in per_package_results
            if {"action_preview", "animation_preview"}.issubset(
                set(str(kind) for kind in list(dict(item.get("history_focus_result") or {}).get("history_focus", {}).get("replay_kinds") or []))
            )
        ),
        "packages_with_min_events": sum(
            1
            for item in per_package_results
            if int(dict(item.get("history_focus_result") or {}).get("history_focus", {}).get("event_count") or 0) >= 2
        ),
    }
    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        first_pass_reason="first_complete_playable_demo_e2_review_history_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": str(workspace_config_path),
            "source_session_manifest": str(session_manifest_path.resolve()),
            "source_replay_report": str(replay_report_path.resolve()),
            "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
            "counts": counts,
            "per_package_results": per_package_results,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "t2_dump_paths": dump_paths,
            },
        },
        "aiue_playable_demo_e2_review_history_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_playable_demo_e2_review_history_report",
            notes=[
                "internal_e2f_review_history",
                "t2_review_history_required",
                "compact_history_focus",
            ],
        ),
    )
    report_path = output_root / "playable_demo_e2_review_history_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
