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
    )
    window.show()
    app.processEvents()

    if args.dump_state_json:
        print(json.dumps(window.current_dump_payload(), ensure_ascii=False, indent=2))

    if args.exit_after_load:
        return 0 if window.app_state.status == "pass" else 1

    exit_code = app.exec()
    if exit_code != 0:
        return exit_code
    return 0 if window.app_state.status == "pass" else 1
