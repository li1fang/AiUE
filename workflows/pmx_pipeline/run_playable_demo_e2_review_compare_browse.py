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


GATE_ID = "playable_demo_e2_review_compare_browse"
DEFAULT_SESSION_MANIFEST_NAME = "playable_demo_e2_session.json"
DEFAULT_COMPARE_REPORT_NAME = "latest_playable_demo_e2_review_compare_report.json"
FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "required_package_count": 2,
    "required_pair_indices": [0, 1],
    "driver": "t2_native_review_compare_browse",
    "focus_kind": "bounded_compare_browse",
    "required_artifact_roles": ["primary_after"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE E2H bounded review-compare browse gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--session-manifest-path")
    parser.add_argument("--compare-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def default_session_manifest_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "demo" / "e2" / "latest" / DEFAULT_SESSION_MANIFEST_NAME


def default_compare_report_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "verification" / DEFAULT_COMPARE_REPORT_NAME


def parse_json_from_stdout(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"t2_dump_payload_missing:{stdout.strip()}")
    return json.loads(stdout[start : end + 1])


def selected_preset_id(package_payload: dict[str, Any], preset_key: str) -> str:
    presets = [dict(item) for item in list(package_payload.get(preset_key) or [])]
    if not presets:
        return ""
    return str(presets[0].get("preset_id") or "")


def run_t2_focus(
    *,
    repo_root: Path,
    session_manifest_path: Path,
    package_id: str,
    action_preset_id: str,
    animation_preset_id: str,
    review_compare_index: int,
    output_root: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any], Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    dump_path = output_root / f"{package_id}_pair_{review_compare_index}_dump.json"
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
        "-ReviewCompareIndex",
        str(review_compare_index),
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


def _validate_image_path(
    *,
    package_id: str,
    requested_index: int,
    event_name: str,
    image_role: str,
    image_path: str,
) -> dict[str, Any] | None:
    if image_path and Path(image_path).exists():
        return None
    return make_failed_requirement(
        "e2h_compare_artifact_missing",
        "E2H browse requires the selected compare pair to keep the compared after-image artifacts on disk.",
        package_id=package_id,
        requested_index=requested_index,
        event_name=event_name,
        image_role=image_role,
        image_path=image_path,
    )


def evaluate_focus(
    *,
    package_id: str,
    requested_index: int,
    completed: subprocess.CompletedProcess[str],
    dump_payload: dict[str, Any],
    dump_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failed_requirements: list[dict[str, Any]] = []
    compare_state = dict(dump_payload.get("demo_review_compare_state") or {})
    compare_focus = dict(dump_payload.get("demo_review_compare_focus") or {})
    selected_pair = dict(compare_focus.get("selected_compare_pair") or {})
    action_event = dict(selected_pair.get("action_event") or {})
    animation_event = dict(selected_pair.get("animation_event") or {})

    if completed.returncode != 0:
        failed_requirements.append(
            make_failed_requirement(
                "e2h_t2_load_failed",
                "E2H browse requires the native workbench to exit cleanly for every bounded compare focus load.",
                package_id=package_id,
                requested_index=requested_index,
                returncode=completed.returncode,
                stderr=completed.stderr[-4000:],
                dump_path=str(dump_path.resolve()),
            )
        )
    if str(compare_state.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2h_compare_state_not_pass",
                "E2H browse requires demo_review_compare_state.status = pass.",
                package_id=package_id,
                requested_index=requested_index,
                compare_state=compare_state,
            )
        )
    if str(compare_focus.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2h_compare_focus_not_pass",
                "E2H browse requires demo_review_compare_focus.status = pass for the selected pair index.",
                package_id=package_id,
                requested_index=requested_index,
                compare_focus=compare_focus,
            )
        )
    if str(compare_focus.get("selected_package_id") or "") != package_id:
        failed_requirements.append(
            make_failed_requirement(
                "e2h_compare_focus_package_mismatch",
                "E2H browse requires the focused compare package to match the requested package id.",
                package_id=package_id,
                requested_index=requested_index,
                compare_focus=compare_focus,
            )
        )
    if int(compare_focus.get("selected_pair_index") or 0) != requested_index:
        failed_requirements.append(
            make_failed_requirement(
                "e2h_compare_pair_index_mismatch",
                "E2H browse requires the focused compare pair index to match the requested bounded browse index.",
                package_id=package_id,
                requested_index=requested_index,
                compare_focus=compare_focus,
            )
        )
    if int(compare_focus.get("available_pair_count") or 0) < 2:
        failed_requirements.append(
            make_failed_requirement(
                "e2h_compare_pair_count_insufficient",
                "E2H browse requires each package to expose at least two compare pairs for bounded browsing.",
                package_id=package_id,
                requested_index=requested_index,
                available_pair_count=compare_focus.get("available_pair_count"),
                compare_focus=compare_focus,
            )
        )
    selected_pair_index = selected_pair.get("pair_index")
    if int(selected_pair_index if selected_pair_index is not None else -1) != requested_index:
        failed_requirements.append(
            make_failed_requirement(
                "e2h_selected_compare_pair_mismatch",
                "E2H browse requires the selected compare pair payload to match the requested browse index.",
                package_id=package_id,
                requested_index=requested_index,
                selected_compare_pair=selected_pair,
            )
        )
    if not bool(compare_focus.get("compare_ready")) or not bool(selected_pair.get("compare_ready")):
        failed_requirements.append(
            make_failed_requirement(
                "e2h_compare_not_ready",
                "E2H browse requires both the focused compare view and the selected pair to be compare_ready = true.",
                package_id=package_id,
                requested_index=requested_index,
                compare_focus=compare_focus,
                selected_compare_pair=selected_pair,
            )
        )
    if str(action_event.get("request_kind") or "") != "action_preview":
        failed_requirements.append(
            make_failed_requirement(
                "e2h_action_event_missing",
                "E2H browse requires the selected compare pair to expose an action_preview event.",
                package_id=package_id,
                requested_index=requested_index,
                action_event=action_event,
            )
        )
    if str(animation_event.get("request_kind") or "") != "animation_preview":
        failed_requirements.append(
            make_failed_requirement(
                "e2h_animation_event_missing",
                "E2H browse requires the selected compare pair to expose an animation_preview event.",
                package_id=package_id,
                requested_index=requested_index,
                animation_event=animation_event,
            )
        )
    if str(action_event.get("result_status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2h_action_event_not_pass",
                "E2H browse requires the selected action replay result_status to pass.",
                package_id=package_id,
                requested_index=requested_index,
                action_event=action_event,
            )
        )
    if str(animation_event.get("result_status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2h_animation_event_not_pass",
                "E2H browse requires the selected animation replay result_status to pass.",
                package_id=package_id,
                requested_index=requested_index,
                animation_event=animation_event,
            )
        )
    for event_name, event_payload in (
        ("action_preview", action_event),
        ("animation_preview", animation_event),
    ):
        key_images = dict(event_payload.get("key_image_paths") or {})
        maybe_failure = _validate_image_path(
            package_id=package_id,
            requested_index=requested_index,
            event_name=event_name,
            image_role="primary_after",
            image_path=str(key_images.get("primary_after") or ""),
        )
        if maybe_failure is not None:
            failed_requirements.append(maybe_failure)

    return (
        {
            "status": "pass" if not failed_requirements else "fail",
            "package_id": package_id,
            "requested_pair_index": requested_index,
            "selected_pair_index": int(compare_focus.get("selected_pair_index") or 0),
            "available_pair_count": int(compare_focus.get("available_pair_count") or 0),
            "compare_ready": bool(compare_focus.get("compare_ready")),
            "selected_compare_pair": selected_pair,
            "dump_path": str(dump_path.resolve()),
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
    compare_report_path = Path(args.compare_report_path).expanduser().resolve() if args.compare_report_path else default_compare_report_path(repo_root)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict[str, Any]] = []
    if not compare_report_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "e2h_compare_report_missing",
                "E2H browse requires the latest E2G compact compare report.",
                compare_report_path=str(compare_report_path.resolve()),
            )
        )
    else:
        compare_report = load_json(compare_report_path)
        if str(compare_report.get("status") or "") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "e2h_compare_report_not_pass",
                    "E2H browse requires the latest E2G compact compare report to pass.",
                    compare_report_path=str(compare_report_path.resolve()),
                    compare_report_status=compare_report.get("status"),
                )
            )

    if not session_manifest_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "e2h_session_manifest_missing",
                "E2H browse requires the latest playable demo E2 session manifest.",
                session_manifest_path=str(session_manifest_path.resolve()),
            )
        )
        session_payload: dict[str, Any] = {}
    else:
        session_payload = load_json(session_manifest_path)

    resolved_packages = [dict(item) for item in list(session_payload.get("packages") or [])]
    package_ids = [str(item.get("package_id") or "") for item in resolved_packages]
    if len(package_ids) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
        failed_requirements.append(
            make_failed_requirement(
                "e2h_required_package_count_mismatch",
                "E2H browse requires exactly two ready bundles in the E2 session manifest.",
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
            focus_results: list[dict[str, Any]] = []
            package_failures: list[dict[str, Any]] = []
            for review_compare_index in list(FIXED_EXECUTION_PROFILE["required_pair_indices"]):
                completed, dump_payload, dump_path = run_t2_focus(
                    repo_root=repo_root,
                    session_manifest_path=session_manifest_path,
                    package_id=package_id,
                    action_preset_id=action_preset_id,
                    animation_preset_id=animation_preset_id,
                    review_compare_index=int(review_compare_index),
                    output_root=output_root / "t2_review_compare_browse_dumps",
                )
                dump_paths.append(str(dump_path.resolve()))
                focus_result, focus_failures = evaluate_focus(
                    package_id=package_id,
                    requested_index=int(review_compare_index),
                    completed=completed,
                    dump_payload=dump_payload,
                    dump_path=dump_path,
                )
                focus_results.append(focus_result)
                package_failures.extend(focus_failures)
                failed_requirements.extend(focus_failures)
            per_package_results.append(
                {
                    "package_id": package_id,
                    "selected_action_preset_id": action_preset_id,
                    "selected_animation_preset_id": animation_preset_id,
                    "status": "pass" if not package_failures else "fail",
                    "browse_focus_results": focus_results,
                    "errors": package_failures,
                }
            )

    counts = {
        "resolved_package_count": len(package_ids),
        "browse_focus_count": sum(len(list(item.get("browse_focus_results") or [])) for item in per_package_results),
        "passing_focus_count": sum(
            1
            for item in per_package_results
            for focus_result in list(item.get("browse_focus_results") or [])
            if str(focus_result.get("status") or "") == "pass"
        ),
        "passing_packages": sum(1 for item in per_package_results if str(item.get("status") or "") == "pass"),
        "packages_with_two_pairs": sum(
            1
            for item in per_package_results
            if all(int(focus_result.get("available_pair_count") or 0) >= 2 for focus_result in list(item.get("browse_focus_results") or []))
        ),
    }
    status = "pass" if not failed_requirements else "fail"
    report_payload = with_report_envelope(
        {
            "gate_id": GATE_ID,
            "status": status,
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_session_manifest": str(session_manifest_path.resolve()),
            "source_report": str(compare_report_path.resolve()),
            "fixed_execution_profile": FIXED_EXECUTION_PROFILE,
            "counts": counts,
            "per_package_results": per_package_results,
            "failed_requirements": failed_requirements,
            "discussion_signal": build_discussion_signal(
                status=status,
                failed_requirements=failed_requirements,
                previous_report=previous_report,
                previous_report_path=previous_report_path,
                first_pass_reason="first_complete_playable_demo_e2_review_compare_browse_pass",
            ),
            "artifacts": {
                "browse_dump_paths": dump_paths,
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
