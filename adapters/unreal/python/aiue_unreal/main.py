from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CORE_ROOT = SCRIPT_DIR.parents[3] / "core" / "python"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

from aiue_core.schema_utils import load_workspace_config
from aiue_unreal.action_runner import load_action_spec, normalize_action_spec, parse_params_json, run_action
from aiue_unreal.probe_runner import probe_capabilities


def parse_args():
    parser = argparse.ArgumentParser(description="Run AiUE Unreal adapter commands.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--command")
    parser.add_argument("--action-spec")
    parser.add_argument("--mode", default="cmd_nullrhi")
    parser.add_argument("--params-json")
    parser.add_argument("--output-path")
    parser.add_argument("--allow-destructive", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run-id")
    return parser.parse_args()


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    if args.command == "probe-capabilities":
        result = probe_capabilities(workspace, mode=args.mode, run_id=args.run_id)
        print(json.dumps({"status": "pass", "capabilities_path": result["capabilities_path"]}, ensure_ascii=False))
        return
    action_spec = normalize_action_spec(
        action_spec=load_action_spec(args.action_spec),
        command=args.command,
        mode=args.mode,
        params=parse_params_json(args.params_json),
        allow_destructive=args.allow_destructive,
        dry_run=args.dry_run,
        output_path=args.output_path
    )
    if not action_spec.get("command"):
        raise SystemExit("AiUE requires --command or --action-spec")
    payload, output_path = run_action(action_spec, workspace)
    print(json.dumps({"output_path": output_path, "status": payload["status"]}, ensure_ascii=False))
    if not payload.get("success"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
