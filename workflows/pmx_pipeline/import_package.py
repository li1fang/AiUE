from __future__ import annotations

import argparse
import json

from _bootstrap import ensure_aiue_paths

ensure_aiue_paths()

from aiue_core.schema_utils import load_workspace_config
from aiue_unreal.action_runner import run_action


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE PMX import-package workflow.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--mode", default="cmd_nullrhi")
    parser.add_argument("--profile")
    parser.add_argument("--asset-root")
    parser.add_argument("--output-path")
    return parser.parse_args()


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    payload, output_path = run_action(
        {
            "command": "import-package",
            "mode": args.mode,
            "params": {
                "manifest": args.manifest,
                "profile": args.profile,
                "asset_root": args.asset_root
            },
            "output_path": args.output_path
        },
        workspace
    )
    print(json.dumps({"output_path": output_path, "status": payload["status"]}, ensure_ascii=False))
    if not payload.get("success"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
