from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _demo_common import default_named_verification_report_path, resolve_report_path, run_host_command_result, subprocess_compare_image_motion
from _gate_common import (
    build_discussion_signal,
    default_latest_report_path,
    default_output_root,
    make_failed_requirement,
    now_utc,
    write_report_pair,
)

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config

GATE_ID = "live_fx_visual_quality_r3"
DEFAULT_R2_LATEST_NAME = "latest_real_fx_item_kind_r2_report.json"
DEFAULT_FX_SLOT_NAME = "fx"
DEFAULT_R3_FX_FIXTURE_ASSET = "/Niagara/DefaultAssets/Templates/Systems/DirectionalBurst.DirectionalBurst"
FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "strict_shot_ids": ["front", "side"],
    "capture_width": 1280,
    "capture_height": 720,
    "scene_capture_source": "SCS_FINAL_COLOR_HDR",
    "scene_capture_warmup_count": 4,
    "scene_capture_warmup_delay_seconds": 0.08,
    "tracked_fx_min_coverage": 0.03,
    "crop_histogram_l1_threshold": 0.0025,
    "crop_mean_abs_pixel_delta_threshold": 0.001,
    "full_frame_histogram_l1_threshold": 0.001,
    "full_frame_mean_abs_pixel_delta_threshold": 0.00035,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE R3 live FX visual quality gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--r2-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    parser.add_argument("--fx-slot-name", default=DEFAULT_FX_SLOT_NAME)
    parser.add_argument("--fx-asset-path", default=DEFAULT_R3_FX_FIXTURE_ASSET)
    parser.add_argument("--fx-attach-socket-name", default="")
    parser.add_argument("--tracked-fx-min-coverage", type=float, default=float(FIXED_EXECUTION_PROFILE["tracked_fx_min_coverage"]))
    parser.add_argument("--crop-histogram-l1-threshold", type=float, default=float(FIXED_EXECUTION_PROFILE["crop_histogram_l1_threshold"]))
    parser.add_argument("--crop-mean-abs-pixel-delta-threshold", type=float, default=float(FIXED_EXECUTION_PROFILE["crop_mean_abs_pixel_delta_threshold"]))
    parser.add_argument("--full-frame-histogram-l1-threshold", type=float, default=float(FIXED_EXECUTION_PROFILE["full_frame_histogram_l1_threshold"]))
    parser.add_argument("--full-frame-mean-abs-pixel-delta-threshold", type=float, default=float(FIXED_EXECUTION_PROFILE["full_frame_mean_abs_pixel_delta_threshold"]))
    parser.add_argument("--niagara-desired-age-seconds", type=float, default=0.08)
    parser.add_argument("--niagara-seek-delta-seconds", type=float, default=1.0 / 60.0)
    parser.add_argument("--niagara-advance-step-count", type=int, default=4)
    parser.add_argument("--niagara-advance-step-delta-seconds", type=float, default=1.0 / 60.0)
    parser.add_argument("--scene-capture-source", default=str(FIXED_EXECUTION_PROFILE["scene_capture_source"]))
    parser.add_argument("--scene-capture-warmup-count", type=int, default=int(FIXED_EXECUTION_PROFILE["scene_capture_warmup_count"]))
    parser.add_argument("--scene-capture-warmup-delay-seconds", type=float, default=float(FIXED_EXECUTION_PROFILE["scene_capture_warmup_delay_seconds"]))
    return parser.parse_args()


def default_latest_r2_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_R2_LATEST_NAME)


def normalize_asset_path(asset_path: str | None) -> str:
    text = str(asset_path or "").strip()
    if not text:
        return ""
    if "." not in text:
        return text
    package_path, object_name = text.rsplit(".", 1)
    leaf_name = package_path.rsplit("/", 1)[-1]
    if object_name == leaf_name:
        return package_path
    return text


def ready_runtime_checks(r2_report: dict) -> list[dict]:
    results = []
    runtime_checks = list(r2_report.get("runtime_checks") or [])
    visual_checks = {str(item.get("package_id") or ""): dict(item) for item in list(r2_report.get("visual_checks") or [])}
    for runtime_check in runtime_checks:
        package_id = str(runtime_check.get("package_id") or "")
        if runtime_check.get("status") != "pass" or not package_id:
            continue
        if package_id not in visual_checks or visual_checks[package_id].get("status") != "pass":
            continue
        results.append(
            {
                "package_id": package_id,
                "sample_id": str(runtime_check.get("sample_id") or ""),
                "host_blueprint_asset_path": str(runtime_check.get("host_blueprint_asset") or ""),
                "runtime_check": dict(runtime_check),
                "source_visual_check": visual_checks[package_id],
            }
        )
    return sorted(results, key=lambda item: item["package_id"])


def fx_binding_from_runtime_check(runtime_check: dict, fx_slot_name: str, fx_asset_path: str, fx_attach_socket_name: str) -> dict:
    fx_binding = dict(runtime_check.get("fx_binding") or {})
    return {
        "slot_name": str(fx_binding.get("slot_name") or fx_slot_name or DEFAULT_FX_SLOT_NAME),
        "item_package_id": str(fx_binding.get("item_package_id") or "r3_runtime_binding"),
        "item_kind": str(fx_binding.get("item_kind") or "niagara_system"),
        "attach_socket_name": str(fx_attach_socket_name or fx_binding.get("attach_socket_name") or "WeaponSocket"),
        "niagara_system_asset": str(fx_asset_path or fx_binding.get("niagara_system_asset") or fx_binding.get("asset_path") or DEFAULT_R3_FX_FIXTURE_ASSET),
        "consumer_ready": bool(fx_binding.get("consumer_ready", True)),
    }


def inspect_visual(
    workspace: dict,
    output_root: Path,
    host_key: str,
    package: dict,
    level_path: str,
    tracked_slot_name: str,
    binding_override: dict | None,
    label_suffix: str,
    args,
) -> tuple[dict, Path]:
    result_path = output_root / f"{package['package_id']}_{label_suffix}.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    shot_results = []
    raw_result_files = []
    shot_ids = list(FIXED_EXECUTION_PROFILE["strict_shot_ids"])

    for shot_id in shot_ids:
        shot_result_path = output_root / f"{package['package_id']}_{label_suffix}_{shot_id}.json"
        shot_capture_root = output_root.parent / f"{package['package_id']}_{label_suffix}_{shot_id}" / "captures"
        shot_capture_root.mkdir(parents=True, exist_ok=True)
        params = {
            "package_id": package["package_id"],
            "sample_id": package["sample_id"],
            "host_blueprint_asset_path": package["host_blueprint_asset_path"],
            "level_path": level_path,
            "output_root": str(shot_capture_root.resolve()),
            "tracked_slots": [tracked_slot_name],
            "requested_shot_ids": [shot_id],
        }
        if binding_override:
            params["slot_binding_overrides"] = [binding_override]
            params["niagara_desired_age_seconds"] = float(binding_override.get("niagara_desired_age_seconds") or 0.08)
            params["niagara_seek_delta_seconds"] = float(binding_override.get("niagara_seek_delta_seconds") or (1.0 / 60.0))
            params["niagara_advance_step_count"] = int(binding_override.get("niagara_advance_step_count") or 4)
            params["niagara_advance_step_delta_seconds"] = float(binding_override.get("niagara_advance_step_delta_seconds") or (1.0 / 60.0))
        if str(args.scene_capture_source or "").strip():
            params["scene_capture_source"] = str(args.scene_capture_source).strip()
        params["scene_capture_warmup_count"] = int(args.scene_capture_warmup_count)
        params["scene_capture_warmup_delay_seconds"] = float(args.scene_capture_warmup_delay_seconds)
        shot_result, _, resolved_result_path = run_host_command_result(
            workspace=workspace,
            mode="editor_rendered",
            command="inspect-host-visual",
            params=params,
            output_path=shot_result_path,
            host_key=host_key,
        )
        shot_results.append(shot_result)
        raw_result_files.append(str(resolved_result_path.resolve()))

    merged = dict(shot_results[0] if shot_results else {})
    merged["shots"] = [
        dict((next((item for item in shot_results if any(str(shot.get("shot_id") or "") == shot_id for shot in list(item.get("shots") or []))), {})).get("shots", [{}])[0])
        for shot_id in shot_ids
    ]
    merged["warnings"] = sorted({warning for item in shot_results for warning in list(item.get("warnings") or [])})
    merged["errors"] = sorted({error for item in shot_results for error in list(item.get("errors") or [])})
    merged["failed_requirements"] = sorted({failure for item in shot_results for failure in list(item.get("failed_requirements") or [])})
    merged["status"] = "pass" if shot_results and all(item.get("status") == "pass" for item in shot_results) else "fail"
    merged["artifacts"] = {"raw_result_paths": raw_result_files}
    result_path.write_text(json.dumps({"result": merged}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return merged, result_path


def inspect_visual_pair(
    workspace: dict,
    output_root: Path,
    host_key: str,
    package: dict,
    level_path: str,
    tracked_slot_name: str,
    binding_override: dict | None,
    args,
) -> tuple[dict, Path]:
    result_path = output_root / f"{package['package_id']}_pair.json"
    pair_capture_root = output_root / package["package_id"]
    params = {
        "package_id": package["package_id"],
        "sample_id": package["sample_id"],
        "host_blueprint_asset_path": package["host_blueprint_asset_path"],
        "level_path": level_path,
        "output_root": str(pair_capture_root.resolve()),
        "tracked_slots": [tracked_slot_name],
        "requested_shot_ids": list(FIXED_EXECUTION_PROFILE["strict_shot_ids"]),
    }
    if binding_override:
        params["slot_binding_overrides"] = [binding_override]
        params["niagara_desired_age_seconds"] = float(binding_override.get("niagara_desired_age_seconds") or 0.08)
        params["niagara_seek_delta_seconds"] = float(binding_override.get("niagara_seek_delta_seconds") or (1.0 / 60.0))
        params["niagara_advance_step_count"] = int(binding_override.get("niagara_advance_step_count") or 4)
        params["niagara_advance_step_delta_seconds"] = float(binding_override.get("niagara_advance_step_delta_seconds") or (1.0 / 60.0))
    if str(args.scene_capture_source or "").strip():
        params["scene_capture_source"] = str(args.scene_capture_source).strip()
    params["scene_capture_warmup_count"] = int(args.scene_capture_warmup_count)
    params["scene_capture_warmup_delay_seconds"] = float(args.scene_capture_warmup_delay_seconds)
    result, _, resolved_result_path = run_host_command_result(
        workspace=workspace,
        mode="editor_rendered",
        command="inspect-live-fx-visual-pair",
        params=params,
        output_path=result_path,
        host_key=host_key,
    )
    return result, resolved_result_path


def shot_lookup(report: dict) -> dict[str, dict]:
    return {str(shot.get("shot_id") or ""): dict(shot) for shot in list(report.get("shots") or [])}


def crop_rect_from_fx_shot(shot: dict, slot_name: str) -> dict | None:
    tracked = dict(((shot.get("tracked_slot_coverages") or {}).get(slot_name) or {}))
    rect = dict(tracked.get("screen_rect") or {})
    try:
        min_x = float(rect["min_x"])
        max_x = float(rect["max_x"])
        min_y = float(rect["min_y"])
        max_y = float(rect["max_y"])
    except Exception:
        return None
    width = max_x - min_x
    height = max_y - min_y
    if width <= 1 or height <= 1:
        return None
    pad_x = max(24.0, width * 0.12)
    pad_y = max(24.0, height * 0.12)
    return {
        "x": max(0.0, min_x - pad_x),
        "y": max(0.0, min_y - pad_y),
        "width": width + (pad_x * 2.0),
        "height": height + (pad_y * 2.0),
    }


def compare_motion(compare_script_path: Path, before_path: str, after_path: str, crop_rect: dict | None) -> dict:
    if not before_path or not after_path:
        return {}
    before_file = Path(before_path)
    after_file = Path(after_path)
    if not before_file.exists() or not after_file.exists():
        return {}
    return subprocess_compare_image_motion(compare_script_path, before_path, after_path, crop_rect)


def evaluate_shot(
    package_id: str,
    shot_id: str,
    baseline_shot: dict,
    with_fx_shot: dict,
    slot_name: str,
    compare_script_path: Path,
    args,
) -> tuple[dict, list[dict]]:
    failed_requirements = []
    fx_coverage = float((((with_fx_shot.get("tracked_slot_coverages") or {}).get(slot_name) or {}).get("coverage_ratio") or 0.0))
    crop_rect = crop_rect_from_fx_shot(with_fx_shot, slot_name)
    crop_metrics = compare_motion(compare_script_path, str(baseline_shot.get("image_path") or ""), str(with_fx_shot.get("image_path") or ""), crop_rect)
    full_frame_metrics = compare_motion(compare_script_path, str(baseline_shot.get("image_path") or ""), str(with_fx_shot.get("image_path") or ""), None)

    crop_histogram_l1 = float(crop_metrics.get("histogram_l1") or 0.0)
    crop_mean_abs_pixel_delta = float(crop_metrics.get("mean_abs_pixel_delta") or 0.0)
    full_frame_histogram_l1 = float(full_frame_metrics.get("histogram_l1") or 0.0)
    full_frame_mean_abs_pixel_delta = float(full_frame_metrics.get("mean_abs_pixel_delta") or 0.0)

    crop_pass = bool(
        crop_metrics
        and (
            crop_histogram_l1 >= float(args.crop_histogram_l1_threshold)
            or crop_mean_abs_pixel_delta >= float(args.crop_mean_abs_pixel_delta_threshold)
        )
    )
    full_frame_pass = bool(
        full_frame_metrics
        and (
            full_frame_histogram_l1 >= float(args.full_frame_histogram_l1_threshold)
            or full_frame_mean_abs_pixel_delta >= float(args.full_frame_mean_abs_pixel_delta_threshold)
        )
    )
    shot_pass = bool(
        baseline_shot.get("status") == "pass"
        and with_fx_shot.get("status") == "pass"
        and fx_coverage >= float(args.tracked_fx_min_coverage)
        and (crop_pass or full_frame_pass)
    )

    if baseline_shot.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "r3_baseline_shot_failed",
                "The baseline shot did not pass the underlying visual proof.",
                package_id=package_id,
                shot_id=shot_id,
            )
        )
    if with_fx_shot.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "r3_fx_shot_failed",
                "The FX-enabled shot did not pass the underlying visual proof.",
                package_id=package_id,
                shot_id=shot_id,
            )
        )
    if fx_coverage < float(args.tracked_fx_min_coverage):
        failed_requirements.append(
            make_failed_requirement(
                "r3_fx_spatial_coverage_insufficient",
                "The FX-enabled shot did not preserve enough spatial FX coverage to support a live-pixel quality check.",
                package_id=package_id,
                shot_id=shot_id,
                fx_screen_coverage=fx_coverage,
                minimum=float(args.tracked_fx_min_coverage),
            )
        )
    if not shot_pass:
        failed_requirements.append(
            make_failed_requirement(
                "r3_live_fx_pixels_missing",
                "The FX-enabled shot did not produce a measurable live-pixel delta against the no-FX baseline.",
                package_id=package_id,
                shot_id=shot_id,
                crop_histogram_l1=crop_histogram_l1,
                crop_mean_abs_pixel_delta=crop_mean_abs_pixel_delta,
                full_frame_histogram_l1=full_frame_histogram_l1,
                full_frame_mean_abs_pixel_delta=full_frame_mean_abs_pixel_delta,
            )
        )

    return (
        {
            "shot_id": shot_id,
            "status": "pass" if shot_pass else "fail",
            "baseline_image_path": str(baseline_shot.get("image_path") or ""),
            "with_fx_image_path": str(with_fx_shot.get("image_path") or ""),
            "fx_screen_coverage": fx_coverage,
            "crop_rect": crop_rect,
            "crop_metrics": crop_metrics,
            "full_frame_metrics": full_frame_metrics,
            "pixel_delta_pass": crop_pass or full_frame_pass,
            "crop_pass": crop_pass,
            "full_frame_pass": full_frame_pass,
        },
        failed_requirements,
    )


def evaluate_package(
    package: dict,
    pair_result: dict,
    pair_path: Path,
    binding: dict,
    args,
) -> tuple[dict, list[dict]]:
    package_id = str(package.get("package_id") or "")
    failed_requirements = []
    compare_script_path = REPO_ROOT / "tools" / "compare_image_motion.ps1"
    baseline_result = dict(pair_result.get("baseline_result") or {})
    with_fx_result = dict(pair_result.get("with_fx_result") or {})
    pair_artifacts = dict(pair_result.get("artifacts") or {})
    baseline_path = Path(str(pair_artifacts.get("baseline_result_path") or pair_path))
    with_fx_path = Path(str(pair_artifacts.get("with_fx_result_path") or pair_path))
    baseline_shots = shot_lookup(baseline_result)
    with_fx_shots = shot_lookup(with_fx_result)
    runtime_check = dict(package.get("runtime_check") or {})
    source_visual_check = dict(package.get("source_visual_check") or {})
    expected_asset_path = normalize_asset_path(binding.get("niagara_system_asset"))
    source_fx_component = dict(source_visual_check.get("fx_component") or {})
    with_fx_component = dict((with_fx_result.get("managed_components_by_slot") or {}).get(binding["slot_name"]) or {})
    shot_results = []

    if runtime_check.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "r3_runtime_prerequisite_failed",
                "R3 requires the source R2 runtime check to pass.",
                package_id=package_id,
            )
        )
    if source_visual_check.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "r3_source_visual_prerequisite_failed",
                "R3 requires the source R2 visual check to pass.",
                package_id=package_id,
            )
        )
    if baseline_result.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "r3_baseline_visual_failed",
                "R3 requires a passing no-FX baseline visual proof.",
                package_id=package_id,
                result_path=str(baseline_path.resolve()),
                errors=list(baseline_result.get("errors") or []),
            )
        )
    if with_fx_result.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "r3_with_fx_visual_failed",
                "R3 requires a passing FX-enabled visual proof before evaluating live-pixel prominence.",
                package_id=package_id,
                result_path=str(with_fx_path.resolve()),
                errors=list(with_fx_result.get("errors") or []),
            )
        )
    if normalize_asset_path(with_fx_component.get("asset_path")) != expected_asset_path:
        failed_requirements.append(
            make_failed_requirement(
                "r3_with_fx_component_asset_mismatch",
                "The FX-enabled R3 capture did not preserve the expected Niagara asset on the managed FX component.",
                package_id=package_id,
                expected_asset_path=expected_asset_path,
                actual_asset_path=with_fx_component.get("asset_path"),
            )
        )

    for shot_id in list(FIXED_EXECUTION_PROFILE["strict_shot_ids"]):
        baseline_shot = dict(baseline_shots.get(shot_id) or {})
        with_fx_shot = dict(with_fx_shots.get(shot_id) or {})
        if not baseline_shot or not with_fx_shot:
            failed_requirements.append(
                make_failed_requirement(
                    "r3_required_shot_missing",
                    "R3 requires matching baseline and FX-enabled shots for each strict shot id.",
                    package_id=package_id,
                    shot_id=shot_id,
                )
            )
            continue
        shot_payload, shot_failures = evaluate_shot(
            package_id,
            shot_id,
            baseline_shot,
            with_fx_shot,
            binding["slot_name"],
            compare_script_path,
            args,
        )
        shot_results.append(shot_payload)
        failed_requirements.extend(shot_failures)

    return (
        {
            "package_id": package_id,
            "sample_id": package.get("sample_id"),
            "status": "pass" if not failed_requirements else "fail",
            "host_blueprint_asset": package.get("host_blueprint_asset_path"),
            "fx_binding": binding,
            "source_fx_component": source_fx_component,
            "with_fx_component": with_fx_component,
            "shot_results": shot_results,
            "artifacts": {
                "baseline_result_path": str(baseline_path.resolve()),
                "with_fx_result_path": str(with_fx_path.resolve()),
            },
        },
        failed_requirements,
    )


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict] = []
    r2_report_path = resolve_report_path(
        args.r2_report_path,
        default_latest_r2_report_path(workspace),
        "No latest_real_fx_item_kind_r2_report.json could be resolved for R3.",
    )
    r2_report = load_json(r2_report_path)
    if r2_report.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "r3_source_prerequisite_failed",
                "R3 requires a passing R2 report.",
                r2_report_path=str(r2_report_path.resolve()),
                r2_status=r2_report.get("status"),
            )
        )

    host_key = str(r2_report.get("host_key") or FIXED_EXECUTION_PROFILE["host_key"])
    level_path = str(r2_report.get("level_path") or "/Game/Levels/DefaultLevel")
    packages = ready_runtime_checks(r2_report)
    if len(packages) != 2:
        failed_requirements.append(
            make_failed_requirement(
                "r3_ready_package_count",
                "R3 requires exactly two ready packages from the latest R2 report.",
                expected=2,
                actual=len(packages),
                r2_report_path=str(r2_report_path.resolve()),
            )
        )

    per_package_results = []
    if not failed_requirements:
        pair_root = output_root / "pair_visuals"
        for package in packages:
            binding = fx_binding_from_runtime_check(package["runtime_check"], args.fx_slot_name, args.fx_asset_path, args.fx_attach_socket_name)
            binding["item_package_id"] = "r3_live_visual_fixture"
            binding["niagara_desired_age_seconds"] = float(args.niagara_desired_age_seconds)
            binding["niagara_seek_delta_seconds"] = float(args.niagara_seek_delta_seconds)
            binding["niagara_advance_step_count"] = int(args.niagara_advance_step_count)
            binding["niagara_advance_step_delta_seconds"] = float(args.niagara_advance_step_delta_seconds)
            try:
                pair_result, pair_path = inspect_visual_pair(
                    workspace,
                    pair_root,
                    host_key,
                    package,
                    level_path,
                    binding["slot_name"],
                    binding,
                    args,
                )
                package_result, package_failures = evaluate_package(
                    package,
                    pair_result,
                    pair_path,
                    binding,
                    args,
                )
                per_package_results.append(package_result)
                failed_requirements.extend(package_failures)
            except Exception as exc:
                failed_requirements.append(
                    make_failed_requirement(
                        "r3_package_execution_failed",
                        "R3 failed while comparing no-FX and FX-enabled visual proofs for a ready bundle.",
                        package_id=package.get("package_id"),
                        error=str(exc),
                    )
                )

    status = "pass" if not failed_requirements else "fail"
    counts = {
        "required_ready_packages": 2,
        "resolved_ready_packages": len(packages),
        "evaluated_packages": len(per_package_results),
        "passing_packages": sum(1 for item in per_package_results if item.get("status") == "pass"),
        "strict_shots_evaluated": sum(len(list(item.get("shot_results") or [])) for item in per_package_results),
        "strict_shots_with_pixel_delta": sum(
            1
            for item in per_package_results
            for shot in list(item.get("shot_results") or [])
            if shot.get("pixel_delta_pass")
        ),
    }
    discussion_signal = build_discussion_signal(status, failed_requirements, previous_report, previous_report_path, "r3_first_complete_pass")
    report = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "host_key": host_key,
            "level_path": level_path,
            "fixed_execution_profile": {
                **FIXED_EXECUTION_PROFILE,
                "host_key": host_key,
                "fx_slot_name": str(args.fx_slot_name),
                "fx_asset_path": str(args.fx_asset_path),
                "fx_attach_socket_name": str(args.fx_attach_socket_name or ""),
                "tracked_fx_min_coverage": float(args.tracked_fx_min_coverage),
                "crop_histogram_l1_threshold": float(args.crop_histogram_l1_threshold),
                "crop_mean_abs_pixel_delta_threshold": float(args.crop_mean_abs_pixel_delta_threshold),
                "full_frame_histogram_l1_threshold": float(args.full_frame_histogram_l1_threshold),
                "full_frame_mean_abs_pixel_delta_threshold": float(args.full_frame_mean_abs_pixel_delta_threshold),
                "niagara_desired_age_seconds": float(args.niagara_desired_age_seconds),
                "niagara_seek_delta_seconds": float(args.niagara_seek_delta_seconds),
                "niagara_advance_step_count": int(args.niagara_advance_step_count),
                "niagara_advance_step_delta_seconds": float(args.niagara_advance_step_delta_seconds),
                "scene_capture_source": str(args.scene_capture_source or ""),
                "scene_capture_warmup_count": int(args.scene_capture_warmup_count),
                "scene_capture_warmup_delay_seconds": float(args.scene_capture_warmup_delay_seconds),
            },
            "counts": counts,
            "failed_requirements": failed_requirements,
            "resolved_package_ids": [package.get("package_id") for package in packages],
            "source_report": {
                "r2_report_path": str(r2_report_path.resolve()),
                "gate_id": r2_report.get("gate_id"),
                "status": r2_report.get("status"),
            },
            "per_package_results": per_package_results,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
            },
        },
        schema_family="aiue_live_fx_visual_quality_report",
        compatibility=make_compatibility_block(
            schema_family="aiue_live_fx_visual_quality_report",
            notes=[
                "internal_r3_gate",
                "live_fx_pixel_delta_vs_baseline",
                "niagara_visual_prominence_check",
            ],
        ),
    )
    write_report_pair(report, output_root / f"{GATE_ID}.json", latest_report_path)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
