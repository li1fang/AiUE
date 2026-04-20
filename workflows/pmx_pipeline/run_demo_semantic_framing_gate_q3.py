from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, make_failed_requirement, now_utc, repo_root_from_workspace, run_stamp
from _demo_common import default_named_verification_report_path, extract_quality_subject_report, resolve_report_path

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json

GATE_ID = "demo_semantic_framing_gate_q3"
DEFAULT_D12_LATEST_NAME = "latest_demo_cross_bundle_regression_d12_report.json"
DEFAULT_Q1_LATEST_NAME = "latest_demo_shot_quality_gate_q1_report.json"
DEFAULT_Q2_LATEST_NAME = "latest_demo_composition_quality_gate_q2_report.json"
SHOT_PROFILES = {
    "front": {
        "subject_center_x_ratio_min": 0.68,
        "subject_center_x_ratio_max": 0.76,
        "subject_right_margin_ratio_min": 0.08,
        "weapon_phase_min_screen_coverage": 0.02,
        "weapon_required_visible_phases_per_pair": 1,
        "weapon_expected_side": "left_of_subject_center",
    },
    "side": {
        "subject_center_x_ratio_min": 0.22,
        "subject_center_x_ratio_max": 0.30,
        "subject_right_edge_ratio_max": 0.50,
        "weapon_phase_min_screen_coverage": 0.04,
        "weapon_required_visible_phases_per_pair": 1,
        "weapon_expected_side": "right_of_subject_center",
    },
}

def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE Q3 semantic framing gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--d12-report-path")
    parser.add_argument("--q1-report-path")
    parser.add_argument("--q2-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()

def default_latest_d12_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_D12_LATEST_NAME)

def default_latest_q1_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_Q1_LATEST_NAME)

def default_latest_q2_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_Q2_LATEST_NAME)

def rect_dict(payload: dict | None) -> dict:
    return dict(payload or {})

def phase_metrics(phase_report: dict, image_width: int, image_height: int) -> dict:
    subject_rect = rect_dict(dict(phase_report.get("subject_coverage") or {}).get("screen_rect"))
    weapon_rect = rect_dict(dict(phase_report.get("weapon_coverage") or {}).get("screen_rect"))
    subj_min_x = float(subject_rect.get("min_x") or 0.0)
    subj_max_x = float(subject_rect.get("max_x") or 0.0)
    subj_min_y = float(subject_rect.get("min_y") or 0.0)
    subj_max_y = float(subject_rect.get("max_y") or 0.0)
    weapon_min_x = float(weapon_rect.get("min_x") or 0.0)
    weapon_max_x = float(weapon_rect.get("max_x") or 0.0)
    weapon_min_y = float(weapon_rect.get("min_y") or 0.0)
    weapon_max_y = float(weapon_rect.get("max_y") or 0.0)
    subject_center_x = (subj_min_x + subj_max_x) * 0.5
    subject_center_y = (subj_min_y + subj_max_y) * 0.5
    weapon_center_x = (weapon_min_x + weapon_max_x) * 0.5 if weapon_rect else 0.0
    weapon_center_y = (weapon_min_y + weapon_max_y) * 0.5 if weapon_rect else 0.0
    return {
        "subject_screen_coverage": float(phase_report.get("subject_screen_coverage") or 0.0),
        "weapon_screen_coverage": float(phase_report.get("weapon_screen_coverage") or 0.0),
        "subject_center_x_ratio": subject_center_x / float(image_width) if image_width else 0.0,
        "subject_center_y_ratio": subject_center_y / float(image_height) if image_height else 0.0,
        "subject_right_margin_ratio": max(0.0, float(image_width) - subj_max_x) / float(image_width) if image_width else 0.0,
        "subject_right_edge_ratio": subj_max_x / float(image_width) if image_width else 0.0,
        "subject_center_x": subject_center_x,
        "weapon_center_x": weapon_center_x,
        "weapon_center_y": weapon_center_y,
        "weapon_rect_present": bool(weapon_rect),
    }

def evaluate_phase_for_profile(phase_report: dict, shot_id: str, image_width: int, image_height: int) -> dict:
    profile = dict(SHOT_PROFILES.get(shot_id) or {})
    metrics = phase_metrics(phase_report, image_width=image_width, image_height=image_height)
    failed_checks = []
    subject_center_x_ratio = float(metrics["subject_center_x_ratio"])
    if subject_center_x_ratio < float(profile["subject_center_x_ratio_min"]):
        failed_checks.append("subject_center_too_far_left")
    if subject_center_x_ratio > float(profile["subject_center_x_ratio_max"]):
        failed_checks.append("subject_center_too_far_right")
    if "subject_right_margin_ratio_min" in profile and float(metrics["subject_right_margin_ratio"]) < float(profile["subject_right_margin_ratio_min"]):
        failed_checks.append("subject_right_margin_too_small")
    if "subject_right_edge_ratio_max" in profile and float(metrics["subject_right_edge_ratio"]) > float(profile["subject_right_edge_ratio_max"]):
        failed_checks.append("subject_right_edge_too_far_right")
    return {
        "status": "pass" if not failed_checks else "fail",
        "failed_checks": failed_checks,
        "metrics": metrics,
    }

def evaluate_pair(pair_shot: dict, image_width: int, image_height: int) -> dict:
    shot_id = str(pair_shot.get("shot_id") or "")
    profile = dict(SHOT_PROFILES.get(shot_id) or {})
    before_eval = evaluate_phase_for_profile(dict(pair_shot.get("before") or {}), shot_id=shot_id, image_width=image_width, image_height=image_height)
    after_eval = evaluate_phase_for_profile(dict(pair_shot.get("after") or {}), shot_id=shot_id, image_width=image_width, image_height=image_height)
    failed_checks = []
    if before_eval["status"] != "pass":
        failed_checks.append("before_phase_semantic_fail")
    if after_eval["status"] != "pass":
        failed_checks.append("after_phase_semantic_fail")

    weapon_visible_phases = []
    semantic_weapon_phases = []
    for phase_name, phase_eval in (("before", before_eval), ("after", after_eval)):
        metrics = dict(phase_eval.get("metrics") or {})
        if float(metrics.get("weapon_screen_coverage") or 0.0) >= float(profile["weapon_phase_min_screen_coverage"]):
            weapon_visible_phases.append(phase_name)
            expected_side = str(profile["weapon_expected_side"])
            subject_center_x = float(metrics.get("subject_center_x") or 0.0)
            weapon_center_x = float(metrics.get("weapon_center_x") or 0.0)
            semantic_ok = (
                weapon_center_x < subject_center_x
                if expected_side == "left_of_subject_center"
                else weapon_center_x > subject_center_x
            )
            if semantic_ok:
                semantic_weapon_phases.append(phase_name)

    if len(weapon_visible_phases) < int(profile["weapon_required_visible_phases_per_pair"]):
        failed_checks.append("weapon_prominence_insufficient")
    if len(semantic_weapon_phases) < int(profile["weapon_required_visible_phases_per_pair"]):
        failed_checks.append("weapon_semantic_position_mismatch")

    return {
        "shot_id": shot_id,
        "camera_id": pair_shot.get("camera_id"),
        "status": "pass" if not failed_checks else "fail",
        "failed_checks": failed_checks,
        "profile": profile,
        "before": before_eval,
        "after": after_eval,
        "weapon_visible_phases": weapon_visible_phases,
        "semantic_weapon_phases": semantic_weapon_phases,
    }

def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict] = []
    source_report_path = resolve_report_path(
        args.d12_report_path,
        default_latest_d12_report_path(workspace),
        "No latest_demo_cross_bundle_regression_d12_report.json could be resolved for Q3.",
    )
    source_report = load_json(source_report_path)
    quality_subject_report, source_metadata = extract_quality_subject_report(source_report, source_report_path)
    q1_report_path = resolve_report_path(
        args.q1_report_path,
        default_latest_q1_report_path(workspace),
        "No latest_demo_shot_quality_gate_q1_report.json could be resolved for Q3.",
    )
    q1_report = load_json(q1_report_path)
    q2_report_path = resolve_report_path(
        args.q2_report_path,
        default_latest_q2_report_path(workspace),
        "No latest_demo_composition_quality_gate_q2_report.json could be resolved for Q3.",
    )
    q2_report = load_json(q2_report_path)

    if quality_subject_report.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "q3_source_prerequisite",
                "Q3 requires a passing D12/D11-like source report before evaluating semantic framing.",
                source_report_path=str(source_report_path.resolve()),
                source_report_status=quality_subject_report.get("status"),
            )
        )
    if q1_report.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "q1_prerequisite",
                "Q3 requires a passing Q1 report.",
                q1_report_path=str(q1_report_path.resolve()),
                q1_status=q1_report.get("status"),
            )
        )
    if q2_report.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "q2_prerequisite",
                "Q3 requires a passing Q2 report.",
                q2_report_path=str(q2_report_path.resolve()),
                q2_status=q2_report.get("status"),
            )
        )

    q1_source_report_path = str(((q1_report.get("source_report") or {}).get("source_report_path")) or "")
    q2_source_report_path = str(((q2_report.get("source_report") or {}).get("source_report_path")) or "")
    if q1_source_report_path and Path(q1_source_report_path).resolve() != source_report_path.resolve():
        failed_requirements.append(
            make_failed_requirement(
                "q1_source_mismatch",
                "Q3 requires Q1 to reference the same source report path.",
                q1_source_report_path=q1_source_report_path,
                q3_source_report_path=str(source_report_path.resolve()),
            )
        )
    if q2_source_report_path and Path(q2_source_report_path).resolve() != source_report_path.resolve():
        failed_requirements.append(
            make_failed_requirement(
                "q2_source_mismatch",
                "Q3 requires Q2 to reference the same source report path.",
                q2_source_report_path=q2_source_report_path,
                q3_source_report_path=str(source_report_path.resolve()),
            )
        )

    source_profile = dict(quality_subject_report.get("fixed_execution_profile") or {})
    image_width = int(source_profile.get("capture_width") or 1280)
    image_height = int(source_profile.get("capture_height") or 720)

    per_round_results = []
    if not failed_requirements:
        for round_result in list(quality_subject_report.get("per_round_results") or []):
            evaluated_round = {
                "round_index": round_result.get("round_index"),
                "status": "pass",
                "per_case_results": [],
                "failed_requirements": [],
            }
            for case_result in list(round_result.get("per_case_results") or []):
                pair_results = [evaluate_pair(pair_shot, image_width=image_width, image_height=image_height) for pair_shot in list(case_result.get("shots") or [])]
                failing_pair_ids = [item.get("shot_id") for item in pair_results if item.get("status") != "pass"]
                case_failed_requirements = []
                if failing_pair_ids:
                    case_failed_requirements.append(
                        make_failed_requirement(
                            "case_semantic_pair_failure",
                            "Every Q3 shot family must satisfy semantic framing and weapon-position rules.",
                            case_id=case_result.get("case_id"),
                            failing_pair_ids=failing_pair_ids,
                        )
                    )
                evaluated_round["per_case_results"].append(
                    {
                        "family": case_result.get("family"),
                        "case_id": case_result.get("case_id"),
                        "animation_asset_path": case_result.get("animation_asset_path"),
                        "status": "pass" if not case_failed_requirements else "fail",
                        "pair_results": pair_results,
                        "failed_requirements": case_failed_requirements,
                    }
                )

            failing_case_ids = [item.get("case_id") for item in evaluated_round["per_case_results"] if item.get("status") != "pass"]
            if failing_case_ids:
                evaluated_round["failed_requirements"].append(
                    make_failed_requirement(
                        "round_semantic_framing_failure",
                        "All cases in a Q3 round must satisfy semantic shot-family framing.",
                        round_index=evaluated_round["round_index"],
                        failing_case_ids=failing_case_ids,
                    )
                )
                evaluated_round["status"] = "fail"
            per_round_results.append(evaluated_round)

    pair_results = []
    for round_result in per_round_results:
        for case_result in list(round_result.get("per_case_results") or []):
            for pair_result in list(case_result.get("pair_results") or []):
                payload = dict(pair_result)
                payload["round_index"] = round_result.get("round_index")
                payload["case_id"] = case_result.get("case_id")
                payload["family"] = case_result.get("family")
                pair_results.append(payload)

    failing_round_indices = [item.get("round_index") for item in per_round_results if item.get("status") != "pass"]
    if failing_round_indices:
        failed_requirements.append(
            make_failed_requirement(
                "q3_round_failure",
                "Every evaluated round must satisfy the Q3 semantic framing gate.",
                failing_round_indices=failing_round_indices,
            )
        )

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(status, failed_requirements, previous_report, previous_report_path, 'q3_first_complete_pass')
    counts = {
        "evaluated_rounds": len(per_round_results),
        "passing_rounds": sum(1 for item in per_round_results if item.get("status") == "pass"),
        "evaluated_cases": sum(len(list(item.get("per_case_results") or [])) for item in per_round_results),
        "passing_cases": sum(1 for round_result in per_round_results for case_result in list(round_result.get("per_case_results") or []) if case_result.get("status") == "pass"),
        "evaluated_shot_pairs": len(pair_results),
        "passing_shot_pairs": sum(1 for item in pair_results if item.get("status") == "pass"),
        "semantic_weapon_pairs": sum(1 for item in pair_results if list(item.get("semantic_weapon_phases") or [])),
        "front_semantic_pairs": sum(1 for item in pair_results if item.get("shot_id") == "front" and item.get("status") == "pass"),
        "side_semantic_pairs": sum(1 for item in pair_results if item.get("shot_id") == "side" and item.get("status") == "pass"),
    }

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": args.workspace_config,
            "host_key": quality_subject_report.get("host_key"),
            "mode": quality_subject_report.get("mode"),
            "level_path": quality_subject_report.get("level_path"),
            "package_id": quality_subject_report.get("package_id"),
            "sample_id": quality_subject_report.get("sample_id"),
            "host_blueprint_asset": quality_subject_report.get("host_blueprint_asset"),
            "fixed_execution_profile": {
                "capture_width": image_width,
                "capture_height": image_height,
                "shot_profiles": SHOT_PROFILES,
                "source_report_kind": source_metadata["source_report_kind"],
                "source_gate_id": source_metadata["source_gate_id"],
            },
            "source_report": source_metadata,
            "q1_report_path": str(q1_report_path.resolve()),
            "q2_report_path": str(q2_report_path.resolve()),
            "counts": counts,
            "failed_requirements": failed_requirements,
            "per_round_results": per_round_results,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "source_report_path": str(source_report_path.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
            },
        },
        "aiue_demo_semantic_framing_gate_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_demo_semantic_framing_gate_report",
            notes=["internal_demo_semantic_framing_gate", "shot_family_profiles", "q1_q2_prerequisite"],
        ),
    )
    report_path = output_root / "q3_demo_semantic_framing_gate_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    print(f"Q3 demo semantic framing gate report written to: {report_path}")
    raise SystemExit(0 if status == "pass" else 1)

if __name__ == "__main__":
    main()


