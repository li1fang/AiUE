from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from aiue_t2.state import resolve_manifest_path
from aiue_t2.ui import WorkbenchWindow


REPO_ROOT = Path(__file__).resolve().parents[4]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE T2 Windows Native Workbench.")
    parser.add_argument("--latest", action="store_true", help="Open Saved/tooling/t1/latest/manifest.json")
    parser.add_argument("--manifest", help="Open a specific T1 manifest path.")
    parser.add_argument("--session-manifest", help="Open a specific E2 session manifest path.")
    parser.add_argument("--workspace-config", help="Workspace config path for controlled demo request dry-runs.")
    parser.add_argument("--package-id", help="Override the selected E2 package id.")
    parser.add_argument("--action-preset-id", help="Override the selected E2 action preset id.")
    parser.add_argument("--animation-preset-id", help="Override the selected E2 animation preset id.")
    parser.add_argument("--review-compare-index", type=int, default=0, help="Select which bounded compare pair to focus.")
    parser.add_argument("--demo-request-export", action="store_true", help="Export the currently selected E2 demo request.")
    parser.add_argument("--demo-request-dry-run", action="store_true", help="Dry-run the currently selected E2 demo request.")
    parser.add_argument("--demo-request-invoke", action="store_true", help="Invoke the currently selected E2 demo request.")
    parser.add_argument("--demo-session-round-invoke", action="store_true", help="Invoke the full E2 session round through T2 native control.")
    parser.add_argument("--demo-review-replay", action="store_true", help="Replay the focused E2 review request through T2 native review control.")
    parser.add_argument(
        "--demo-request-kind",
        choices=["action_preview", "animation_preview"],
        default="action_preview",
        help="Select which demo request kind to export or dry-run.",
    )
    parser.add_argument("--dump-state-json", action="store_true", help="Print the current workbench state as JSON.")
    parser.add_argument("--exit-after-load", action="store_true", help="Load the manifest and exit immediately.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_path = resolve_manifest_path(
        repo_root=REPO_ROOT,
        manifest_path=args.manifest,
        latest=args.latest or not args.manifest,
    )
    app = QApplication.instance() or QApplication(sys.argv[:1] if argv is None else ["aiue-t2", *argv])
    app.setApplicationName("AiUE T2 Workbench")
    window = WorkbenchWindow(
        manifest_path=manifest_path,
        session_manifest_path=Path(args.session_manifest).expanduser().resolve() if args.session_manifest else None,
        repo_root=REPO_ROOT,
        workspace_config_path=Path(args.workspace_config).expanduser().resolve() if args.workspace_config else None,
        selected_package_id=args.package_id,
        selected_action_preset_id=args.action_preset_id,
        selected_animation_preset_id=args.animation_preset_id,
        selected_review_compare_index=args.review_compare_index,
    )
    window.show()
    app.processEvents()

    operation_requested = False
    if args.demo_request_export:
        operation_requested = True
        window.export_current_demo_request(request_kind=args.demo_request_kind)
        app.processEvents()
    if args.demo_request_dry_run:
        operation_requested = True
        window.dry_run_current_demo_request(
            request_kind=args.demo_request_kind,
            workspace_config_path=Path(args.workspace_config).expanduser().resolve() if args.workspace_config else None,
        )
        app.processEvents()
    if args.demo_request_invoke:
        operation_requested = True
        window.invoke_current_demo_request(
            request_kind=args.demo_request_kind,
            workspace_config_path=Path(args.workspace_config).expanduser().resolve() if args.workspace_config else None,
        )
        app.processEvents()
    if args.demo_session_round_invoke:
        operation_requested = True
        window.invoke_session_round(
            workspace_config_path=Path(args.workspace_config).expanduser().resolve() if args.workspace_config else None,
        )
        app.processEvents()
    if args.demo_review_replay:
        operation_requested = True
        window.replay_current_demo_review(
            request_kind=args.demo_request_kind,
            workspace_config_path=Path(args.workspace_config).expanduser().resolve() if args.workspace_config else None,
        )
        app.processEvents()

    if args.dump_state_json:
        print(json.dumps(window.current_dump_payload(), ensure_ascii=False, indent=2))

    if args.exit_after_load:
        status_ok = window.app_state.status == "pass"
        if operation_requested:
            payload = window.current_dump_payload()
            status_ok = status_ok and (
                payload.get("demo_request_control", {}).get("status") == "pass"
                or payload.get("demo_review_replay_control", {}).get("status") == "pass"
                or payload.get("demo_round_control", {}).get("status") == "pass"
            )
        return 0 if status_ok else 1

    exit_code = app.exec()
    if exit_code != 0:
        return exit_code
    status_ok = window.app_state.status == "pass"
    if operation_requested:
        payload = window.current_dump_payload()
        status_ok = status_ok and (
            payload.get("demo_request_control", {}).get("status") == "pass"
            or payload.get("demo_review_replay_control", {}).get("status") == "pass"
            or payload.get("demo_round_control", {}).get("status") == "pass"
        )
    return 0 if status_ok else 1
