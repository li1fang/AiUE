from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import ensure_t2_paths

REPO_ROOT = ensure_t2_paths()

from aiue_t2.demo_request_runner import (
    export_demo_request,
    invoke_demo_request,
    load_demo_request_selection,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve or execute an AiUE E2 demo request.")
    parser.add_argument("--latest", action="store_true", help="Resolve the latest T1 manifest.")
    parser.add_argument("--manifest", help="Resolve a specific T1 manifest path.")
    parser.add_argument("--session-manifest", help="Resolve a specific E2 session manifest path.")
    parser.add_argument("--package-id", help="Override the selected package id.")
    parser.add_argument("--action-preset-id", help="Override the selected action preset id.")
    parser.add_argument("--animation-preset-id", help="Override the selected animation preset id.")
    parser.add_argument(
        "--request-kind",
        choices=("action_preview", "animation_preview"),
        default="action_preview",
        help="Select which request kind to materialize.",
    )
    parser.add_argument("--dump-request-json", action="store_true", help="Print the selected request payload as JSON.")
    parser.add_argument("--write-request-path", help="Write the selected request payload to a JSON file.")
    parser.add_argument("--workspace-config", help="Workspace config path required for --invoke.")
    parser.add_argument("--result-json-path", help="Write invoke output to this JSON path.")
    parser.add_argument("--invoke", action="store_true", help="Invoke the selected request through auto_ue_cli.")
    parser.add_argument("--dry-run", action="store_true", help="Invoke the selected request with -DryRun.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selection = load_demo_request_selection(
        repo_root=REPO_ROOT,
        manifest_path=args.manifest,
        latest=args.latest or not args.manifest,
        session_manifest_path=args.session_manifest,
        package_id=args.package_id,
        action_preset_id=args.action_preset_id,
        animation_preset_id=args.animation_preset_id,
        request_kind=args.request_kind,
    )

    payload: dict = selection.to_dump_dict()
    if args.write_request_path:
        request_json_path = export_demo_request(selection, request_json_path=args.write_request_path)
        payload["request_json_path"] = str(request_json_path)

    if args.invoke:
        if not args.workspace_config:
            raise SystemExit("--workspace-config is required when --invoke is used.")
        invocation_payload = invoke_demo_request(
            selection,
            workspace_config=args.workspace_config,
            result_json_path=args.result_json_path,
            dry_run=args.dry_run,
        )
        payload["invoke"] = invocation_payload
    elif args.dry_run:
        if not args.workspace_config:
            raise SystemExit("--workspace-config is required when --dry-run is used.")
        invocation_payload = invoke_demo_request(
            selection,
            workspace_config=args.workspace_config,
            result_json_path=args.result_json_path,
            dry_run=True,
        )
        payload["invoke"] = invocation_payload

    if args.dump_request_json or args.invoke or args.dry_run or args.write_request_path:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
