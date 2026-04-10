from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json
from aiue_unreal.host_bridge import run_host_auto_ue_cli

GATE_ID = "demo_action_preview_d2"
DEMO_HOST_KEY = "demo"
REQUIRED_MODE = "editor_rendered"
DEFAULT_LEVEL_PATH = "/Game/Levels/DefaultLevel"
SHOT_ORDER = ["front", "side"]
ACTION_KIND = "root_translate_and_turn"
FIXED_EXECUTION_PROFILE = {
    "host_key": DEMO_HOST_KEY,
    "mode": REQUIRED_MODE,
    "level_path": DEFAULT_LEVEL_PATH,
    "shot_order": list(SHOT_ORDER),
    "camera_mode": "explicit_pose",
    "capture_width": 1280,
    "capture_height": 720,
    "capture_delay_seconds": 0.2,
    "subject_min_screen_coverage": 0.015,
    "weapon_min_screen_coverage": 0.001,
    "action_kind": ACTION_KIND,
    "action_distance": 85.0,
    "action_yaw_delta": 24.0,
    "action_settle_seconds": 0.2,
    "min_distance_delta": 40.0,
    "min_yaw_delta": 10.0,
    "histogram_l1_threshold": 0.015,
    "mean_abs_pixel_delta_threshold": 0.005,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE D2 demo action preview gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--d1-report-path")
    parser.add_argument("--package-id")
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


def make_failed_requirement(requirement_id: str, message: str, **details) -> dict:
    payload = {
        "id": requirement_id,
        "message": message,
    }
    payload.update(details)
    return payload


def resolve_d1_report_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"D1 report path does not exist: {candidate}")
    candidate = default_latest_d1_report_path(workspace)
    if candidate.exists():
        return candidate
    raise FileNotFoundError("No latest_demo_stage_d1_onboarding_report.json could be resolved for D2.")


def resolve_target_package(d1_report: dict, requested_package_id: str | None) -> dict | None:
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
    if requested_package_id:
        for item in candidates:
            if item["package_id"] == requested_package_id:
                return item
        return None
    return candidates[0] if candidates else None


def compare_image_motion(repo_root: Path, before_path: str, after_path: str) -> dict:
    script_path = repo_root / "tools" / "compare_image_motion.ps1"
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-BeforePath",
            before_path,
            "-AfterPath",
            after_path,
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout or "compare_image_motion failed")
    return json.loads(completed.stdout.strip())


def evaluate_external_motion(repo_root: Path, shots: list[dict]) -> tuple[list[dict], list[dict]]:
    failed_requirements: list[dict] = []
    evaluated = []
    motion_pass_count = 0
    for shot in shots:
        before = dict(shot.get("before") or {})
        after = dict(shot.get("after") or {})
        before_path = str(before.get("image_path") or "")
        after_path = str(after.get("image_path") or "")
        metrics = None
        errors = []
        if before_path and after_path and Path(before_path).exists() and Path(after_path).exists():
            try:
                metrics = compare_image_motion(repo_root, before_path, after_path)
            except Exception as exc:
                errors.append(f"motion_compare_failed:{exc}")
        else:
            errors.append("before_or_after_image_missing")

        histogram_l1 = float((metrics or {}).get("histogram_l1") or 0.0)
        mean_abs_pixel_delta = float((metrics or {}).get("mean_abs_pixel_delta") or 0.0)
        pass_threshold = (
            histogram_l1 >= FIXED_EXECUTION_PROFILE["histogram_l1_threshold"]
            or mean_abs_pixel_delta >= FIXED_EXECUTION_PROFILE["mean_abs_pixel_delta_threshold"]
        )
        motion_pass = bool(pass_threshold and not errors)
        motion_pass_count += int(motion_pass)
        evaluated.append(
            {
                "shot_id": shot.get("shot_id"),
                "camera_id": shot.get("camera_id"),
                "before_image_path": before_path,
                "after_image_path": after_path,
                "histogram_l1": histogram_l1,
                "mean_abs_pixel_delta": mean_abs_pixel_delta,
                "thresholds": {
                    "histogram_l1_threshold": FIXED_EXECUTION_PROFILE["histogram_l1_threshold"],
                    "mean_abs_pixel_delta_threshold": FIXED_EXECUTION_PROFILE["mean_abs_pixel_delta_threshold"],
                },
                "status": "pass" if motion_pass else "fail",
                "errors": errors,
                "metrics": metrics or {},
            }
        )

    if motion_pass_count < 1:
        failed_requirements.append(
            make_failed_requirement(
                "external_motion_evidence",
                "At least one fixed camera shot must show external motion evidence after the demo action preview.",
                required_motion_pass_shots=1,
                actual_motion_pass_shots=motion_pass_count,
            )
        )
    return evaluated, failed_requirements


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
        payload["reason"] = "d2_first_complete_pass"
        return payload
    if status != "pass" and current_failed_ids and previous_status != "pass" and current_failed_ids == previous_failed_ids:
        payload["should_discuss"] = True
        payload["reason"] = "same_failed_requirement_two_rounds"
        payload["repeated_failed_requirement_ids"] = current_failed_ids
    return payload


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
    d1_report_path = resolve_d1_report_path(workspace, args.d1_report_path)
    d1_report = load_json(d1_report_path)
    if d1_report.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "d1_prerequisite",
                "D2 requires a passing D1 demo onboarding report.",
                d1_report_path=str(d1_report_path),
                d1_status=d1_report.get("status"),
            )
        )

    target_package = resolve_target_package(d1_report, args.package_id)
    if not target_package:
        failed_requirements.append(
            make_failed_requirement(
                "d1_target_package",
                "D2 could not resolve a passing runtime-ready package from D1.",
                d1_report_path=str(d1_report_path),
                requested_package_id=args.package_id or "",
            )
        )

    level_path = str((d1_report.get("level_path") or FIXED_EXECUTION_PROFILE["level_path"]))
    action_result_path = output_root / "action_preview_result.json"
    action_payload = None
    action_result = {}
    if not failed_requirements and target_package:
        action_payload = run_host_auto_ue_cli(
            workspace_or_config=workspace,
            mode=REQUIRED_MODE,
            command="action-preview",
            params={
                "package_id": target_package["package_id"],
                "sample_id": target_package.get("sample_id"),
                "host_blueprint_asset_path": target_package["host_blueprint_asset_path"],
                "level_path": level_path,
                "location": {"x": 0.0, "y": 0.0, "z": 120.0},
                "rotation": {"pitch": 0.0, "yaw": 180.0, "roll": 0.0},
                "output_root": str((output_root / "captures").resolve()),
                "shot_order": list(SHOT_ORDER),
                "capture_width": FIXED_EXECUTION_PROFILE["capture_width"],
                "capture_height": FIXED_EXECUTION_PROFILE["capture_height"],
                "capture_delay_seconds": FIXED_EXECUTION_PROFILE["capture_delay_seconds"],
                "subject_min_screen_coverage": FIXED_EXECUTION_PROFILE["subject_min_screen_coverage"],
                "weapon_min_screen_coverage": FIXED_EXECUTION_PROFILE["weapon_min_screen_coverage"],
                "action_kind": FIXED_EXECUTION_PROFILE["action_kind"],
                "action_distance": FIXED_EXECUTION_PROFILE["action_distance"],
                "action_yaw_delta": FIXED_EXECUTION_PROFILE["action_yaw_delta"],
                "action_settle_seconds": FIXED_EXECUTION_PROFILE["action_settle_seconds"],
                "min_distance_delta": FIXED_EXECUTION_PROFILE["min_distance_delta"],
                "min_yaw_delta": FIXED_EXECUTION_PROFILE["min_yaw_delta"],
            },
            output_path=str(action_result_path.resolve()),
            host_key=DEMO_HOST_KEY,
        )
        action_result = dict((action_payload.get("payload") or {}).get("result") or {})
        if not action_payload.get("payload", {}).get("success") or action_result.get("status") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "action_preview_host",
                    "Demo host action-preview command did not complete successfully.",
                    action_result_path=str(action_result_path.resolve()),
                    host_status=action_result.get("status"),
                    host_errors=list(action_result.get("errors") or []),
                )
            )

    shots = list(action_result.get("shots") or [])
    external_motion_evidence = []
    if not failed_requirements and shots:
        external_motion_evidence, motion_failures = evaluate_external_motion(repo_root, shots)
        failed_requirements.extend(motion_failures)

    transform_delta = dict(action_result.get("transform_delta") or {})
    if action_result:
        if float(transform_delta.get("distance_delta") or 0.0) < FIXED_EXECUTION_PROFILE["min_distance_delta"] and abs(float(transform_delta.get("yaw_delta") or 0.0)) < FIXED_EXECUTION_PROFILE["min_yaw_delta"]:
            failed_requirements.append(
                make_failed_requirement(
                    "engine_action_delta",
                    "Demo host action preview did not move or rotate enough to count as a meaningful action.",
                    transform_delta=transform_delta,
                )
            )

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(status, failed_requirements, previous_report, previous_report_path)
    counts = {
        "requested_packages": 1 if target_package else 0,
        "resolved_packages": 1 if target_package else 0,
        "captured_shot_pairs": sum(1 for shot in shots if (shot.get("before") or {}).get("image_path") and (shot.get("after") or {}).get("image_path")),
        "passing_engine_shots": sum(1 for shot in shots if shot.get("status") == "pass"),
        "passing_external_motion_shots": sum(1 for item in external_motion_evidence if item.get("status") == "pass"),
    }
    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": args.workspace_config,
            "host_key": DEMO_HOST_KEY,
            "level_path": level_path,
            "package_id": target_package["package_id"] if target_package else None,
            "sample_id": target_package.get("sample_id") if target_package else None,
            "host_blueprint_asset": target_package.get("host_blueprint_asset_path") if target_package else None,
            "fixed_execution_profile": FIXED_EXECUTION_PROFILE,
            "counts": counts,
            "failed_requirements": failed_requirements,
            "engine_evidence": {
                "action_kind": action_result.get("action_kind"),
                "before_actor_transform": action_result.get("before_actor_transform"),
                "after_actor_transform": action_result.get("after_actor_transform"),
                "transform_delta": transform_delta,
                "shots": shots,
            },
            "external_motion_evidence": external_motion_evidence,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "d1_report_path": str(d1_report_path.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
                "action_result_path": str(action_result_path.resolve()),
            },
        },
        "aiue_demo_action_preview_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_demo_action_preview_report",
            notes=["internal_demo_action_preview_gate", "demo_host_only", "external_histogram_motion_evidence"],
        ),
    )
    report_path = output_root / "d2_demo_action_preview_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    print(f"D2 demo action preview report written to: {report_path}")
    raise SystemExit(0 if status == "pass" else 1)


if __name__ == "__main__":
    main()
