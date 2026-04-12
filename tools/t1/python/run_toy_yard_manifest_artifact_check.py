from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import ensure_t1_paths

REPO_ROOT = ensure_t1_paths()

from aiue_core.schema_utils import load_workspace_config
from aiue_t1.toy_yard_manifest_artifact_check import write_manifest_artifact_check_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE toy-yard manifest artifact self-check.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT.resolve()))
    parser.add_argument("--workspace-config")
    parser.add_argument("--view-root")
    parser.add_argument("--summary")
    parser.add_argument("--manifest")
    parser.add_argument("--output-path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config) if args.workspace_config else None
    payload = write_manifest_artifact_check_report(
        repo_root=Path(args.repo_root).expanduser().resolve(),
        manifest_path=Path(args.manifest).expanduser().resolve() if args.manifest else None,
        workspace=workspace,
        workspace_config_path=Path(args.workspace_config).expanduser().resolve() if args.workspace_config else None,
        view_root=Path(args.view_root).expanduser().resolve() if args.view_root else None,
        summary=Path(args.summary).expanduser().resolve() if args.summary else None,
        output_path=Path(args.output_path).expanduser().resolve() if args.output_path else None,
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
