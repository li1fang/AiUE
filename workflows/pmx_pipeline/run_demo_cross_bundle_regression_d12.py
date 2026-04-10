from __future__ import annotations

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json

GATE_ID = "demo_cross_bundle_regression_d12"
DEFAULT_ANIMATION_ASSET_PATH = "/Game/CombatMagicAnims/Demo/Mannequins/Anims/Unarmed/Attack/MM_Attack_01"
STEP_DEFINITIONS = [
    {
        "step_id": "d4",
        "script_name": "run_demo_retarget_preflight_d4.ps1",
        "report_name": "d4_demo_retarget_preflight_report.json",
        "latest_name": "latest_d4_demo_retarget_preflight_report.json",
    },
    {
        "step_id": "d5",
        "script_name": "run_demo_retarget_bootstrap_d5.ps1",
        "report_name": "d5_demo_retarget_bootstrap_report.json",
        "latest_name": "latest_d5_demo_retarget_bootstrap_report.json",
    },
    {
        "step_id": "d7",
        "script_name": "run_demo_retarget_refine_chains_d7.ps1",
        "report_name": "d7_demo_retarget_refine_chains_report.json",
        "latest_name": "latest_d7_demo_retarget_refine_chains_report.json",
    },
    {
        "step_id": "d8",
        "script_name": "run_demo_retargeted_animation_preview_d8.ps1",
        "report_name": "d8_demo_retargeted_animation_preview_report.json",
        "latest_name": "latest_d8_demo_retargeted_animation_preview_report.json",
    },
    {
        "step_id": "d10",
        "script_name": "run_demo_animation_family_regression_d10.ps1",
        "report_name": "d10_demo_animation_family_regression_report.json",
        "latest_name": "latest_d10_demo_animation_family_regression_report.json",
    },
    {
        "step_id": "d11",
        "script_name": "run_demo_animation_stability_regression_d11.ps1",
        "report_name": "d11_demo_animation_stability_regression_report.json",
        "latest_name": "latest_d11_demo_animation_stability_regression_report.json",
    },
]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE D12 cross-bundle demo regression gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--d1-report-path")
    parser.add_argument("--primary-package-id")
    parser.add_argument("--secondary-package-id")
    parser.add_argument("--animation-asset-path", default=DEFAULT_ANIMATION_ASSET_PATH)
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def repo_root_from_workspace(workspace: dict) -> Path:
    return Path(workspace["paths"].get("aiue_repo_root") or REPO_ROOT).expanduser().resolve()


def default_output_root(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / f"{GATE_ID}_{run_stamp()}"


def default_latest_report_path(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / f"latest_{GATE_ID}_report.json"


def default_latest_d1_report_path(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / "latest_demo_stage_d1_onboarding_report.json"


def default_latest_d8_report_path(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / "latest_demo_retargeted_animation_preview_d8_report.json"


def make_failed_requirement(requirement_id: str, message: str, **details) -> dict:
    payload = {"id": requirement_id, "message": message}
    payload.update(details)
    return payload


def resolve_report_path(explicit_path: str | None, fallback_path: Path, missing_message: str) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Report path does not exist: {candidate}")
    if fallback_path.exists():
        return fallback_path
    raise FileNotFoundError(missing_message)


def resolve_secondary_package(d1_report: dict, primary_package_id: str | None, explicit_secondary_package_id: str | None) -> dict | None:
    package_results = list((((d1_report.get("scene_sweep") or {}).get("result") or {}).get("package_results") or []))
    candidates = []
    for entry in package_results:
        package_id = str(entry.get("package_id") or "")
        host_asset = str(entry.get("host_blueprint_asset_path") or "")
        if not package_id or not host_asset or entry.get("status") != "pass":
            continue
        candidates.append(
            {
                "package_id": package_id,
                "sample_id": entry.get("sample_id"),
                "host_blueprint_asset_path": host_asset,
            }
        )
    candidates = sorted(candidates, key=lambda item: item["package_id"])
    if explicit_secondary_package_id:
        for item in candidates:
            if item["package_id"] == explicit_secondary_package_id:
                return item
        return None
    for item in candidates:
        if item["package_id"] != str(primary_package_id or ""):
            return item
    return None


def build_discussion_signal(status: str, failed_requirements: list[dict], previous_report: dict | None, previous_report_path: Path | None) -> dict:
    current_failed_ids = sorted({item.get("id") for item in failed_requirements if item.get("id")})
    previous_failed_ids = sorted(
        {
            item.get("id")
            for item in ((previous_report or {}).get("failed_requirements") or [])
            if isinstance(item, dict) and item.get("id")
        }
    )
    previous_status = (previous_report or {}).get("status")
    payload = {
        "should_discuss": False,
        "reason": None,
        "previous_report_path": str(previous_report_path) if previous_report_path else None,
        "repeated_failed_requirement_ids": [],
    }
    if status == "pass" and previous_status != "pass":
        payload["should_discuss"] = True
        payload["reason"] = "d12_first_complete_pass"
        return payload
    if status != "pass" and current_failed_ids and previous_status != "pass" and current_failed_ids == previous_failed_ids:
        payload["should_discuss"] = True
        payload["reason"] = "same_failed_requirement_two_rounds"
        payload["repeated_failed_requirement_ids"] = current_failed_ids
    return payload


def run_step(script_path: Path, arguments: list[str]) -> tuple[int, str, str]:
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        *arguments,
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode, completed.stdout, completed.stderr


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict] = []
    d1_report_path = resolve_report_path(
        args.d1_report_path,
        default_latest_d1_report_path(workspace),
        "No latest_demo_stage_d1_onboarding_report.json could be resolved for D12.",
    )
    d1_report = load_json(d1_report_path)
    d8_report_path = resolve_report_path(
        None,
        default_latest_d8_report_path(workspace),
        "No latest_demo_retargeted_animation_preview_d8_report.json could be resolved for D12.",
    )
    d8_report = load_json(d8_report_path)
    primary_package_id = str(args.primary_package_id or d8_report.get("package_id") or "")
    secondary_package = resolve_secondary_package(d1_report, primary_package_id, args.secondary_package_id)
    if not secondary_package:
        failed_requirements.append(
            make_failed_requirement(
                "secondary_package_resolution",
                "D12 could not resolve a second passing runtime-ready package distinct from the current primary package.",
                primary_package_id=primary_package_id,
                requested_secondary_package_id=args.secondary_package_id or "",
                d1_report_path=str(d1_report_path),
            )
        )

    per_step_results = []
    current_report_path: Path | None = None
    if not failed_requirements and secondary_package:
        current_report_path = None
        for step in STEP_DEFINITIONS:
            step_root = output_root / step["step_id"]
            step_root.mkdir(parents=True, exist_ok=True)
            step_report_path = step_root / step["report_name"]
            step_latest_path = step_root / step["latest_name"]
            script_path = repo_root / step["script_name"]
            arguments = [
                "-WorkspaceConfig",
                args.workspace_config,
                "-OutputRoot",
                str(step_root),
                "-LatestReportPath",
                str(step_latest_path),
            ]
            if step["step_id"] == "d4":
                arguments += [
                    "-PackageId",
                    secondary_package["package_id"],
                    "-AnimationAssetPath",
                    args.animation_asset_path,
                    "-D1ReportPath",
                    str(d1_report_path),
                ]
            elif step["step_id"] == "d5":
                arguments += ["-D4ReportPath", str(current_report_path)]
            elif step["step_id"] == "d7":
                arguments += ["-D5ReportPath", str(current_report_path)]
            elif step["step_id"] == "d8":
                arguments += [
                    "-D7ReportPath",
                    str(current_report_path),
                    "-AnimationAssetPath",
                    args.animation_asset_path,
                ]
            elif step["step_id"] == "d10":
                arguments += ["-D8ReportPath", str(current_report_path)]
            elif step["step_id"] == "d11":
                arguments += ["-D10ReportPath", str(current_report_path)]

            returncode, stdout, stderr = run_step(script_path, arguments)
            step_report = load_json(step_report_path) if step_report_path.exists() else None
            per_step_results.append(
                {
                    "step_id": step["step_id"],
                    "status": (step_report or {}).get("status") or ("pass" if returncode == 0 else "fail"),
                    "returncode": returncode,
                    "stdout": stdout.strip(),
                    "stderr": stderr.strip(),
                    "report_path": str(step_report_path.resolve()),
                    "latest_report_path": str(step_latest_path.resolve()),
                }
            )
            current_report_path = step_report_path
            if returncode != 0 or not step_report or step_report.get("status") != "pass":
                failed_requirements.append(
                    make_failed_requirement(
                        "pipeline_step_failed",
                        "A required D12 pipeline step did not pass for the second ready PMX bundle.",
                        step_id=step["step_id"],
                        report_path=str(step_report_path.resolve()),
                        returncode=returncode,
                    )
                )
                break

    final_step_report = load_json(current_report_path) if current_report_path and current_report_path.exists() else None
    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(status, failed_requirements, previous_report, previous_report_path)
    counts = {
        "requested_secondary_packages": 1 if secondary_package else 0,
        "resolved_secondary_packages": 1 if secondary_package else 0,
        "completed_pipeline_steps": len(per_step_results),
        "passing_pipeline_steps": sum(1 for item in per_step_results if item.get("status") == "pass"),
    }

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": args.workspace_config,
            "primary_package_id": primary_package_id,
            "secondary_package_id": secondary_package.get("package_id") if secondary_package else None,
            "secondary_sample_id": secondary_package.get("sample_id") if secondary_package else None,
            "secondary_host_blueprint_asset": secondary_package.get("host_blueprint_asset_path") if secondary_package else None,
            "fixed_execution_profile": {
                "animation_asset_path": args.animation_asset_path,
                "pipeline_steps": [item["step_id"] for item in STEP_DEFINITIONS],
            },
            "counts": counts,
            "failed_requirements": failed_requirements,
            "per_step_results": per_step_results,
            "final_step_report": final_step_report,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "d1_report_path": str(d1_report_path.resolve()),
                "primary_d8_report_path": str(d8_report_path.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
            },
        },
        "aiue_demo_cross_bundle_regression_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_demo_cross_bundle_regression_report",
            notes=["internal_demo_cross_bundle_regression_gate", "demo_host_only", "second_ready_bundle_path"],
        ),
    )
    report_path = output_root / "d12_demo_cross_bundle_regression_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    print(f"D12 demo cross-bundle regression report written to: {report_path}")
    raise SystemExit(0 if status == "pass" else 1)


if __name__ == "__main__":
    main()
