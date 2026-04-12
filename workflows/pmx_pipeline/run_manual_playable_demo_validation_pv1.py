from __future__ import annotations

import argparse
import os
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
    verification_named_report_path,
    write_report_pair,
)

from aiue_core.report_writer import make_compatibility_block, with_report_envelope  # noqa: E402
from aiue_core.schema_utils import load_json, load_workspace_config  # noqa: E402


GATE_ID = "manual_playable_demo_validation_pv1"
DEFAULT_SESSION_MANIFEST_NAME = "playable_demo_e2_session.json"
DEFAULT_E2B_LATEST_NAME = "latest_playable_demo_e2b_credible_showcase_report.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the AiUE PV1 manual playable demo validation signoff report.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--session-manifest-path")
    parser.add_argument("--e2b-report-path")
    parser.add_argument("--operator", default=os.environ.get("USERNAME", "unknown"))
    parser.add_argument("--signoff-status", choices=["pass", "attention"], default="attention")
    parser.add_argument("--notes", default="manual_playable_demo_validation_pending")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def default_session_manifest_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "demo" / "e2" / "latest" / DEFAULT_SESSION_MANIFEST_NAME


def build_checked_packages(session_payload: dict[str, Any]) -> list[dict[str, Any]]:
    checked_packages = []
    for package in list(session_payload.get("packages") or []):
        action_presets = list(package.get("action_presets") or [])
        animation_presets = list(package.get("animation_presets") or [])
        checked_packages.append(
            {
                "package_id": str(package.get("package_id") or ""),
                "sample_id": str(package.get("sample_id") or ""),
                "action_preset_id": str((action_presets[0] or {}).get("preset_id") or "") if action_presets else "",
                "animation_preset_id": str((animation_presets[0] or {}).get("preset_id") or "") if animation_presets else "",
                "host_blueprint_asset": str(package.get("host_blueprint_asset") or ""),
            }
        )
    return checked_packages


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    session_manifest_path = Path(args.session_manifest_path).expanduser().resolve() if args.session_manifest_path else default_session_manifest_path(repo_root)
    e2b_report_path = Path(args.e2b_report_path).expanduser().resolve() if args.e2b_report_path else verification_named_report_path(workspace, REPO_ROOT, DEFAULT_E2B_LATEST_NAME)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict[str, Any]] = []
    if not session_manifest_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "pv1_session_manifest_missing",
                "PV1 requires the latest playable demo session manifest.",
                session_manifest_path=str(session_manifest_path.resolve()),
            )
        )
        session_payload = {}
    else:
        session_payload = load_json(session_manifest_path)

    if not e2b_report_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "pv1_e2b_report_missing",
                "PV1 requires the latest E2B credible showcase report as its signoff source.",
                e2b_report_path=str(e2b_report_path.resolve()),
            )
        )
        e2b_report = {}
    else:
        e2b_report = load_json(e2b_report_path)
    if e2b_report and str(e2b_report.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "pv1_e2b_not_pass",
                "PV1 signoff can only be marked against a passing E2B credible showcase report.",
                e2b_report_path=str(e2b_report_path.resolve()),
                e2b_status=e2b_report.get("status"),
            )
        )

    checked_packages = build_checked_packages(session_payload)
    checked_package_ids = [
        str(item.get("package_id") or "")
        for item in checked_packages
        if str(item.get("package_id") or "")
    ]
    if not checked_packages:
        failed_requirements.append(
            make_failed_requirement(
                "pv1_checked_packages_missing",
                "PV1 requires checked package metadata from the current session manifest.",
                session_manifest_path=str(session_manifest_path.resolve()) if session_manifest_path.exists() else "",
            )
        )

    requested_status = str(args.signoff_status or "attention")
    status = "pass" if requested_status == "pass" and not failed_requirements else "attention"
    completed_operations = bool(status == "pass")
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        "first_complete_manual_playable_demo_validation_pv1_pass",
    )
    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "operator": str(args.operator or "unknown"),
            "requested_signoff_status": requested_status,
            "notes": str(args.notes or ""),
            "source_session_manifest": str(session_manifest_path.resolve()) if session_manifest_path.exists() else "",
            "source_e2b_report": str(e2b_report_path.resolve()) if e2b_report_path.exists() else "",
            "checked_packages": checked_packages,
            "checked_package_ids": checked_package_ids,
            "checked_package_count": len(checked_package_ids),
            "completed_operations": completed_operations,
            "issues": failed_requirements if status != "pass" else [],
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
            },
            "failed_requirements": failed_requirements,
        },
        "aiue_manual_playable_demo_validation_pv1_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_manual_playable_demo_validation_pv1_report",
            notes=[
                "governance_signoff_only",
                "manual_demo_validation_not_automation_authority",
                "pv1_playable_demo_signoff",
            ],
        ),
    )
    report_path = output_root / "manual_playable_demo_validation_pv1_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
