from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = REPO_ROOT / "core" / "python"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from aiue_core.schema_utils import load_workspace_config


REQUIRED_PATH_KEYS = [
    "unreal_project_root",
    "aiue_repo_root",
    "blender_addon_root",
    "dataset_root",
    "dataset_catalog_root",
    "preflight_root",
    "conversion_root",
    "blender_python_exe",
    "unreal_editor_cmd",
    "unreal_editor_gui",
    "asset_root",
    "visual_review_output_root",
    "capability_probe_root",
    "auto_ue_cli_output_root",
]


def path_status(value: str):
    if value.startswith("/Game/"):
        return {"kind": "virtual_asset_path", "exists": True}
    path = Path(value).expanduser()
    return {"kind": "filesystem", "exists": path.exists()}


def main():
    parser = argparse.ArgumentParser(description="Dry-run an AiUE workspace config.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--allow-missing-paths", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()

    workspace = load_workspace_config(args.config)
    missing_keys = [key for key in REQUIRED_PATH_KEYS if key not in workspace["paths"]]
    path_checks = {}
    missing_paths = []
    for key in REQUIRED_PATH_KEYS:
        value = workspace["paths"].get(key)
        if value is None:
            continue
        status = path_status(str(value))
        path_checks[key] = {"value": value, **status}
        if not status["exists"]:
            missing_paths.append(key)

    report = {
        "status": "pass" if not missing_keys and (args.allow_missing_paths or not missing_paths) else "fail",
        "version": workspace.get("version"),
        "config_path": workspace["config_path"],
        "config_hash": workspace["config_hash"],
        "missing_required_keys": missing_keys,
        "missing_paths": missing_paths,
        "allow_missing_paths": bool(args.allow_missing_paths),
        "path_checks": path_checks,
    }
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(1 if report["status"] != "pass" else 0)


if __name__ == "__main__":
    main()
