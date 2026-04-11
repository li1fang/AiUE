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


GATE_ID = "playable_demo_e2_review_replay"
DEFAULT_SESSION_MANIFEST_NAME = "playable_demo_e2_session.json"
DEFAULT_NAVIGATION_REPORT_NAME = "latest_playable_demo_e2_review_navigation_report.json"
FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "required_package_count": 2,
    "driver": "t2_native_review_replay",
    "request_kinds": ["action_preview", "animation_preview"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE E2E review-replay gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--session-manifest-path")
    parser.add_argument("--navigation-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def default_session_manifest_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "demo" / "e2" / "latest" / DEFAULT_SESSION_MANIFEST_NAME


def default_navigation_report_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "verification" / DEFAULT_NAVIGATION_REPORT_NAME


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


def evaluate_replay(
    *,
    package_id: str,
    request_kind: str,
    completed: subprocess.CompletedProcess[str],
    dump_payload: dict[str, Any],
    dump_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failed_requirements: list[dict[str, Any]] = []
    replay_control = dict(dump_payload.get("demo_review_replay_control") or {})
    replay_state = dict(dump_payload.get("demo_review_replay_state") or {})
    package_replays = dict((replay_state.get("last_replays_by_package") or {}).get(package_id) or {})
    replay_run = dict(package_replays.get(request_kind) or {})
    credibility_summary = dict(replay_run.get("credibility_summary") or {})
    required_flag = "action_motion_verified" if request_kind == "action_preview" else "animation_pose_verified"

    if completed.returncode != 0:
        failed_requirements.append(
            make_failed_requirement(
                "e2e_t2_replay_process_failed",
                "E2E review replay requires the T2 native review replay process to exit cleanly.",
                package_id=package_id,
                request_kind=request_kind,
                returncode=completed.returncode,
                stderr=completed.stderr[-4000:],
                dump_path=str(dump_path.resolve()),
            )
        )
    if str(replay_control.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2e_replay_control_failed",
                "E2E review replay requires demo_review_replay_control.status = pass.",
                package_id=package_id,
                request_kind=request_kind,
                replay_control=replay_control,
            )
        )
    if str(replay_state.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2e_replay_state_failed",
                "E2E review replay requires demo_review_replay_state.status = pass.",
                package_id=package_id,
                request_kind=request_kind,
                replay_state=replay_state,
            )
        )
    if str(replay_run.get("result_status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2e_replay_result_not_pass",
                "E2E review replay requires the replayed result to pass.",
                package_id=package_id,
                request_kind=request_kind,
                replay_run=replay_run,
            )
        )
    if not bool(credibility_summary.get(required_flag)):
        failed_requirements.append(
            make_failed_requirement(
                "e2e_replay_credibility_not_verified",
                "E2E review replay requires the replayed result to satisfy its credibility evidence rule.",
                package_id=package_id,
                request_kind=request_kind,
                credibility_summary=credibility_summary,
            )
        )

    return (
        {
            "status": "pass" if not failed_requirements else "fail",
            "request_kind": request_kind,
            "replay_control": replay_control,
            "replay_run": replay_run,
            "dump_path": str(dump_path.resolve()),
        },
        failed_requirements,
    )


def evaluate_fresh_readback(
    *,
    package_id: str,
    completed: subprocess.CompletedProcess[str],
    dump_payload: dict[str, Any],
    dump_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failed_requirements: list[dict[str, Any]] = []
    review_focus = dict(dump_payload.get("demo_review_focus") or {})
    replay_state = dict(dump_payload.get("demo_review_replay_state") or {})
    package_replays = dict((replay_state.get("last_replays_by_package") or {}).get(package_id) or {})

    if completed.returncode != 0:
        failed_requirements.append(
            make_failed_requirement(
                "e2e_fresh_readback_failed",
                "E2E review replay requires a fresh T2 readback per package after replay.",
                package_id=package_id,
                returncode=completed.returncode,
                stderr=completed.stderr[-4000:],
                dump_path=str(dump_path.resolve()),
            )
        )
    if str(review_focus.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2e_fresh_focus_not_pass",
                "E2E review replay requires demo_review_focus.status = pass on fresh readback.",
                package_id=package_id,
                review_focus=review_focus,
            )
        )
    if str(review_focus.get("selected_package_id") or "") != package_id:
        failed_requirements.append(
            make_failed_requirement(
                "e2e_fresh_focus_package_mismatch",
                "E2E review replay requires fresh readback focus to match the requested package.",
                package_id=package_id,
                review_focus=review_focus,
            )
        )
    if not {"action_preview", "animation_preview"}.issubset(set(package_replays)):
        failed_requirements.append(
            make_failed_requirement(
                "e2e_fresh_replay_kinds_incomplete",
                "E2E review replay requires both replay kinds to remain present on fresh readback.",
                package_id=package_id,
                replay_state=replay_state,
            )
        )

    return (
        {
            "status": "pass" if not failed_requirements else "fail",
            "review_focus": review_focus,
            "replay_state_path": str(replay_state.get("replay_state_path") or ""),
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
    navigation_report_path = Path(args.navigation_report_path).expanduser().resolve() if args.navigation_report_path else default_navigation_report_path(repo_root)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict[str, Any]] = []
    if not navigation_report_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "e2e_navigation_report_missing",
                "E2E review replay requires the latest E2D review-navigation report.",
                navigation_report_path=str(navigation_report_path.resolve()),
            )
        )
    else:
        navigation_report = load_json(navigation_report_path)
        if str(navigation_report.get("status") or "") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "e2e_navigation_report_not_pass",
                    "E2E review replay requires the latest E2D review-navigation report to pass.",
                    navigation_report_path=str(navigation_report_path.resolve()),
                    navigation_report_status=navigation_report.get("status"),
                )
            )

    if not session_manifest_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "e2e_session_manifest_missing",
                "E2E review replay requires the latest playable demo E2 session manifest.",
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
                "e2e_required_package_count_mismatch",
                "E2E review replay requires exactly two ready bundles in the E2 session manifest.",
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
            package_errors: list[dict[str, Any]] = []
            if not action_preset_id or not animation_preset_id:
                package_errors.append(
                    make_failed_requirement(
                        "e2e_package_presets_missing",
                        "E2E review replay requires both action and animation presets per package.",
                        package_id=package_id,
                    )
                )
                per_package_results.append(
                    {
                        "package_id": package_id,
                        "status": "fail",
                        "action_replay": {"status": "fail"},
                        "animation_replay": {"status": "fail"},
                        "fresh_readback": {"status": "fail"},
                        "errors": package_errors,
                    }
                )
                failed_requirements.extend(package_errors)
                continue

            action_completed, action_payload, action_dump_path = run_t2(
                repo_root=repo_root,
                session_manifest_path=session_manifest_path,
                workspace_config_path=workspace_config_path,
                package_id=package_id,
                action_preset_id=action_preset_id,
                animation_preset_id=animation_preset_id,
                request_kind="action_preview",
                replay=True,
                output_root=output_root / "t2_review_replay_dumps",
                dump_name=f"{package_id}_action_replay_dump.json",
            )
            dump_paths.append(str(action_dump_path.resolve()))
            action_replay, action_failures = evaluate_replay(
                package_id=package_id,
                request_kind="action_preview",
                completed=action_completed,
                dump_payload=action_payload,
                dump_path=action_dump_path,
            )
            package_errors.extend(action_failures)

            animation_completed, animation_payload, animation_dump_path = run_t2(
                repo_root=repo_root,
                session_manifest_path=session_manifest_path,
                workspace_config_path=workspace_config_path,
                package_id=package_id,
                action_preset_id=action_preset_id,
                animation_preset_id=animation_preset_id,
                request_kind="animation_preview",
                replay=True,
                output_root=output_root / "t2_review_replay_dumps",
                dump_name=f"{package_id}_animation_replay_dump.json",
            )
            dump_paths.append(str(animation_dump_path.resolve()))
            animation_replay, animation_failures = evaluate_replay(
                package_id=package_id,
                request_kind="animation_preview",
                completed=animation_completed,
                dump_payload=animation_payload,
                dump_path=animation_dump_path,
            )
            package_errors.extend(animation_failures)

            fresh_completed, fresh_payload, fresh_dump_path = run_t2(
                repo_root=repo_root,
                session_manifest_path=session_manifest_path,
                workspace_config_path=workspace_config_path,
                package_id=package_id,
                action_preset_id=action_preset_id,
                animation_preset_id=animation_preset_id,
                request_kind=None,
                replay=False,
                output_root=output_root / "t2_review_replay_dumps",
                dump_name=f"{package_id}_fresh_readback_dump.json",
            )
            dump_paths.append(str(fresh_dump_path.resolve()))
            fresh_readback, fresh_failures = evaluate_fresh_readback(
                package_id=package_id,
                completed=fresh_completed,
                dump_payload=fresh_payload,
                dump_path=fresh_dump_path,
            )
            package_errors.extend(fresh_failures)

            per_package_results.append(
                {
                    "package_id": package_id,
                    "selected_action_preset_id": action_preset_id,
                    "selected_animation_preset_id": animation_preset_id,
                    "status": "pass" if not package_errors else "fail",
                    "action_replay": action_replay,
                    "animation_replay": animation_replay,
                    "fresh_readback": fresh_readback,
                    "errors": package_errors,
                }
            )
            failed_requirements.extend(package_errors)

    counts = {
        "resolved_package_count": len(package_ids),
        "replayed_package_count": len(per_package_results),
        "replay_invoke_count": len(per_package_results) * 2,
        "passing_packages": sum(1 for item in per_package_results if str(item.get("status") or "") == "pass"),
        "action_replay_verified": sum(1 for item in per_package_results if str(dict(item.get("action_replay") or {}).get("status") or "") == "pass"),
        "animation_replay_verified": sum(1 for item in per_package_results if str(dict(item.get("animation_replay") or {}).get("status") or "") == "pass"),
        "fresh_readback_passed": sum(1 for item in per_package_results if str(dict(item.get("fresh_readback") or {}).get("status") or "") == "pass"),
    }
    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        first_pass_reason="first_complete_playable_demo_e2_review_replay_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": str(workspace_config_path),
            "source_session_manifest": str(session_manifest_path.resolve()),
            "source_navigation_report": str(navigation_report_path.resolve()),
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
        "aiue_playable_demo_e2_review_replay_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_playable_demo_e2_review_replay_report",
            notes=[
                "internal_e2e_review_replay",
                "t2_review_replay_required",
                "fresh_readback_required",
            ],
        ),
    )
    report_path = output_root / "playable_demo_e2_review_replay_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
