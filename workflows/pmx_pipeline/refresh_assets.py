from __future__ import annotations

import argparse
import json

from _bootstrap import ensure_aiue_paths

ensure_aiue_paths()

from aiue_core.schema_utils import load_workspace_config
from aiue_unreal.action_runner import run_action


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE PMX refresh-assets workflow.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--mode", default="cmd_nullrhi")
    parser.add_argument("--asset-root")
    parser.add_argument("--registry-output")
    parser.add_argument("--assets-output")
    parser.add_argument("--force-blueprint-fallback", action="store_true")
    parser.add_argument("--output-path")
    return parser.parse_args()


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    payload, output_path = run_action(
        {
            "command": "refresh-assets",
            "mode": args.mode,
            "params": {
                "summary": args.summary,
                "asset_root": args.asset_root,
                "registry_output": args.registry_output,
                "assets_output": args.assets_output,
                "force_blueprint_fallback": args.force_blueprint_fallback
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
