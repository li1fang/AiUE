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

GATE_ID = "demo_retargeted_animation_preview_d8"
DEMO_HOST_KEY = "demo"
REQUIRED_MODE = "editor_rendered"
DEFAULT_LEVEL_PATH = "/Game/Levels/DefaultLevel"
DEFAULT_ANIMATION_ASSET_PATH = "/Game/CombatMagicAnims/Demo/Mannequins/Anims/Unarmed/Attack/MM_Attack_01"
SHOT_ORDER = ["front", "side"]
FIXED_EXECUTION_PROFILE = {
    "host_key": DEMO_HOST_KEY,
    "mode": REQUIRED_MODE,
    "level_path": DEFAULT_LEVEL_PATH,
    "animation_asset_path": DEFAULT_ANIMATION_ASSET_PATH,
    "shot_order": list(SHOT_ORDER),
    "camera_mode": "explicit_pose",
    "capture_width": 1280,
    "capture_height": 720,
    "capture_delay_seconds": 0.2,
    "subject_min_screen_coverage": 0.015,
    "weapon_min_screen_coverage": 0.001,
    "animation_sample_time_seconds": 0.65,
    "animation_settle_seconds": 0.1,
    "histogram_l1_threshold": 0.015,
    "mean_abs_pixel_delta_threshold": 0.005,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE D8 demo retargeted animation preview gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--d7-report-path")
    parser.add_argument("--animation-asset-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def repo_root_from_workspace(workspace: dict) -> Path:
    return Path(workspace["paths"].get("aiue_repo_root") or REPO_ROOT).expanduser().resolve()


def default_output_root(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / f"{GATE_ID}_{run_stamp()}"


def default_latest_report_path(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / f"latest_{GATE_ID}_report.json"


def default_latest_d7_report_path(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / "latest_demo_retarget_refine_chains_d7_report.json"


def make_failed_requirement(requirement_id: str, message: str, **details) -> dict:
    payload = {"id": requirement_id, "message": message}
    payload.update(details)
    return payload


def pose_probe_bone_names_from_d7_report(d7_report: dict) -> list[str]:
    planned_chains = list(((d7_report.get("engine_evidence") or {}).get("planned_chains")) or [])
    ordered = []
    seen = set()
    for chain in planned_chains:
        for key in ("start_bone", "end_bone"):
            bone_name = str(chain.get(key) or "").strip()
            if not bone_name or bone_name in seen:
                continue
            seen.add(bone_name)
            ordered.append(bone_name)
    return ordered


def resolve_d7_report_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"D7 report path does not exist: {candidate}")
    candidate = default_latest_d7_report_path(workspace)
    if candidate.exists():
        return candidate
    raise FileNotFoundError("No latest_demo_retarget_refine_chains_d7_report.json could be resolved for D8.")


def compare_image_motion(repo_root: Path, before_path: str, after_path: str) -> dict:
    script_path = repo_root / "tools" / "compare_image_motion.ps1"
    return subprocess_compare_image_motion(script_path, before_path, after_path, None)


def subprocess_compare_image_motion(script_path: Path, before_path: str, after_path: str, crop_rect: dict | None) -> dict:
    args = [
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
    ]
    if crop_rect:
        args.extend(
            [
                "-CropX",
                str(crop_rect["x"]),
                "-CropY",
                str(crop_rect["y"]),
                "-CropWidth",
                str(crop_rect["width"]),
                "-CropHeight",
                str(crop_rect["height"]),
            ]
        )
    completed = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout or "compare_image_motion failed")
    return json.loads(completed.stdout.strip())


def normalized_screen_rect(screen_rect: dict | None) -> dict | None:
    if not isinstance(screen_rect, dict):
        return None
    try:
        min_x = float(screen_rect["min_x"])
        max_x = float(screen_rect["max_x"])
        min_y = float(screen_rect["min_y"])
        max_y = float(screen_rect["max_y"])
    except Exception:
        return None
    width = max_x - min_x
    height = max_y - min_y
    if width <= 1 or height <= 1:
        return None
    return {
        "min_x": min_x,
        "max_x": max_x,
        "min_y": min_y,
        "max_y": max_y,
        "width": width,
        "height": height,
    }


def merged_crop_rect(rectangles: list[dict], image_width: int, image_height: int, padding_ratio: float = 0.12, min_padding_px: float = 24.0) -> dict | None:
    if not rectangles:
        return None
    min_x = min(rect["min_x"] for rect in rectangles)
    min_y = min(rect["min_y"] for rect in rectangles)
    max_x = max(rect["max_x"] for rect in rectangles)
    max_y = max(rect["max_y"] for rect in rectangles)
    width = max_x - min_x
    height = max_y - min_y
    if width <= 1 or height <= 1:
        return None
    pad_x = max(min_padding_px, width * padding_ratio)
    pad_y = max(min_padding_px, height * padding_ratio)
    clamped_min_x = max(0.0, min_x - pad_x)
    clamped_min_y = max(0.0, min_y - pad_y)
    clamped_max_x = min(float(image_width), max_x + pad_x)
    clamped_max_y = min(float(image_height), max_y + pad_y)
    if clamped_max_x - clamped_min_x <= 1 or clamped_max_y - clamped_min_y <= 1:
        return None
    return {
        "x": clamped_min_x,
        "y": clamped_min_y,
        "width": clamped_max_x - clamped_min_x,
        "height": clamped_max_y - clamped_min_y,
    }


def crop_rect_for_shot(shot: dict) -> dict | None:
    rectangles = []
    for phase_key in ("before", "after"):
        phase = dict(shot.get(phase_key) or {})
        for coverage_key in ("subject_coverage", "weapon_coverage"):
            rect = normalized_screen_rect(dict(phase.get(coverage_key) or {}).get("screen_rect"))
            if rect:
                rectangles.append(rect)
    return merged_crop_rect(
        rectangles,
        image_width=FIXED_EXECUTION_PROFILE["capture_width"],
        image_height=FIXED_EXECUTION_PROFILE["capture_height"],
    )


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
        crop_rect = crop_rect_for_shot(shot)
        if before_path and after_path and Path(before_path).exists() and Path(after_path).exists():
            try:
                metrics = subprocess_compare_image_motion(repo_root / "tools" / "compare_image_motion.ps1", before_path, after_path, crop_rect)
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
                "crop_rect": crop_rect,
            }
        )

    if motion_pass_count < 1:
        failed_requirements.append(
            make_failed_requirement(
                "external_motion_evidence",
                "At least one fixed camera shot must show external motion evidence after the retargeted animation preview.",
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
        payload["reason"] = "d8_first_complete_pass"
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
    d7_report_path = resolve_d7_report_path(workspace, args.d7_report_path)
    d7_report = load_json(d7_report_path)
    if d7_report.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "d7_prerequisite",
                "D8 requires a passing D7 retarget refine chains report.",
                d7_report_path=str(d7_report_path),
                d7_status=d7_report.get("status"),
            )
        )

    engine_evidence = dict(d7_report.get("engine_evidence") or {})
    fixed_execution_profile = dict(FIXED_EXECUTION_PROFILE)
    fixed_execution_profile["animation_asset_path"] = str(args.animation_asset_path or d7_report.get("fixed_execution_profile", {}).get("animation_asset_path") or DEFAULT_ANIMATION_ASSET_PATH)
    fixed_execution_profile["retarget_source_ik_rig_asset_path"] = engine_evidence.get("target_ik_rig_asset_path")
    fixed_execution_profile["retarget_target_ik_rig_asset_path"] = engine_evidence.get("source_ik_rig_asset_path")
    fixed_execution_profile["retarget_source_mesh_asset_path"] = engine_evidence.get("target_ik_rig_profile", {}).get("skeletal_mesh_asset_path")
    fixed_execution_profile["retarget_target_mesh_asset_path"] = engine_evidence.get("source_ik_rig_profile", {}).get("skeletal_mesh_asset_path")
    fixed_execution_profile["pose_probe_bone_names"] = pose_probe_bone_names_from_d7_report(d7_report)

    action_result_path = output_root / "retargeted_animation_preview_result.json"
    host_result = {}
    host_invocation_error = None
    if not failed_requirements:
        try:
            host_payload = run_host_auto_ue_cli(
                workspace_or_config=workspace,
                mode=REQUIRED_MODE,
                command="animation-preview",
                params={
                    "package_id": d7_report.get("package_id"),
                    "sample_id": d7_report.get("sample_id"),
                    "host_blueprint_asset_path": d7_report.get("host_blueprint_asset"),
                    "level_path": str(d7_report.get("fixed_execution_profile", {}).get("level_path") or DEFAULT_LEVEL_PATH),
                    "location": {"x": 0.0, "y": 0.0, "z": 120.0},
                    "rotation": {"pitch": 0.0, "yaw": 180.0, "roll": 0.0},
                    "output_root": str((output_root / "captures").resolve()),
                    "shot_order": list(SHOT_ORDER),
                    "capture_width": FIXED_EXECUTION_PROFILE["capture_width"],
                    "capture_height": FIXED_EXECUTION_PROFILE["capture_height"],
                    "capture_delay_seconds": FIXED_EXECUTION_PROFILE["capture_delay_seconds"],
                    "subject_min_screen_coverage": FIXED_EXECUTION_PROFILE["subject_min_screen_coverage"],
                    "weapon_min_screen_coverage": FIXED_EXECUTION_PROFILE["weapon_min_screen_coverage"],
                    "animation_asset_path": fixed_execution_profile["animation_asset_path"],
                    "animation_sample_time_seconds": FIXED_EXECUTION_PROFILE["animation_sample_time_seconds"],
                    "animation_settle_seconds": FIXED_EXECUTION_PROFILE["animation_settle_seconds"],
                    "retarget_if_needed": True,
                    "retarget_source_ik_rig_asset_path": fixed_execution_profile["retarget_source_ik_rig_asset_path"],
                    "retarget_target_ik_rig_asset_path": fixed_execution_profile["retarget_target_ik_rig_asset_path"],
                    "retarget_source_mesh_asset_path": fixed_execution_profile["retarget_source_mesh_asset_path"],
                    "retarget_target_mesh_asset_path": fixed_execution_profile["retarget_target_mesh_asset_path"],
                    "pose_probe_bone_names": list(fixed_execution_profile["pose_probe_bone_names"]),
                },
                output_path=str(action_result_path.resolve()),
                host_key=DEMO_HOST_KEY,
            )
            host_result = dict((host_payload.get("payload") or {}).get("result") or {})
        except Exception as exc:
            host_invocation_error = str(exc)
            if action_result_path.exists():
                payload = load_json(action_result_path)
                host_result = dict(payload.get("result") or {})

    if not failed_requirements and host_result.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "retargeted_animation_preview_host",
                "The demo host retargeted animation preview command did not complete successfully.",
                host_invocation_error=host_invocation_error,
                host_errors=list(host_result.get("errors") or []),
                result_path=str(action_result_path.resolve()),
            )
        )

    direct_compatibility = dict(host_result.get("direct_animation_compatibility") or {})
    resolved_compatibility = dict(host_result.get("animation_compatibility") or {})
    retarget_generation = dict(host_result.get("retarget_generation") or {})
    if not failed_requirements:
        if not bool(retarget_generation.get("attempted")):
            failed_requirements.append(
                make_failed_requirement(
                    "retarget_generation_not_attempted",
                    "D8 expected the host preview path to attempt retarget generation when direct skeleton compatibility was absent.",
                    direct_animation_compatibility=direct_compatibility,
                )
            )
        if not bool(retarget_generation.get("success")):
            failed_requirements.append(
                make_failed_requirement(
                    "retarget_generation_failed",
                    "D8 did not successfully generate a retargeted animation asset for the PMX target mesh.",
                    retarget_generation=retarget_generation,
                )
            )
        if not bool(resolved_compatibility.get("compatible")):
            failed_requirements.append(
                make_failed_requirement(
                    "retargeted_animation_incompatible",
                    "The resolved animation asset is still not compatible with the PMX character after retarget generation.",
                    animation_compatibility=resolved_compatibility,
                    retarget_generation=retarget_generation,
                )
            )

    shots = list(host_result.get("shots") or [])
    passing_engine_shots = sum(1 for shot in shots if shot.get("status") == "pass")
    if not failed_requirements and passing_engine_shots < 1:
        failed_requirements.append(
            make_failed_requirement(
                "engine_motion_preview_missing",
                "At least one retargeted animation preview shot must pass inside the demo host.",
                passing_engine_shots=passing_engine_shots,
                total_shots=len(shots),
            )
        )

    external_motion_evidence = []
    external_motion_failures = []
    if shots:
        external_motion_evidence, external_motion_failures = evaluate_external_motion(repo_root, shots)
    failed_requirements.extend(external_motion_failures)

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(status, failed_requirements, previous_report, previous_report_path)
    counts = {
        "requested_packages": 1,
        "resolved_packages": 1 if d7_report.get("package_id") else 0,
        "captured_shot_pairs": len(shots),
        "passing_engine_shots": passing_engine_shots,
        "passing_external_motion_shots": sum(1 for shot in external_motion_evidence if shot.get("status") == "pass"),
    }
    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": args.workspace_config,
            "host_key": DEMO_HOST_KEY,
            "level_path": str(d7_report.get("fixed_execution_profile", {}).get("level_path") or DEFAULT_LEVEL_PATH),
            "package_id": d7_report.get("package_id"),
            "sample_id": d7_report.get("sample_id"),
            "host_blueprint_asset": d7_report.get("host_blueprint_asset"),
            "fixed_execution_profile": fixed_execution_profile,
            "counts": counts,
            "failed_requirements": failed_requirements,
            "engine_evidence": host_result,
            "external_motion_evidence": external_motion_evidence,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "d7_report_path": str(d7_report_path.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
                "retargeted_animation_preview_result_path": str(action_result_path.resolve()),
            },
        },
        "aiue_demo_retargeted_animation_preview_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_demo_retargeted_animation_preview_report",
            notes=["internal_demo_retargeted_animation_preview_gate", "demo_host_only", "retargeted_animation_asset_evidence"],
        ),
    )
    report_path = output_root / "d8_demo_retargeted_animation_preview_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    print(f"D8 demo retargeted animation preview report written to: {report_path}")
    raise SystemExit(0 if status == "pass" else 1)


if __name__ == "__main__":
    main()
