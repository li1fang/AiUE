from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()
T1_PYTHON_ROOT = REPO_ROOT / "tools" / "t1" / "python"
if str(T1_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(T1_PYTHON_ROOT))

from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, make_failed_requirement, now_utc, write_report_pair

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config
from aiue_t1.q5a_visible_conflict import analyze_visible_conflict
from aiue_unreal.host_bridge import run_host_auto_ue_cli

GATE_ID = "visible_conflict_inspection_q5a"
DEFAULT_P2_LATEST_NAME = "latest_clothing_vertical_slice_p2_report.json"
DEFAULT_LEVEL_PATH = "/Game/Levels/DefaultLevel"
DEFAULT_CLOTHING_ASSET_PATH = "/Game/Characters/Echo/Meshes/SKM_Echo_Hair.SKM_Echo_Hair"
DEFAULT_SLOT_NAME = "clothing"
DEFAULT_ATTACH_SOCKET_NAME = "Head"
DEFAULT_SHOT_IDS = ["front", "side"]
FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "level_path": DEFAULT_LEVEL_PATH,
    "slot_name": DEFAULT_SLOT_NAME,
    "attach_socket_name": DEFAULT_ATTACH_SOCKET_NAME,
    "clothing_asset_path": DEFAULT_CLOTHING_ASSET_PATH,
    "shot_ids": list(DEFAULT_SHOT_IDS),
    "scene_capture_source": "SCS_FINAL_COLOR_LDR",
    "capture_hdr": False,
    "capture_backend": "scene_capture_render_target",
    "capture_width": 1280,
    "capture_height": 720,
    "capture_profile": "qa_mask_skeletal_only",
    "camera_distance_scale": 0.8,
    "slot_mask_coverage_ratio_min": 0.001,
    "slot_core_pixels_min": 400,
    "slot_visible_ratio_in_core_min": 0.75,
    "body_intrusion_ratio_in_core_max": 0.05,
    "close_kernel_px": 9,
    "erode_kernel_px": 7,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE Q5A visible conflict inspection gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--p2-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    parser.add_argument("--level-path", default=DEFAULT_LEVEL_PATH)
    parser.add_argument("--clothing-asset-path", default=DEFAULT_CLOTHING_ASSET_PATH)
    parser.add_argument("--slot-name", default=DEFAULT_SLOT_NAME)
    parser.add_argument("--attach-socket-name", default=DEFAULT_ATTACH_SOCKET_NAME)
    return parser.parse_args()


def default_latest_p2_report_path(workspace: dict) -> Path:
    return Path(workspace["paths"]["aiue_repo_root"]).expanduser().resolve() / "Saved" / "verification" / DEFAULT_P2_LATEST_NAME


def resolve_report_path(explicit_path: str | None, fallback_path: Path, missing_message: str) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Report path does not exist: {candidate}")
    if fallback_path.exists():
        return fallback_path
    raise FileNotFoundError(missing_message)


def _normalize_binding(binding: dict | None, clothing_asset_path: str, attach_socket_name: str, slot_name: str) -> dict:
    payload = dict(binding or {})
    return {
        "slot_name": str(payload.get("slot_name") or slot_name or DEFAULT_SLOT_NAME),
        "item_package_id": str(payload.get("item_package_id") or "q5a_clothing_fixture"),
        "item_kind": str(payload.get("item_kind") or "skeletal_mesh"),
        "attach_socket_name": str(payload.get("attach_socket_name") or attach_socket_name or DEFAULT_ATTACH_SOCKET_NAME),
        "skeletal_mesh_asset": str(payload.get("skeletal_mesh_asset") or payload.get("asset_path") or clothing_asset_path or DEFAULT_CLOTHING_ASSET_PATH),
        "static_mesh_asset": str(payload.get("static_mesh_asset") or ""),
        "consumer_ready": bool(payload.get("consumer_ready", True)),
    }


def ready_p2_packages(p2_report: dict, *, clothing_asset_path: str, attach_socket_name: str, slot_name: str) -> list[dict]:
    runtime_checks = {
        str(item.get("package_id") or ""): dict(item)
        for item in list(p2_report.get("runtime_checks") or [])
        if item.get("status") == "pass" and item.get("package_id")
    }
    visual_checks = {
        str(item.get("package_id") or ""): dict(item)
        for item in list(p2_report.get("visual_checks") or [])
        if item.get("status") == "pass" and item.get("package_id")
    }
    results = []
    for package_id in sorted(set(runtime_checks) & set(visual_checks)):
        runtime_check = runtime_checks[package_id]
        results.append(
            {
                "package_id": package_id,
                "sample_id": str(runtime_check.get("sample_id") or ""),
                "host_blueprint_asset": str(runtime_check.get("host_blueprint_asset") or ""),
                "clothing_binding": _normalize_binding(runtime_check.get("clothing_binding"), clothing_asset_path, attach_socket_name, slot_name),
                "source_runtime_check": runtime_check,
                "source_visual_check": visual_checks[package_id],
            }
        )
    return results


def run_package_inspection(
    *,
    workspace: dict,
    output_root: Path,
    package: dict,
    level_path: str,
    slot_name: str,
) -> tuple[dict, Path]:
    result_path = output_root / "host_results" / f"{package['package_id']}.json"
    capture_root = output_root / "captures" / package["package_id"]
    result_path.parent.mkdir(parents=True, exist_ok=True)
    capture_root.mkdir(parents=True, exist_ok=True)
    host_payload = run_host_auto_ue_cli(
        workspace_or_config=workspace,
        mode=str(FIXED_EXECUTION_PROFILE["mode"]),
        command="inspect-visible-conflict",
        params={
            "package_id": package["package_id"],
            "sample_id": package["sample_id"],
            "host_blueprint_asset_path": package["host_blueprint_asset"],
            "level_path": level_path,
            "output_root": str(capture_root.resolve()),
            "slot_name": slot_name,
            "requested_shot_ids": list(DEFAULT_SHOT_IDS),
            "slot_binding_overrides": [dict(package["clothing_binding"])],
            "capture_profile": str(FIXED_EXECUTION_PROFILE["capture_profile"]),
            "capture_hdr": bool(FIXED_EXECUTION_PROFILE["capture_hdr"]),
            "capture_width": int(FIXED_EXECUTION_PROFILE["capture_width"]),
            "capture_height": int(FIXED_EXECUTION_PROFILE["capture_height"]),
            "scene_capture_source": str(FIXED_EXECUTION_PROFILE["scene_capture_source"]),
            "camera_distance_scale": float(FIXED_EXECUTION_PROFILE["camera_distance_scale"]),
        },
        output_path=str(result_path.resolve()),
        host_key=str(FIXED_EXECUTION_PROFILE["host_key"]),
    )
    return dict((host_payload.get("payload") or {}).get("result") or {}), result_path


def analyze_host_result(host_result: dict, *, output_root: Path) -> tuple[dict, list[dict]]:
    failed_requirements = []
    package_id = str(host_result.get("package_id") or "")
    shot_results = []
    mask_mode_counts = {
        "color_threshold": 0,
        "silhouette_fallback": 0,
        "unknown": 0,
    }
    for shot in list(host_result.get("shot_results") or []):
        shot_id = str(shot.get("shot_id") or "shot")
        artifacts = dict(shot.get("artifacts") or {})
        overlay_path = output_root / "analysis" / package_id / f"{shot_id}_debug_overlay.png"
        analysis = analyze_visible_conflict(
            body_only_image_path=artifacts.get("body_only_image_path"),
            slot_only_image_path=artifacts.get("slot_only_image_path"),
            combined_visible_image_path=artifacts.get("combined_visible_image_path"),
            debug_overlay_path=overlay_path,
            thresholds={
                "slot_mask_coverage_ratio_min": FIXED_EXECUTION_PROFILE["slot_mask_coverage_ratio_min"],
                "slot_core_pixels_min": FIXED_EXECUTION_PROFILE["slot_core_pixels_min"],
                "slot_visible_ratio_in_core_min": FIXED_EXECUTION_PROFILE["slot_visible_ratio_in_core_min"],
                "body_intrusion_ratio_in_core_max": FIXED_EXECUTION_PROFILE["body_intrusion_ratio_in_core_max"],
                "close_kernel_px": FIXED_EXECUTION_PROFILE["close_kernel_px"],
                "erode_kernel_px": FIXED_EXECUTION_PROFILE["erode_kernel_px"],
            },
        )
        shot_failed_requirements = []
        for error_id in list(shot.get("errors") or []):
            shot_failed_requirements.append(
                make_failed_requirement(
                    error_id,
                    "The host-side visible conflict capture pass failed before mask analysis completed.",
                    package_id=package_id,
                    shot_id=shot_id,
                )
            )
        for failure_id in list(analysis.get("failed_requirements") or []):
            shot_failed_requirements.append(
                make_failed_requirement(
                    failure_id,
                    "The Q5A visible-conflict analysis did not meet the fixed threshold for this shot.",
                    package_id=package_id,
                    shot_id=shot_id,
                    metrics=dict(analysis.get("metrics") or {}),
                )
            )
        if not str(analysis.get("debug_overlay_path") or "").strip():
            shot_failed_requirements.append(
                make_failed_requirement(
                    "debug_overlay_missing",
                    "The Q5A analysis did not emit a debug overlay artifact.",
                    package_id=package_id,
                    shot_id=shot_id,
                )
            )
        mask_extraction_mode = str(analysis.get("mask_extraction_mode") or "unknown")
        if mask_extraction_mode not in mask_mode_counts:
            mask_mode_counts[mask_extraction_mode] = 0
        mask_mode_counts[mask_extraction_mode] += 1
        shot_results.append(
            {
                "shot_id": shot_id,
                "status": "pass" if not shot_failed_requirements else "fail",
                "mask_extraction_mode": mask_extraction_mode,
                "mask_extraction_signal": dict(analysis.get("mask_extraction_signal") or {}),
                "artifacts": {
                    "body_only_image_path": str(artifacts.get("body_only_image_path") or ""),
                    "slot_only_image_path": str(artifacts.get("slot_only_image_path") or ""),
                    "combined_visible_image_path": str(artifacts.get("combined_visible_image_path") or ""),
                    "debug_overlay_path": str(analysis.get("debug_overlay_path") or ""),
                },
                "metrics": dict(analysis.get("metrics") or {}),
                "failed_requirements": shot_failed_requirements,
            }
        )
        failed_requirements.extend(shot_failed_requirements)

    host_errors = list(host_result.get("errors") or [])
    if host_errors and not shot_results:
        failed_requirements.append(
            make_failed_requirement(
                "mask_capture_failed",
                "The host-side visible conflict inspection failed before any shot results were produced.",
                package_id=package_id,
                errors=host_errors,
            )
        )
    return (
        {
            "package_id": package_id,
            "sample_id": host_result.get("sample_id"),
            "host_blueprint_asset": host_result.get("host_blueprint_asset"),
            "clothing_binding": dict(host_result.get("clothing_binding") or {}),
            "clothing_attach_state": dict(host_result.get("clothing_attach_state") or {}),
            "status": "pass" if not failed_requirements else "fail",
            "shot_results": shot_results,
            "mask_capture_signal": {
                "mask_mode_counts": mask_mode_counts,
                "all_shots_use_color_threshold": mask_mode_counts.get("silhouette_fallback", 0) == 0 and bool(shot_results),
                "any_shot_uses_silhouette_fallback": mask_mode_counts.get("silhouette_fallback", 0) > 0,
            },
            "errors": sorted(set(host_errors)),
            "artifacts": {
                "host_result_output_root": str(((host_result.get("artifacts") or {}).get("output_root")) or ""),
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
    p2_report_path = resolve_report_path(
        args.p2_report_path,
        default_latest_p2_report_path(workspace),
        "No latest_clothing_vertical_slice_p2_report.json could be resolved for Q5A.",
    )
    p2_report = load_json(p2_report_path)
    ready_packages = ready_p2_packages(
        p2_report,
        clothing_asset_path=args.clothing_asset_path,
        attach_socket_name=args.attach_socket_name,
        slot_name=args.slot_name,
    )

    if len(ready_packages) != 2:
        failed_requirements.append(
            make_failed_requirement(
                "q5a_ready_package_count_mismatch",
                "Q5A requires exactly 2 P2 runtime+visual ready bundles.",
                resolved_ready_packages=len(ready_packages),
                required_ready_packages=2,
                resolved_package_ids=[item["package_id"] for item in ready_packages],
            )
        )

    per_package_results = []
    for package in ready_packages:
        host_result = {}
        host_result_path = output_root / "host_results" / f"{package['package_id']}.json"
        try:
            host_result, host_result_path = run_package_inspection(
                workspace=workspace,
                output_root=output_root,
                package=package,
                level_path=args.level_path,
                slot_name=args.slot_name,
            )
        except Exception as exc:
            if host_result_path.exists():
                host_result = dict((load_json(host_result_path).get("result") or {}))
            else:
                host_result = {
                    "package_id": package["package_id"],
                    "sample_id": package["sample_id"],
                    "host_blueprint_asset": package["host_blueprint_asset"],
                    "clothing_binding": dict(package["clothing_binding"]),
                    "errors": [str(exc)],
                    "shot_results": [],
                }
        package_result, package_failures = analyze_host_result(host_result, output_root=output_root)
        package_result["package_id"] = package["package_id"]
        package_result["sample_id"] = package["sample_id"]
        package_result["host_blueprint_asset"] = package["host_blueprint_asset"]
        package_result["clothing_binding"] = dict(host_result.get("clothing_binding") or package["clothing_binding"])
        package_result["artifacts"]["result_path"] = str(host_result_path.resolve())
        per_package_results.append(package_result)
        failed_requirements.extend(package_failures)

    counts = {
        "required_package_count": 2,
        "resolved_package_count": len(ready_packages),
        "packages": len(per_package_results),
        "passing_packages": sum(1 for item in per_package_results if item.get("status") == "pass"),
        "shot_sets": sum(len(list(item.get("shot_results") or [])) for item in per_package_results),
        "passing_shot_sets": sum(
            1
            for item in per_package_results
            for shot in list(item.get("shot_results") or [])
            if shot.get("status") == "pass"
        ),
        "raw_pass_images": sum(
            3
            for item in per_package_results
            for shot in list(item.get("shot_results") or [])
            if all(str((shot.get("artifacts") or {}).get(key) or "").strip() for key in ("body_only_image_path", "slot_only_image_path", "combined_visible_image_path"))
        ),
        "debug_overlays": sum(
            1
            for item in per_package_results
            for shot in list(item.get("shot_results") or [])
            if str((shot.get("artifacts") or {}).get("debug_overlay_path") or "").strip()
        ),
        "color_threshold_shot_sets": sum(
            1
            for item in per_package_results
            for shot in list(item.get("shot_results") or [])
            if str(shot.get("mask_extraction_mode") or "") == "color_threshold"
        ),
        "silhouette_fallback_shot_sets": sum(
            1
            for item in per_package_results
            for shot in list(item.get("shot_results") or [])
            if str(shot.get("mask_extraction_mode") or "") == "silhouette_fallback"
        ),
    }

    gate_status = "pass"
    if failed_requirements:
        gate_status = "fail"
    if len(ready_packages) != 2:
        gate_status = "fail"
    if counts["shot_sets"] != 4:
        failed_requirements.append(
            make_failed_requirement(
                "q5a_shot_count_mismatch",
                "Q5A requires exactly 4 shot sets across the two ready bundles.",
                actual=counts["shot_sets"],
                required=4,
            )
        )
        gate_status = "fail"
    if counts["raw_pass_images"] != 12:
        failed_requirements.append(
            make_failed_requirement(
                "q5a_raw_pass_image_count_mismatch",
                "Q5A requires 12 raw pass images across body_only / slot_only / combined_visible.",
                actual=counts["raw_pass_images"],
                required=12,
            )
        )
        gate_status = "fail"
    if counts["debug_overlays"] != 4:
        failed_requirements.append(
            make_failed_requirement(
                "q5a_debug_overlay_count_mismatch",
                "Q5A requires one debug overlay per shot set.",
                actual=counts["debug_overlays"],
                required=4,
            )
        )
        gate_status = "fail"

    discussion_signal = build_discussion_signal(
        gate_status,
        failed_requirements,
        previous_report,
        previous_report_path,
        "first_complete_q5a_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": gate_status,
            "success": gate_status == "pass",
            "workspace_config": workspace["config_path"],
            "source_report": str(p2_report_path.resolve()),
            "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
            "counts": counts,
            "failed_requirements": failed_requirements,
            "resolved_package_ids": [item["package_id"] for item in ready_packages],
            "mask_capture_signal": {
                "all_shots_use_color_threshold": counts["shot_sets"] > 0 and counts["silhouette_fallback_shot_sets"] == 0,
                "any_shot_uses_silhouette_fallback": counts["silhouette_fallback_shot_sets"] > 0,
                "all_shots_use_silhouette_fallback": counts["shot_sets"] > 0 and counts["silhouette_fallback_shot_sets"] == counts["shot_sets"],
                "color_threshold_shot_sets": counts["color_threshold_shot_sets"],
                "silhouette_fallback_shot_sets": counts["silhouette_fallback_shot_sets"],
            },
            "per_package_results": per_package_results,
            "artifacts": {
                "output_root": str(output_root.resolve()),
            },
            "discussion_signal": discussion_signal,
        },
        "aiue_visible_conflict_inspection_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            schema_family="aiue_visible_conflict_inspection_report",
            notes=[
                "internal_q5a_gate",
                "body_vs_clothing_visible_conflict",
            ],
        ),
        schema_version="0.1.0",
    )

    report_path = output_root / f"{GATE_ID}_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(str(report_path))


if __name__ == "__main__":
    main()
