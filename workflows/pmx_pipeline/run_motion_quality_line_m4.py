from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import (  # noqa: E402
    build_discussion_signal,
    default_latest_report_path,
    default_output_root,
    make_failed_requirement,
    now_utc,
    repo_root_from_workspace,
    write_report_pair,
)
from aiue_core.report_writer import make_compatibility_block, with_report_envelope  # noqa: E402
from aiue_core.schema_utils import load_json, load_workspace_config  # noqa: E402


GATE_ID = "motion_quality_line_m4"
SOURCE_GATE_ID = "motion_default_source_switch_m3_5"
REQUIRED_CHAIN_NAMES = {"root", "Spine", "LeftClavicle", "RightClavicle", "LeftArm", "RightArm"}
ALLOWED_ACTION_WARNINGS = {"animation_blueprint_library_unavailable"}
MIN_NATIVE_CHANGED_BONES = 1
MIN_NATIVE_LOCATION_DELTA = 1.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the current motion line as a reusable quality capability.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--source-report")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def resolve_source_report_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Source report path does not exist: {candidate}")
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    candidate = repo_root / "Saved" / "verification" / f"latest_{SOURCE_GATE_ID}_report.json"
    if candidate.exists():
        return candidate.resolve()
    raise FileNotFoundError(f"Latest M3.5 report is missing: {candidate}")


def _existing_file(path_text: str | None) -> bool:
    text = str(path_text or "").strip()
    if not text:
        return False
    return Path(text).expanduser().exists()


def evaluate_package_quality(package_result: dict[str, Any]) -> dict[str, Any]:
    package_id = str(package_result.get("package_id") or "")
    sample_id = str(package_result.get("sample_id") or "")
    scenario_id = str(package_result.get("scenario_id") or "")
    artifacts = dict(package_result.get("import_ready_artifacts") or {})
    consumer_result_report_path = str(artifacts.get("consumer_result_report_path") or "")
    preview_result_json_path = str(artifacts.get("preview_result_json_path") or "")
    manifest_path = str(artifacts.get("packet_manifest_path") or "")

    failed_requirements: list[dict[str, Any]] = []
    if not _existing_file(consumer_result_report_path):
        failed_requirements.append(
            make_failed_requirement(
                "m4_consumer_result_report_missing",
                f"Consumer result report is missing for package {package_id}.",
                package_id=package_id,
                consumer_result_report_path=consumer_result_report_path,
            )
        )
        return {
            "package_id": package_id,
            "sample_id": sample_id,
            "scenario_id": scenario_id,
            "status": "fail",
            "failed_requirements": failed_requirements,
        }
    if not _existing_file(preview_result_json_path):
        failed_requirements.append(
            make_failed_requirement(
                "m4_preview_result_missing",
                f"Preview action result is missing for package {package_id}.",
                package_id=package_id,
                preview_result_json_path=preview_result_json_path,
            )
        )
        return {
            "package_id": package_id,
            "sample_id": sample_id,
            "scenario_id": scenario_id,
            "status": "fail",
            "failed_requirements": failed_requirements,
        }

    consumer_report = load_json(consumer_result_report_path)
    preview_payload = load_json(preview_result_json_path)
    manifest_payload = load_json(Path(manifest_path).expanduser()) if _existing_file(manifest_path) else {}
    consumer_result = dict(consumer_report.get("consumer_result") or {})
    preview_result = dict(preview_payload.get("result") or {})
    native_eval = dict(preview_result.get("native_animation_pose_evaluation") or {})
    retarget_generation = dict(preview_result.get("retarget_generation") or {})
    animation_compatibility = dict(preview_result.get("animation_compatibility") or {})
    direct_animation_compatibility = dict(preview_result.get("direct_animation_compatibility") or {})
    warnings = {str(item) for item in list(preview_payload.get("warnings") or []) if str(item)}
    unexpected_warnings = sorted(warnings - ALLOWED_ACTION_WARNINGS)
    exact_chain_names = {str(item) for item in list(retarget_generation.get("exact_named_mapped_chain_names") or []) if str(item)}

    if str(preview_payload.get("status") or "") != "pass" or not bool(preview_payload.get("success")):
        failed_requirements.append(
            make_failed_requirement(
                "m4_preview_action_not_pass",
                f"Animation preview action did not pass for package {package_id}.",
                package_id=package_id,
                preview_status=str(preview_payload.get("status") or ""),
            )
        )
    if str(preview_result.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "m4_preview_result_not_pass",
                f"Preview result did not pass for package {package_id}.",
                package_id=package_id,
                preview_result_status=str(preview_result.get("status") or ""),
            )
        )
    if str(consumer_result.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "m4_consumer_result_not_pass",
                f"Consumer result did not pass for package {package_id}.",
                package_id=package_id,
                consumer_result_status=str(consumer_result.get("status") or ""),
            )
        )
    if not bool(animation_compatibility.get("compatible")):
        failed_requirements.append(
            make_failed_requirement(
                "m4_animation_compatibility_failed",
                f"Resolved animation compatibility is false for package {package_id}.",
                package_id=package_id,
            )
        )
    if not bool(retarget_generation.get("success")):
        failed_requirements.append(
            make_failed_requirement(
                "m4_retarget_generation_failed",
                f"Retarget generation did not succeed for package {package_id}.",
                package_id=package_id,
            )
        )
    missing_chains = sorted(REQUIRED_CHAIN_NAMES - exact_chain_names)
    if missing_chains:
        failed_requirements.append(
            make_failed_requirement(
                "m4_required_retarget_chains_missing",
                f"Required retarget chains are missing for package {package_id}.",
                package_id=package_id,
                missing_chains=missing_chains,
            )
        )
    if not bool(native_eval.get("available")) or not bool(native_eval.get("success")) or not bool(native_eval.get("pose_changed")):
        failed_requirements.append(
            make_failed_requirement(
                "m4_native_pose_evaluation_failed",
                f"Native pose evaluation is not strong enough for package {package_id}.",
                package_id=package_id,
                native_available=bool(native_eval.get("available")),
                native_success=bool(native_eval.get("success")),
                pose_changed=bool(native_eval.get("pose_changed")),
            )
        )
    if int(native_eval.get("changed_bone_count") or 0) < MIN_NATIVE_CHANGED_BONES:
        failed_requirements.append(
            make_failed_requirement(
                "m4_changed_bone_count_too_low",
                f"Changed bone count is too low for package {package_id}.",
                package_id=package_id,
                changed_bone_count=int(native_eval.get("changed_bone_count") or 0),
                required_minimum=MIN_NATIVE_CHANGED_BONES,
            )
        )
    if float(native_eval.get("max_location_delta") or 0.0) < MIN_NATIVE_LOCATION_DELTA:
        failed_requirements.append(
            make_failed_requirement(
                "m4_location_delta_too_low",
                f"Native max location delta is too low for package {package_id}.",
                package_id=package_id,
                max_location_delta=float(native_eval.get("max_location_delta") or 0.0),
                required_minimum=MIN_NATIVE_LOCATION_DELTA,
            )
        )
    if unexpected_warnings:
        failed_requirements.append(
            make_failed_requirement(
                "m4_unexpected_action_warnings",
                f"Unexpected action warnings are present for package {package_id}.",
                package_id=package_id,
                warnings=unexpected_warnings,
            )
        )
    if not _existing_file(artifacts.get("before_image_path")) or not _existing_file(artifacts.get("after_image_path")):
        failed_requirements.append(
            make_failed_requirement(
                "m4_preview_images_missing",
                f"Preview images are missing for package {package_id}.",
                package_id=package_id,
                before_image_path=str(artifacts.get("before_image_path") or ""),
                after_image_path=str(artifacts.get("after_image_path") or ""),
            )
        )
    if str(preview_result.get("sample_id") or "") and str(preview_result.get("sample_id") or "") != sample_id:
        failed_requirements.append(
            make_failed_requirement(
                "m4_sample_id_drift",
                f"Preview result sample id drifted for package {package_id}.",
                package_id=package_id,
                expected_sample_id=sample_id,
                actual_sample_id=str(preview_result.get("sample_id") or ""),
            )
        )
    if str(preview_result.get("package_id") or "") and str(preview_result.get("package_id") or "") != package_id:
        failed_requirements.append(
            make_failed_requirement(
                "m4_package_id_drift",
                f"Preview result package id drifted for package {package_id}.",
                package_id=package_id,
                actual_package_id=str(preview_result.get("package_id") or ""),
            )
        )

    duration_sec = float(manifest_payload.get("duration_sec") or 0.0)
    fps = int(manifest_payload.get("fps") or 0)
    frame_count = int(manifest_payload.get("frame_count") or 0)
    if duration_sec <= 0 or fps <= 0 or frame_count <= 0:
        failed_requirements.append(
            make_failed_requirement(
                "m4_manifest_motion_shape_invalid",
                f"Motion manifest shape is invalid for package {package_id}.",
                package_id=package_id,
                duration_sec=duration_sec,
                fps=fps,
                frame_count=frame_count,
            )
        )

    return {
        "package_id": package_id,
        "sample_id": sample_id,
        "scenario_id": scenario_id,
        "status": "pass" if not failed_requirements else "fail",
        "direct_animation_compatible": bool(direct_animation_compatibility.get("compatible")),
        "resolved_animation_compatible": bool(animation_compatibility.get("compatible")),
        "retarget_success": bool(retarget_generation.get("success")),
        "required_chain_coverage": sorted(exact_chain_names),
        "native_pose_changed": bool(native_eval.get("pose_changed")),
        "native_changed_bone_count": int(native_eval.get("changed_bone_count") or 0),
        "native_max_location_delta": float(native_eval.get("max_location_delta") or 0.0),
        "unexpected_warnings": unexpected_warnings,
        "motion_shape": {
            "duration_sec": duration_sec,
            "fps": fps,
            "frame_count": frame_count,
        },
        "failed_requirements": failed_requirements,
        "artifacts": {
            "consumer_result_report_path": consumer_result_report_path,
            "preview_result_json_path": preview_result_json_path,
            "packet_manifest_path": manifest_path,
            "before_image_path": str(artifacts.get("before_image_path") or ""),
            "after_image_path": str(artifacts.get("after_image_path") or ""),
        },
    }


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)

    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    source_report_path = resolve_source_report_path(workspace, args.source_report)
    source_report = load_json(source_report_path)
    failed_requirements: list[dict[str, Any]] = []

    if str(source_report.get("status") or "") != "pass" or not bool(source_report.get("default_source_applied")):
        failed_requirements.append(
            make_failed_requirement(
                "m4_source_switch_not_pass",
                "M3.5 source switch is not pass.",
                source_report=str(source_report_path),
                source_status=str(source_report.get("status") or ""),
                default_source_applied=bool(source_report.get("default_source_applied")),
            )
        )

    m3_report_path = Path(str(((source_report.get("artifacts") or {}).get("m3_report_path")) or "")).expanduser()
    m2_5_report_path = Path(str(((source_report.get("artifacts") or {}).get("m2_5_report_path")) or "")).expanduser()
    if not m3_report_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "m4_m3_report_missing",
                "M4 requires a resolvable M3 report path.",
                m3_report_path=str(m3_report_path),
            )
        )
    if not m2_5_report_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "m4_m2_5_report_missing",
                "M4 requires a resolvable M2.5 report path.",
                m2_5_report_path=str(m2_5_report_path),
            )
        )

    package_evaluations: list[dict[str, Any]] = []
    candidate_snapshot: dict[str, Any] = {}
    if not failed_requirements:
        m3_report = load_json(m3_report_path)
        m2_5_report = load_json(m2_5_report_path)
        candidate_snapshot = dict(m3_report.get("candidate_snapshot") or {})
        for package_result in list(m2_5_report.get("package_results") or []):
            package_evaluations.append(evaluate_package_quality(package_result))
        for item in package_evaluations:
            failed_requirements.extend(list(item.get("failed_requirements") or []))
        if len(package_evaluations) < 3:
            failed_requirements.append(
                make_failed_requirement(
                    "m4_package_count_insufficient",
                    "M4 requires at least three package evaluations.",
                    package_count=len(package_evaluations),
                    required_minimum=3,
                )
            )
        if len(list(candidate_snapshot.get("scenario_ids") or [])) < 3:
            failed_requirements.append(
                make_failed_requirement(
                    "m4_distinct_scenarios_insufficient",
                    "M4 requires at least three distinct scenarios in the candidate snapshot.",
                    scenario_ids=list(candidate_snapshot.get("scenario_ids") or []),
                )
            )

    counts = {
        "package_count": len(package_evaluations),
        "quality_passes": sum(1 for item in package_evaluations if item["status"] == "pass"),
        "quality_failures": sum(1 for item in package_evaluations if item["status"] != "pass"),
        "retarget_successes": sum(1 for item in package_evaluations if item.get("retarget_success")),
        "native_pose_changed_passes": sum(1 for item in package_evaluations if item.get("native_pose_changed")),
        "unexpected_warning_packages": sum(1 for item in package_evaluations if item.get("unexpected_warnings")),
        "direct_compatible_packages": sum(1 for item in package_evaluations if item.get("direct_animation_compatible")),
        "resolved_compatible_packages": sum(1 for item in package_evaluations if item.get("resolved_animation_compatible")),
        "distinct_scenarios": len(list(candidate_snapshot.get("scenario_ids") or [])),
    }
    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        latest_report_path if latest_report_path.exists() else None,
        "m4_motion_quality_line_first_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_report": str(source_report_path),
            "source_gate_id": SOURCE_GATE_ID,
            "fixed_execution_profile": {
                "source_mode": "report_only",
                "quality_focus": "retarget_and_native_pose_quality",
                "required_chain_names": sorted(REQUIRED_CHAIN_NAMES),
                "allowed_action_warnings": sorted(ALLOWED_ACTION_WARNINGS),
                "minimum_changed_bones": MIN_NATIVE_CHANGED_BONES,
                "minimum_native_location_delta": MIN_NATIVE_LOCATION_DELTA,
            },
            "candidate_snapshot": candidate_snapshot,
            "counts": counts,
            "package_results": package_evaluations,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "m3_5_report_path": str(source_report_path),
                "m3_report_path": str(m3_report_path),
                "m2_5_report_path": str(m2_5_report_path),
            },
        },
        "motion_quality_line_m4_report",
        workflow_pack="pmx_pipeline",
        tool_name="AiUE",
        compatibility=make_compatibility_block(
            schema_family="motion_quality_line_m4_report",
            notes=["internal_gate_runner", "motion_quality_line", "retarget_quality"],
        ),
    )
    report_path = output_root / f"{GATE_ID}_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(f"M4 motion quality line report written to: {report_path}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
