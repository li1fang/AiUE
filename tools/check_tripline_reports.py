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

from aiue_core.schema_utils import load_json, load_workspace_config
from aiue_unreal.command_catalog import COMMANDS
from aiue_unreal.guards import GuardError, ensure_action_allowed


def latest_file(root: Path, pattern: str) -> Path | None:
    candidates = sorted(root.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def check_smoke_e2e(conversion_root: Path) -> dict:
    report_path = latest_file(conversion_root / "_e2e_runs" / "smoke", "*/e2e_run_report.json")
    if not report_path:
        return {"name": "smoke_e2e", "status": "fail", "errors": ["missing_smoke_e2e_report"]}
    payload = load_json(report_path)
    stage_results = payload.get("stage_results") or {}
    required_stages = ["preflight", "conversion", "ue", "native", "animation"]
    failed_stages = [stage for stage in required_stages if (stage_results.get(stage) or {}).get("status") != "pass"]
    return {
        "name": "smoke_e2e",
        "status": "pass" if not failed_stages and not payload.get("failures") else "fail",
        "path": str(report_path),
        "errors": failed_stages + list(payload.get("failures") or []),
    }


def check_scene_sweep(saved_root: Path, prefix: str, label: str) -> dict:
    report_path = latest_file(saved_root / "verification", f"{prefix}*/run-scene-sweep.json")
    if not report_path:
        return {"name": label, "status": "fail", "errors": [f"missing_{label}_report"]}
    payload = load_json(report_path)
    result = payload.get("result") or {}
    counts = result.get("counts") or {}
    errors = []
    if not payload.get("success"):
        errors.append("action_not_successful")
    if int(counts.get("failed_packages", 0)) != 0:
        errors.append("failed_packages_nonzero")
    if int(counts.get("captured_after_exit", 0)) != 0:
        errors.append("captured_after_exit_nonzero")
    if int(counts.get("captured_before_report", 0)) <= 0:
        errors.append("captured_before_report_missing")
    return {
        "name": label,
        "status": "pass" if not errors else "fail",
        "path": str(report_path),
        "errors": errors,
    }


def check_bundle_report(saved_root: Path) -> dict:
    report_path = latest_file(saved_root / "open_source_bundle", "*/open_source_readiness_report.json")
    if not report_path:
        return {"name": "bundle_audit", "status": "fail", "errors": ["missing_bundle_report"]}
    payload = load_json(report_path)
    errors = []
    if not payload.get("ready_for_public_export"):
        errors.append("bundle_not_ready_for_public_export")
    return {
        "name": "bundle_audit",
        "status": "pass" if not errors else "fail",
        "path": str(report_path),
        "errors": errors,
    }


def check_destructive_guard() -> dict:
    errors = []
    for command_id, metadata in COMMANDS.items():
        if not metadata.get("destructive"):
            continue
        try:
            ensure_action_allowed({"command": command_id, "allow_destructive": False}, metadata)
            errors.append(f"guard_failed_for:{command_id}")
        except GuardError:
            pass
    return {
        "name": "destructive_guard",
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description="Check AiUE alpha tripline reports.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--aiue-root", default=REPO_ROOT)
    parser.add_argument("--output")
    args = parser.parse_args()

    workspace = load_workspace_config(args.workspace_config)
    aiue_root = Path(args.aiue_root).expanduser().resolve()
    conversion_root = Path(workspace["paths"]["conversion_root"]).expanduser().resolve()
    saved_root = aiue_root / "Saved"

    checks = [
        check_smoke_e2e(conversion_root),
        check_scene_sweep(saved_root, "weapon_split_cmd", "weapon_split_cmd"),
        check_scene_sweep(saved_root, "weapon_split_editor", "weapon_split_editor"),
        check_scene_sweep(saved_root, "core_regression_cmd", "core_regression_cmd"),
        check_scene_sweep(saved_root, "core_regression_editor", "core_regression_editor"),
        check_bundle_report(saved_root),
        check_destructive_guard(),
    ]
    failed = [item for item in checks if item["status"] != "pass"]
    report = {
        "status": "pass" if not failed else "fail",
        "checks": checks,
        "failed_checks": [item["name"] for item in failed],
    }
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
