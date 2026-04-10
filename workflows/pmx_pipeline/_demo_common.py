from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from aiue_core.schema_utils import load_json
from aiue_unreal.host_bridge import run_host_auto_ue_cli

from _gate_common import make_failed_requirement, verification_named_report_path


def default_named_verification_report_path(workspace: dict, repo_root_fallback: str | Path, report_name: str) -> Path:
    return verification_named_report_path(workspace, repo_root_fallback, report_name)


def resolve_report_path(explicit_path: str | None, fallback_path: Path, missing_message: str) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Report path does not exist: {candidate}")
    if fallback_path.exists():
        return fallback_path
    raise FileNotFoundError(missing_message)


def extract_quality_subject_report(source_report: dict, source_report_path: Path) -> tuple[dict, dict]:
    gate_id = str(source_report.get("gate_id") or "")
    if gate_id == "demo_cross_bundle_regression_d12" and isinstance(source_report.get("final_step_report"), dict):
        final_step_report = dict(source_report.get("final_step_report") or {})
        return final_step_report, {
            "source_report_kind": "d12_final_step_report",
            "source_gate_id": gate_id,
            "source_report_path": str(source_report_path.resolve()),
            "source_package_id": source_report.get("secondary_package_id"),
        }
    return source_report, {
        "source_report_kind": "direct_d11_report",
        "source_gate_id": gate_id,
        "source_report_path": str(source_report_path.resolve()),
        "source_package_id": source_report.get("package_id"),
    }


def animation_label(animation_asset_path: str) -> str:
    asset_name = str(animation_asset_path or "").strip().split("/")[-1]
    if "." in asset_name:
        asset_name = asset_name.split(".", 1)[0]
    sanitized = re.sub(r"[^A-Za-z0-9_]+", "_", asset_name).strip("_")
    return sanitized or "animation"


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


def crop_rect_for_shot(shot: dict, capture_width: int, capture_height: int) -> dict | None:
    rectangles = []
    for phase_key in ("before", "after"):
        phase = dict(shot.get(phase_key) or {})
        for coverage_key in ("subject_coverage", "weapon_coverage"):
            rect = normalized_screen_rect(dict(phase.get(coverage_key) or {}).get("screen_rect"))
            if rect:
                rectangles.append(rect)
    return merged_crop_rect(rectangles, image_width=capture_width, image_height=capture_height)


def evaluate_external_motion(
    repo_root: Path,
    shots: list[dict],
    capture_width: int,
    capture_height: int,
    histogram_l1_threshold: float,
    mean_abs_pixel_delta_threshold: float,
) -> tuple[list[dict], int]:
    evaluated = []
    motion_pass_count = 0
    compare_script_path = repo_root / "tools" / "compare_image_motion.ps1"
    for shot in shots:
        before = dict(shot.get("before") or {})
        after = dict(shot.get("after") or {})
        before_path = str(before.get("image_path") or "")
        after_path = str(after.get("image_path") or "")
        metrics = None
        errors = []
        crop_rect = crop_rect_for_shot(shot, capture_width=capture_width, capture_height=capture_height)
        if before_path and after_path and Path(before_path).exists() and Path(after_path).exists():
            try:
                metrics = subprocess_compare_image_motion(compare_script_path, before_path, after_path, crop_rect)
            except Exception as exc:
                errors.append(f"motion_compare_failed:{exc}")
        else:
            errors.append("before_or_after_image_missing")

        histogram_l1 = float((metrics or {}).get("histogram_l1") or 0.0)
        mean_abs_pixel_delta = float((metrics or {}).get("mean_abs_pixel_delta") or 0.0)
        motion_pass = bool(
            not errors
            and (
                histogram_l1 >= histogram_l1_threshold
                or mean_abs_pixel_delta >= mean_abs_pixel_delta_threshold
            )
        )
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
                    "histogram_l1_threshold": histogram_l1_threshold,
                    "mean_abs_pixel_delta_threshold": mean_abs_pixel_delta_threshold,
                },
                "status": "pass" if motion_pass else "fail",
                "errors": errors,
                "metrics": metrics or {},
                "crop_rect": crop_rect,
            }
        )
    return evaluated, motion_pass_count


def run_animation_preview(
    *,
    workspace: dict,
    output_root: Path,
    d8_report: dict,
    fixed_execution_profile: dict,
    animation_asset_path: str,
    host_key: str,
    mode: str,
    spawn_location: dict,
    spawn_rotation: dict,
    result_name: str = "retargeted_animation_preview_result.json",
) -> tuple[dict, str | None, Path]:
    animation_dir = output_root / f"{len(list(output_root.glob('*'))) + 1:03d}_{animation_label(animation_asset_path)}"
    animation_dir.mkdir(parents=True, exist_ok=True)
    result_path = animation_dir / result_name
    host_result = {}
    host_invocation_error = None
    try:
        host_payload = run_host_auto_ue_cli(
            workspace_or_config=workspace,
            mode=mode,
            command="animation-preview",
            params={
                "package_id": d8_report.get("package_id"),
                "sample_id": d8_report.get("sample_id"),
                "host_blueprint_asset_path": d8_report.get("host_blueprint_asset"),
                "level_path": str(d8_report.get("level_path") or fixed_execution_profile["level_path"]),
                "location": dict(spawn_location),
                "rotation": dict(spawn_rotation),
                "output_root": str((animation_dir / "captures").resolve()),
                "shot_order": list(fixed_execution_profile["shot_order"]),
                "capture_width": fixed_execution_profile["capture_width"],
                "capture_height": fixed_execution_profile["capture_height"],
                "capture_delay_seconds": fixed_execution_profile["capture_delay_seconds"],
                "subject_min_screen_coverage": fixed_execution_profile["subject_min_screen_coverage"],
                "weapon_min_screen_coverage": fixed_execution_profile["weapon_min_screen_coverage"],
                "animation_asset_path": animation_asset_path,
                "animation_sample_time_seconds": fixed_execution_profile["animation_sample_time_seconds"],
                "animation_settle_seconds": fixed_execution_profile["animation_settle_seconds"],
                "retarget_if_needed": True,
                "retarget_source_ik_rig_asset_path": fixed_execution_profile["retarget_source_ik_rig_asset_path"],
                "retarget_target_ik_rig_asset_path": fixed_execution_profile["retarget_target_ik_rig_asset_path"],
                "retarget_source_mesh_asset_path": fixed_execution_profile["retarget_source_mesh_asset_path"],
                "retarget_target_mesh_asset_path": fixed_execution_profile["retarget_target_mesh_asset_path"],
                "pose_probe_bone_names": list(fixed_execution_profile["pose_probe_bone_names"]),
            },
            output_path=str(result_path.resolve()),
            host_key=host_key,
        )
        host_result = dict((host_payload.get("payload") or {}).get("result") or {})
    except Exception as exc:
        host_invocation_error = str(exc)
        if result_path.exists():
            payload = load_json(result_path)
            host_result = dict(payload.get("result") or {})
    return host_result, host_invocation_error, result_path


def evaluate_animation_result(
    *,
    repo_root: Path,
    animation_asset_path: str,
    host_result: dict,
    host_invocation_error: str | None,
    result_path: Path,
    fixed_execution_profile: dict,
    required_engine_pass_key: str,
    required_external_motion_key: str,
    host_failure_id: str,
    host_failure_message: str,
) -> dict:
    failed_requirements = []
    if host_result.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                host_failure_id,
                host_failure_message,
                host_invocation_error=host_invocation_error,
                host_errors=list(host_result.get("errors") or []),
                result_path=str(result_path.resolve()),
            )
        )

    direct_compatibility = dict(host_result.get("direct_animation_compatibility") or {})
    resolved_compatibility = dict(host_result.get("animation_compatibility") or {})
    retarget_generation = dict(host_result.get("retarget_generation") or {})
    if not bool(retarget_generation.get("attempted")):
        failed_requirements.append(
            make_failed_requirement(
                "retarget_generation_not_attempted",
                "The preview path did not attempt retarget generation when direct skeleton compatibility was absent.",
                direct_animation_compatibility=direct_compatibility,
            )
        )
    if not bool(retarget_generation.get("success")):
        failed_requirements.append(
            make_failed_requirement(
                "retarget_generation_failed",
                "The preview path did not successfully generate or resolve a retargeted animation asset.",
                retarget_generation=retarget_generation,
            )
        )
    if not bool(resolved_compatibility.get("compatible")):
        failed_requirements.append(
            make_failed_requirement(
                "retargeted_animation_incompatible",
                "The resolved animation asset is not compatible with the PMX character for this preview.",
                animation_compatibility=resolved_compatibility,
                retarget_generation=retarget_generation,
            )
        )

    shots = list(host_result.get("shots") or [])
    passing_engine_shots = sum(1 for shot in shots if shot.get("status") == "pass")
    required_engine_passes = int(fixed_execution_profile[required_engine_pass_key])
    if passing_engine_shots < required_engine_passes:
        failed_requirements.append(
            make_failed_requirement(
                "engine_motion_preview_missing",
                "This animation did not produce enough passing engine-side preview shots.",
                required_passing_engine_shots=required_engine_passes,
                actual_passing_engine_shots=passing_engine_shots,
                total_shots=len(shots),
            )
        )

    external_motion_evidence, passing_external_motion_shots = evaluate_external_motion(
        repo_root,
        shots,
        capture_width=int(fixed_execution_profile["capture_width"]),
        capture_height=int(fixed_execution_profile["capture_height"]),
        histogram_l1_threshold=float(fixed_execution_profile["histogram_l1_threshold"]),
        mean_abs_pixel_delta_threshold=float(fixed_execution_profile["mean_abs_pixel_delta_threshold"]),
    )
    required_external_passes = int(fixed_execution_profile[required_external_motion_key])
    if passing_external_motion_shots < required_external_passes:
        failed_requirements.append(
            make_failed_requirement(
                "external_motion_evidence",
                "This animation did not produce enough passing external motion evidence.",
                required_external_motion_shots=required_external_passes,
                actual_external_motion_shots=passing_external_motion_shots,
            )
        )

    native_pose = dict(host_result.get("native_animation_pose_evaluation") or {})
    pose_probe = dict(host_result.get("pose_probe_delta") or {})
    counts = {
        "captured_shot_pairs": len(shots),
        "passing_engine_shots": passing_engine_shots,
        "passing_external_motion_shots": passing_external_motion_shots,
        "native_changed_bone_count": int(native_pose.get("changed_bone_count") or 0),
        "moving_probe_bone_count": int(pose_probe.get("moving_bone_count") or 0),
    }
    return {
        "animation_asset_path": animation_asset_path,
        "animation_id": animation_label(animation_asset_path),
        "status": "pass" if not failed_requirements else "fail",
        "counts": counts,
        "resolved_animation_asset_path": host_result.get("resolved_animation_asset_path"),
        "retargeted_animation_asset_path": retarget_generation.get("retargeted_animation_asset_path"),
        "direct_animation_compatibility": direct_compatibility,
        "animation_compatibility": resolved_compatibility,
        "retarget_generation_summary": {
            "attempted": bool(retarget_generation.get("attempted")),
            "success": bool(retarget_generation.get("success")),
            "retargeter_asset_path": retarget_generation.get("retargeter_asset_path"),
            "retargeted_animation_asset_path": retarget_generation.get("retargeted_animation_asset_path"),
        },
        "native_animation_pose_evaluation": native_pose,
        "pose_probe_delta": pose_probe,
        "shots": shots,
        "external_motion_evidence": external_motion_evidence,
        "failed_requirements": failed_requirements,
        "warnings": list(host_result.get("warnings") or []),
        "errors": list(host_result.get("errors") or []),
        "artifacts": {
            "result_path": str(result_path.resolve()),
        },
    }
