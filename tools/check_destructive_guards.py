from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = REPO_ROOT / "core" / "python"
ADAPTER_ROOT = REPO_ROOT / "adapters" / "unreal" / "python"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))
if str(ADAPTER_ROOT) not in sys.path:
    sys.path.insert(0, str(ADAPTER_ROOT))

from aiue_unreal.command_catalog import COMMANDS
from aiue_unreal.guards import GuardError, ensure_action_allowed


def main() -> None:
    parser = argparse.ArgumentParser(description="Check AiUE destructive command guards.")
    parser.add_argument("--output")
    args = parser.parse_args()

    results = []
    failures = []
    for command_id, metadata in sorted(COMMANDS.items()):
        if not metadata.get("destructive"):
            continue
        blocked_without_flag = False
        allowed_with_flag = False
        try:
            ensure_action_allowed({"command": command_id, "allow_destructive": False}, metadata)
        except GuardError:
            blocked_without_flag = True
        try:
            ensure_action_allowed({"command": command_id, "allow_destructive": True}, metadata)
            allowed_with_flag = True
        except GuardError:
            allowed_with_flag = False
        status = "pass" if blocked_without_flag and allowed_with_flag else "fail"
        if status != "pass":
            failures.append(command_id)
        results.append(
            {
                "command": command_id,
                "status": status,
                "blocked_without_flag": blocked_without_flag,
                "allowed_with_flag": allowed_with_flag,
            }
        )

    report = {
        "status": "pass" if not failures else "fail",
        "checked_commands": len(results),
        "failed_commands": failures,
        "results": results,
    }
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
