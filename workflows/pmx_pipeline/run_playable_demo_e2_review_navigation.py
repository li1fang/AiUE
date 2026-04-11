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


GATE_ID = "playable_demo_e2_review_navigation"
DEFAULT_SESSION_MANIFEST_NAME = "playable_demo_e2_session.json"
DEFAULT_REVIEW_REPORT_NAME = "latest_playable_demo_e2_curated_review_report.json"
FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "required_package_count": 2,
    "driver": "t2_native_review_navigation",
    "focus_source": "demo_review_focus",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE E2D review-navigation gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--session-manifest-path")
    parser.add_argument("--review-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def default_session_manifest_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "demo" / "e2" / "latest" / DEFAULT_SESSION_MANIFEST_NAME


def default_review_report_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "verification" / DEFAULT_REVIEW_REPORT_NAME


def parse_json_from_stdout(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"t2_dump_payload_missing:{stdout.strip()}")
    return json.loads(stdout[start : end + 1])


def dump_t2_focus(
    *,
    repo_root: Path,
    session_manifest_path: Path,
    package_id: str,
    output_root: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any], Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    dump_path = output_root / f"{package_id}_review_navigation_dump.json"
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
        timeout=900,
        env=env,
    )
    payload = parse_json_from_stdout(completed.stdout)
    write_json(dump_path, payload)
    return completed, payload, dump_path


def path_exists(path_value: str) -> bool:
    return bool(path_value) and Path(path_value).expanduser().exists()


def evaluate_package_focus(
    *,
    package_id: str,
    completed: subprocess.CompletedProcess[str],
    dump_payload: dict[str, Any],
    dump_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failed_requirements: list[dict[str, Any]] = []
    review_state = dict(dump_payload.get("demo_review_state") or {})
    review_focus = dict(dump_payload.get("demo_review_focus") or {})

    if completed.returncode != 0:
        failed_requirements.append(
            make_failed_requirement(
                "e2d_t2_load_failed",
                "E2D review navigation requires the native workbench to exit cleanly for every focused package load.",
                package_id=package_id,
                returncode=completed.returncode,
                stderr=completed.stderr[-4000:],
                dump_path=str(dump_path.resolve()),
            )
        )
    if str(review_state.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2d_review_state_not_pass",
                "E2D review navigation requires demo_review_state.status = pass.",
                package_id=package_id,
                review_state=review_state,
            )
        )
    if str(review_focus.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2d_review_focus_not_pass",
                "E2D review navigation requires demo_review_focus.status = pass.",
                package_id=package_id,
                review_focus=review_focus,
            )
        )
    if str(review_focus.get("selected_package_id") or "") != package_id:
        failed_requirements.append(
            make_failed_requirement(
                "e2d_review_focus_package_mismatch",
                "E2D review navigation requires the focused review package to match the requested package id.",
                package_id=package_id,
                review_focus=review_focus,
            )
        )
    if str(review_focus.get("package_review_status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2d_package_review_failed",
                "E2D review navigation requires the focused package review to pass.",
                package_id=package_id,
                review_focus=review_focus,
            )
        )
    if str(review_focus.get("action_review_status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2d_action_review_failed",
                "E2D review navigation requires the focused action review to pass.",
                package_id=package_id,
                review_focus=review_focus,
            )
        )
    if str(review_focus.get("animation_review_status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2d_animation_review_failed",
                "E2D review navigation requires the focused animation review to pass.",
                package_id=package_id,
                review_focus=review_focus,
            )
        )

    artifact_fields = [
        "hero_before_image_path",
        "hero_after_image_path",
        "action_primary_before_image_path",
        "action_primary_after_image_path",
        "animation_primary_before_image_path",
        "animation_primary_after_image_path",
    ]
    missing_artifacts = [field for field in artifact_fields if not path_exists(str(review_focus.get(field) or ""))]
    if missing_artifacts:
        failed_requirements.append(
            make_failed_requirement(
                "e2d_focus_artifacts_missing",
                "E2D review navigation requires the focused review summary to expose reachable hero, action, and animation artifacts.",
                package_id=package_id,
                missing_artifact_fields=missing_artifacts,
                review_focus=review_focus,
            )
        )

    return (
        {
            "package_id": package_id,
            "status": "pass" if not failed_requirements else "fail",
            "review_focus": review_focus,
            "review_state_status": str(review_state.get("status") or ""),
            "dump_path": str(dump_path.resolve()),
            "errors": failed_requirements,
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
    review_report_path = Path(args.review_report_path).expanduser().resolve() if args.review_report_path else default_review_report_path(repo_root)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict[str, Any]] = []
    if not review_report_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "e2d_curated_review_report_missing",
                "E2D review navigation requires the latest E2C curated review report.",
                review_report_path=str(review_report_path.resolve()),
            )
        )
        review_report = {}
    else:
        review_report = load_json(review_report_path)
        if str(review_report.get("status") or "") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "e2d_curated_review_report_not_pass",
                    "E2D review navigation requires the latest E2C curated review report to pass.",
                    review_report_path=str(review_report_path.resolve()),
                    review_report_status=review_report.get("status"),
                )
            )

    if not session_manifest_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "e2d_session_manifest_missing",
                "E2D review navigation requires the latest playable demo E2 session manifest.",
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
                "e2d_required_package_count_mismatch",
                "E2D review navigation requires exactly two ready bundles in the E2 session manifest.",
                required_package_count=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                resolved_package_ids=package_ids,
            )
        )

    per_package_results: list[dict[str, Any]] = []
    dump_paths: list[str] = []
    if not failed_requirements:
        for package_id in package_ids:
            completed, dump_payload, dump_path = dump_t2_focus(
                repo_root=repo_root,
                session_manifest_path=session_manifest_path,
                package_id=package_id,
                output_root=output_root / "t2_review_navigation_dumps",
            )
            dump_paths.append(str(dump_path.resolve()))
            package_result, package_failures = evaluate_package_focus(
                package_id=package_id,
                completed=completed,
                dump_payload=dump_payload,
                dump_path=dump_path,
            )
            per_package_results.append(package_result)
            failed_requirements.extend(package_failures)

    counts = {
        "resolved_package_count": len(package_ids),
        "focused_package_count": len(per_package_results),
        "passing_packages": sum(1 for item in per_package_results if str(item.get("status") or "") == "pass"),
        "action_review_passed": sum(1 for item in per_package_results if str(dict(item.get("review_focus") or {}).get("action_review_status") or "") == "pass"),
        "animation_review_passed": sum(1 for item in per_package_results if str(dict(item.get("review_focus") or {}).get("animation_review_status") or "") == "pass"),
    }
    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        first_pass_reason="first_complete_playable_demo_e2_review_navigation_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_session_manifest": str(session_manifest_path.resolve()),
            "source_review_report": str(review_report_path.resolve()),
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
        "aiue_playable_demo_e2_review_navigation_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_playable_demo_e2_review_navigation_report",
            notes=[
                "internal_e2d_review_navigation",
                "t2_focus_state_required",
                "native_review_navigation",
            ],
        ),
    )
    report_path = output_root / "playable_demo_e2_review_navigation_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
