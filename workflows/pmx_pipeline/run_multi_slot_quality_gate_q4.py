from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _demo_common import default_named_verification_report_path, resolve_report_path
from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, make_failed_requirement, now_utc, write_report_pair

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config

GATE_ID = "multi_slot_quality_gate_q4"
DEFAULT_P4_LATEST_NAME = "latest_multi_slot_composition_p4_report.json"
FIXED_EXECUTION_PROFILE = {
    "strict_shot_ids": ["front", "side"],
    "strict_weapon_min_coverage": 0.004,
    "strict_clothing_min_coverage": 0.001,
    "strict_fx_min_coverage": 0.03,
    "hero_weapon_min_coverage": 0.004,
    "hero_clothing_min_coverage": 0.003,
    "hero_fx_min_coverage": 0.05,
    "allow_clothing_owner_origin_fallback": True,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE Q4 multi-slot quality gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--p4-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def default_latest_p4_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_P4_LATEST_NAME)


def shot_lookup(visual_check: dict) -> dict[str, dict]:
    return {str(shot.get("shot_id") or ""): dict(shot) for shot in list(visual_check.get("shots") or [])}


def tracked_coverage(shot: dict, slot_name: str) -> float:
    tracked = dict((shot.get("tracked_slot_coverages") or {}).get(slot_name) or {})
    return float(tracked.get("coverage_ratio") or 0.0)


def shot_quality_payload(shot: dict) -> dict:
    quality_gate = dict(shot.get("quality_gate") or {})
    return {
        "status": str(shot.get("status") or "fail"),
        "weapon_visible": bool(quality_gate.get("weapon_visible")),
        "subject_visible": bool(quality_gate.get("subject_visible")),
        "line_of_sight_clear": bool(quality_gate.get("line_of_sight_clear")),
        "capture_succeeded": bool(quality_gate.get("capture_succeeded")),
        "subject_screen_coverage": float(shot.get("subject_screen_coverage") or 0.0),
        "weapon_screen_coverage": float(shot.get("weapon_screen_coverage") or 0.0),
        "clothing_screen_coverage": tracked_coverage(shot, "clothing"),
        "fx_screen_coverage": tracked_coverage(shot, "fx"),
        "image_path": str(shot.get("image_path") or ""),
    }


def strict_shot_checks(shot_id: str, shot: dict) -> tuple[dict, list[dict]]:
    payload = shot_quality_payload(shot)
    failed_requirements = []
    if payload["status"] != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "q4_strict_shot_failed",
                "A required strict shot did not pass the underlying visual proof.",
                shot_id=shot_id,
                shot_status=payload["status"],
            )
        )
    if not payload["weapon_visible"] or payload["weapon_screen_coverage"] < float(FIXED_EXECUTION_PROFILE["strict_weapon_min_coverage"]):
        failed_requirements.append(
            make_failed_requirement(
                "q4_weapon_visibility_insufficient",
                "A required strict shot did not keep the weapon visible enough.",
                shot_id=shot_id,
                weapon_screen_coverage=payload["weapon_screen_coverage"],
                minimum=float(FIXED_EXECUTION_PROFILE["strict_weapon_min_coverage"]),
            )
        )
    if payload["clothing_screen_coverage"] < float(FIXED_EXECUTION_PROFILE["strict_clothing_min_coverage"]):
        failed_requirements.append(
            make_failed_requirement(
                "q4_clothing_visibility_insufficient",
                "A required strict shot did not keep the clothing slot visible enough.",
                shot_id=shot_id,
                clothing_screen_coverage=payload["clothing_screen_coverage"],
                minimum=float(FIXED_EXECUTION_PROFILE["strict_clothing_min_coverage"]),
            )
        )
    if payload["fx_screen_coverage"] < float(FIXED_EXECUTION_PROFILE["strict_fx_min_coverage"]):
        failed_requirements.append(
            make_failed_requirement(
                "q4_fx_visibility_insufficient",
                "A required strict shot did not keep the FX slot visible enough.",
                shot_id=shot_id,
                fx_screen_coverage=payload["fx_screen_coverage"],
                minimum=float(FIXED_EXECUTION_PROFILE["strict_fx_min_coverage"]),
            )
        )
    return (
        {
            "shot_id": shot_id,
            "status": "pass" if not failed_requirements else "fail",
            **payload,
        },
        failed_requirements,
    )


def is_hero_shot(shot: dict) -> bool:
    payload = shot_quality_payload(shot)
    return bool(
        payload["status"] == "pass"
        and payload["weapon_visible"]
        and payload["weapon_screen_coverage"] >= float(FIXED_EXECUTION_PROFILE["hero_weapon_min_coverage"])
        and payload["clothing_screen_coverage"] >= float(FIXED_EXECUTION_PROFILE["hero_clothing_min_coverage"])
        and payload["fx_screen_coverage"] >= float(FIXED_EXECUTION_PROFILE["hero_fx_min_coverage"])
    )


def evaluate_package(runtime_check: dict, visual_check: dict) -> tuple[dict, list[dict]]:
    failed_requirements = []
    package_id = str(runtime_check.get("package_id") or visual_check.get("package_id") or "")
    strict_results = []

    if runtime_check.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "q4_runtime_prerequisite_failed",
                "Q4 requires a passing P4 runtime check for each package.",
                package_id=package_id,
            )
        )
    if visual_check.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "q4_visual_prerequisite_failed",
                "Q4 requires a passing P4 visual check for each package.",
                package_id=package_id,
            )
        )

    clothing_attach_state = dict(runtime_check.get("clothing_attach_state") or {})
    clothing_owner_origin_ok = bool(runtime_check.get("clothing_owner_origin_ok"))
    if clothing_attach_state.get("resolved_attach_socket_exists") is False and not (
        FIXED_EXECUTION_PROFILE["allow_clothing_owner_origin_fallback"] and clothing_owner_origin_ok
    ):
        failed_requirements.append(
            make_failed_requirement(
                "q4_clothing_attach_quality_failed",
                "Q4 requires the clothing slot attach state to be resolved or explicitly accepted as owner_origin fallback.",
                package_id=package_id,
                clothing_attach_state=clothing_attach_state,
            )
        )

    fx_attach_state = dict(runtime_check.get("fx_attach_state") or {})
    if fx_attach_state.get("resolved_attach_socket_exists") is False:
        failed_requirements.append(
            make_failed_requirement(
                "q4_fx_attach_quality_failed",
                "Q4 requires the FX slot attach state to resolve successfully.",
                package_id=package_id,
                fx_attach_state=fx_attach_state,
            )
        )

    shots_by_id = shot_lookup(visual_check)
    for shot_id in list(FIXED_EXECUTION_PROFILE["strict_shot_ids"]):
        shot = dict(shots_by_id.get(shot_id) or {})
        if not shot:
            failed_requirements.append(
                make_failed_requirement(
                    "q4_required_shot_missing",
                    "Q4 requires all strict shot ids to be present in the P4 visual report.",
                    package_id=package_id,
                    shot_id=shot_id,
                )
            )
            continue
        strict_result, shot_failures = strict_shot_checks(shot_id, shot)
        strict_results.append(strict_result)
        failed_requirements.extend(
            [
                {
                    **failure,
                    "package_id": package_id,
                }
                for failure in shot_failures
            ]
        )

    hero_shot_ids = [
        str(shot.get("shot_id") or "")
        for shot in list(visual_check.get("shots") or [])
        if is_hero_shot(dict(shot))
    ]
    if not hero_shot_ids:
        failed_requirements.append(
            make_failed_requirement(
                "q4_full_stack_hero_shot_missing",
                "Q4 requires at least one hero shot where weapon, clothing, and FX all exceed the stronger coexistence thresholds.",
                package_id=package_id,
                thresholds={
                    "weapon": float(FIXED_EXECUTION_PROFILE["hero_weapon_min_coverage"]),
                    "clothing": float(FIXED_EXECUTION_PROFILE["hero_clothing_min_coverage"]),
                    "fx": float(FIXED_EXECUTION_PROFILE["hero_fx_min_coverage"]),
                },
            )
        )

    return (
        {
            "package_id": package_id,
            "sample_id": runtime_check.get("sample_id") or visual_check.get("sample_id"),
            "status": "pass" if not failed_requirements else "fail",
            "strict_shot_results": strict_results,
            "hero_shot_ids": hero_shot_ids,
            "weapon_binding": runtime_check.get("weapon_binding"),
            "clothing_binding": runtime_check.get("clothing_binding"),
            "fx_binding": runtime_check.get("fx_binding"),
            "clothing_attach_state": clothing_attach_state,
            "clothing_owner_origin_ok": clothing_owner_origin_ok,
            "fx_attach_state": fx_attach_state,
            "artifacts": {
                "runtime_result_path": str(((runtime_check.get("artifacts") or {}).get("result_path")) or ""),
                "visual_result_path": str(((visual_check.get("artifacts") or {}).get("result_path")) or ""),
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
    p4_report_path = resolve_report_path(
        args.p4_report_path,
        default_latest_p4_report_path(workspace),
        "No latest_multi_slot_composition_p4_report.json could be resolved for Q4.",
    )
    p4_report = load_json(p4_report_path)
    if p4_report.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "q4_source_prerequisite_failed",
                "Q4 requires a passing P4 coexistence report.",
                p4_report_path=str(p4_report_path.resolve()),
                p4_status=p4_report.get("status"),
            )
        )

    runtime_checks = list(p4_report.get("runtime_checks") or [])
    visual_checks = list(p4_report.get("visual_checks") or [])
    runtime_by_package = {str(item.get("package_id") or ""): dict(item) for item in runtime_checks}
    visual_by_package = {str(item.get("package_id") or ""): dict(item) for item in visual_checks}
    package_ids = sorted(set(runtime_by_package) | set(visual_by_package))
    per_package_results = []

    if not failed_requirements:
        for package_id in package_ids:
            runtime_check = runtime_by_package.get(package_id)
            visual_check = visual_by_package.get(package_id)
            if not runtime_check or not visual_check:
                failed_requirements.append(
                    make_failed_requirement(
                        "q4_package_pairing_incomplete",
                        "Q4 requires both runtime and visual P4 records for each package.",
                        package_id=package_id,
                    )
                )
                continue
            evaluated_package, package_failures = evaluate_package(runtime_check, visual_check)
            per_package_results.append(evaluated_package)
            failed_requirements.extend(package_failures)

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(status, failed_requirements, previous_report, previous_report_path, "q4_first_complete_pass")
    counts = {
        "evaluated_packages": len(per_package_results),
        "passing_packages": sum(1 for item in per_package_results if item.get("status") == "pass"),
        "strict_shots_evaluated": sum(len(list(item.get("strict_shot_results") or [])) for item in per_package_results),
        "strict_shots_passed": sum(
            1
            for item in per_package_results
            for shot in list(item.get("strict_shot_results") or [])
            if shot.get("status") == "pass"
        ),
        "packages_with_hero_shot": sum(1 for item in per_package_results if list(item.get("hero_shot_ids") or [])),
        "packages_using_clothing_owner_origin_fallback": sum(1 for item in per_package_results if item.get("clothing_owner_origin_ok")),
    }

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": args.workspace_config,
            "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
            "counts": counts,
            "failed_requirements": failed_requirements,
            "source_report": {
                "p4_report_path": str(p4_report_path.resolve()),
                "gate_id": p4_report.get("gate_id"),
                "status": p4_report.get("status"),
            },
            "per_package_results": per_package_results,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
            },
        },
        schema_family="aiue_multi_slot_quality_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_multi_slot_quality_report",
            notes=["internal_q4_gate", "slot_aware_quality", "multi_slot_platform"],
        ),
    )
    report_path = output_root / "q4_multi_slot_quality_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
