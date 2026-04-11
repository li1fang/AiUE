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
    repo_root_from_workspace,
    write_report_pair,
)

from aiue_core.report_writer import make_compatibility_block, with_report_envelope  # noqa: E402
from aiue_core.schema_utils import load_json, load_workspace_config, write_json  # noqa: E402
from aiue_t2.demo_review_compare_state import write_demo_review_compare_state  # noqa: E402
from aiue_t2.demo_review_history_state import load_demo_review_history_state  # noqa: E402


GATE_ID = "playable_demo_e2_review_compare"
DEFAULT_SESSION_MANIFEST_NAME = "playable_demo_e2_session.json"
DEFAULT_HISTORY_REPORT_NAME = "latest_playable_demo_e2_review_history_report.json"
FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "required_package_count": 2,
    "driver": "t2_native_review_compare",
    "focus_kind": "compact_compare",
    "request_kinds": ["action_preview", "animation_preview"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE E2G compact review-compare gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--session-manifest-path")
    parser.add_argument("--history-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def default_session_manifest_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "demo" / "e2" / "latest" / DEFAULT_SESSION_MANIFEST_NAME


def default_history_report_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "verification" / DEFAULT_HISTORY_REPORT_NAME


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
    package_id: str,
    action_preset_id: str,
    animation_preset_id: str,
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
        "-PackageId",
        package_id,
        "-ActionPresetId",
        action_preset_id,
        "-AnimationPresetId",
        animation_preset_id,
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


def _validate_key_image_path(
    *,
    package_id: str,
    event_name: str,
    image_role: str,
    image_path: str,
) -> dict[str, Any] | None:
    if image_path and Path(image_path).exists():
        return None
    return make_failed_requirement(
        "e2g_compare_image_missing",
        "E2G review compare requires the compared action and animation events to keep their key images on disk.",
        package_id=package_id,
        event_name=event_name,
        image_role=image_role,
        image_path=image_path,
    )


def evaluate_compare_focus(
    *,
    package_id: str,
    completed: subprocess.CompletedProcess[str],
    dump_payload: dict[str, Any],
    dump_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failed_requirements: list[dict[str, Any]] = []
    compare_state = dict(dump_payload.get("demo_review_compare_state") or {})
    compare_focus = dict(dump_payload.get("demo_review_compare_focus") or {})
    latest_action_event = dict(compare_focus.get("latest_action_event") or {})
    latest_animation_event = dict(compare_focus.get("latest_animation_event") or {})

    if completed.returncode != 0:
        failed_requirements.append(
            make_failed_requirement(
                "e2g_t2_load_failed",
                "E2G review compare requires the native workbench to exit cleanly on focused compare readback.",
                package_id=package_id,
                returncode=completed.returncode,
                stderr=completed.stderr[-4000:],
                dump_path=str(dump_path.resolve()),
            )
        )
    if str(compare_state.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2g_compare_state_not_pass",
                "E2G review compare requires demo_review_compare_state.status = pass.",
                package_id=package_id,
                compare_state=compare_state,
            )
        )
    if str(compare_focus.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2g_compare_focus_not_pass",
                "E2G review compare requires demo_review_compare_focus.status = pass.",
                package_id=package_id,
                compare_focus=compare_focus,
            )
        )
    if str(compare_focus.get("selected_package_id") or "") != package_id:
        failed_requirements.append(
            make_failed_requirement(
                "e2g_compare_focus_package_mismatch",
                "E2G review compare requires the focused compare package to match the requested package.",
                package_id=package_id,
                compare_focus=compare_focus,
            )
        )
    replay_kinds = set(str(item) for item in list(compare_focus.get("replay_kinds") or []))
    if not {"action_preview", "animation_preview"}.issubset(replay_kinds):
        failed_requirements.append(
            make_failed_requirement(
                "e2g_compare_kinds_incomplete",
                "E2G review compare requires both action and animation replay kinds in the focused compare view.",
                package_id=package_id,
                compare_focus=compare_focus,
            )
        )
    if not bool(compare_focus.get("compare_ready")):
        failed_requirements.append(
            make_failed_requirement(
                "e2g_compare_not_ready",
                "E2G review compare requires the focused compare view to be compare_ready = true.",
                package_id=package_id,
                compare_focus=compare_focus,
            )
        )
    if str(latest_action_event.get("request_kind") or "") != "action_preview":
        failed_requirements.append(
            make_failed_requirement(
                "e2g_action_event_missing",
                "E2G review compare requires a latest action_preview event in the compare focus.",
                package_id=package_id,
                latest_action_event=latest_action_event,
            )
        )
    if str(latest_animation_event.get("request_kind") or "") != "animation_preview":
        failed_requirements.append(
            make_failed_requirement(
                "e2g_animation_event_missing",
                "E2G review compare requires a latest animation_preview event in the compare focus.",
                package_id=package_id,
                latest_animation_event=latest_animation_event,
            )
        )
    if str(latest_action_event.get("result_status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2g_action_event_not_pass",
                "E2G review compare requires the focused action replay result_status to pass.",
                package_id=package_id,
                latest_action_event=latest_action_event,
            )
        )
    if str(latest_animation_event.get("result_status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2g_animation_event_not_pass",
                "E2G review compare requires the focused animation replay result_status to pass.",
                package_id=package_id,
                latest_animation_event=latest_animation_event,
            )
        )
    for event_name, event_payload in (
        ("action_preview", latest_action_event),
        ("animation_preview", latest_animation_event),
    ):
        key_images = dict(event_payload.get("key_image_paths") or {})
        for image_role in ("primary_before", "primary_after"):
            maybe_failure = _validate_key_image_path(
                package_id=package_id,
                event_name=event_name,
                image_role=image_role,
                image_path=str(key_images.get(image_role) or ""),
            )
            if maybe_failure is not None:
                failed_requirements.append(maybe_failure)

    return (
        {
            "status": "pass" if not failed_requirements else "fail",
            "package_id": package_id,
            "compare_focus": compare_focus,
            "compare_state_path": str(compare_state.get("compare_state_path") or ""),
            "dump_path": str(dump_path.resolve()),
            "latest_action_event_id": latest_action_event.get("history_event_id"),
            "latest_animation_event_id": latest_animation_event.get("history_event_id"),
        },
        failed_requirements,
    )


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    session_manifest_path = Path(args.session_manifest_path).expanduser().resolve() if args.session_manifest_path else default_session_manifest_path(repo_root)
    history_report_path = Path(args.history_report_path).expanduser().resolve() if args.history_report_path else default_history_report_path(repo_root)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict[str, Any]] = []
    if not history_report_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "e2g_history_report_missing",
                "E2G review compare requires the latest E2F review-history report.",
                history_report_path=str(history_report_path.resolve()),
            )
        )
    else:
        history_report = load_json(history_report_path)
        if str(history_report.get("status") or "") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "e2g_history_report_not_pass",
                    "E2G review compare requires the latest E2F review-history report to pass.",
                    history_report_path=str(history_report_path.resolve()),
                    history_report_status=history_report.get("status"),
                )
            )

    if not session_manifest_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "e2g_session_manifest_missing",
                "E2G review compare requires the latest playable demo E2 session manifest.",
                session_manifest_path=str(session_manifest_path.resolve()),
            )
        )
        session_payload = {}
    else:
        session_payload = load_json(session_manifest_path)

    history_state = load_demo_review_history_state(session_manifest_path)
    if str(history_state.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2g_history_state_not_pass",
                "E2G review compare requires the latest review history state to pass.",
                history_state_path=str(history_state.get("history_state_path") or ""),
                history_state=history_state,
            )
        )
        compare_state = {}
    else:
        compare_state = write_demo_review_compare_state(
            session_manifest_path=session_manifest_path,
            demo_review_history_state=history_state,
        )

    resolved_packages = [dict(item) for item in list(session_payload.get("packages") or [])]
    package_ids = [str(item.get("package_id") or "") for item in resolved_packages]
    if len(package_ids) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
        failed_requirements.append(
            make_failed_requirement(
                "e2g_required_package_count_mismatch",
                "E2G review compare requires exactly two ready bundles in the E2 session manifest.",
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
            completed, dump_payload, dump_path = run_t2(
                repo_root=repo_root,
                session_manifest_path=session_manifest_path,
                package_id=package_id,
                action_preset_id=action_preset_id,
                animation_preset_id=animation_preset_id,
                output_root=output_root / "t2_review_compare_dumps",
                dump_name=f"{package_id}_review_compare_dump.json",
            )
            dump_paths.append(str(dump_path.resolve()))
            package_result, package_failures = evaluate_compare_focus(
                package_id=package_id,
                completed=completed,
                dump_payload=dump_payload,
                dump_path=dump_path,
            )
            per_package_results.append(package_result)
            failed_requirements.extend(package_failures)

    counts = {
        "resolved_package_count": len(package_ids),
        "compare_focus_package_count": len(per_package_results),
        "passing_packages": sum(1 for item in per_package_results if str(item.get("status") or "") == "pass"),
        "packages_with_compare_pair": sum(
            1 for item in per_package_results if bool(dict(item.get("compare_focus") or {}).get("compare_ready"))
        ),
        "compare_state_package_count": int(dict(compare_state.get("counts") or {}).get("package_count") or 0),
    }
    status = "pass" if not failed_requirements else "fail"
    report_payload = with_report_envelope(
        {
            "gate_id": GATE_ID,
            "status": status,
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_session_manifest": str(session_manifest_path.resolve()),
            "source_report": str(history_report_path.resolve()),
            "fixed_execution_profile": FIXED_EXECUTION_PROFILE,
            "counts": counts,
            "compare_state": {
                "status": compare_state.get("status"),
                "compare_state_path": compare_state.get("compare_state_path"),
                "counts": compare_state.get("counts"),
            },
            "per_package_results": per_package_results,
            "failed_requirements": failed_requirements,
            "discussion_signal": build_discussion_signal(
                status=status,
                failed_requirements=failed_requirements,
                previous_report=previous_report,
                previous_report_path=previous_report_path,
                first_pass_reason="first_complete_playable_demo_e2_review_compare_pass",
            ),
            "artifacts": {
                "compare_state_path": str(compare_state.get("compare_state_path") or ""),
                "compare_dump_paths": dump_paths,
            },
        },
        schema_family="aiue_gate_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block("aiue_gate_report"),
    )
    report_path = output_root / f"{GATE_ID}_report.json"
    write_report_pair(report_payload, report_path=report_path, latest_report_path=latest_report_path)
    print(str(report_path))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
