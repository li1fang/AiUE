from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json

GATE_ID = "demo_composition_quality_gate_q2"
DEFAULT_D12_LATEST_NAME = "latest_demo_cross_bundle_regression_d12_report.json"
DEFAULT_D11_LATEST_NAME = "latest_demo_animation_stability_regression_d11_report.json"
DEFAULT_Q1_LATEST_NAME = "latest_demo_shot_quality_gate_q1_report.json"
FIXED_EXECUTION_PROFILE = {
    "minimum_subject_side_margin_ratio": 0.05,
    "minimum_subject_top_margin_ratio": 0.12,
    "maximum_subject_center_offset_ratio": 0.28,
    "maximum_pair_center_drift_pixels": 24.0,
    "maximum_pair_subject_coverage_delta": 0.03,
    "weapon_phase_min_screen_coverage": 0.02,
    "required_weapon_visible_pairs_per_case": 2,
    "required_weapon_visible_phases_per_case": 2,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE Q2 demo composition quality gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--d12-report-path")
    parser.add_argument("--d11-report-path")
    parser.add_argument("--q1-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def repo_root_from_workspace(workspace: dict) -> Path:
    return Path(workspace["paths"].get("aiue_repo_root") or REPO_ROOT).expanduser().resolve()


def default_output_root(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / f"{GATE_ID}_{run_stamp()}"


def default_latest_report_path(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / f"latest_{GATE_ID}_report.json"


def default_latest_d12_report_path(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / DEFAULT_D12_LATEST_NAME


def default_latest_d11_report_path(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / DEFAULT_D11_LATEST_NAME


def default_latest_q1_report_path(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / DEFAULT_Q1_LATEST_NAME


def make_failed_requirement(requirement_id: str, message: str, **details) -> dict:
    payload = {"id": requirement_id, "message": message}
    payload.update(details)
    return payload


def resolve_source_report_path(workspace: dict, d12_report_path: str | None, d11_report_path: str | None) -> Path:
    if d12_report_path:
        candidate = Path(d12_report_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"D12 report path does not exist: {candidate}")
    default_d12 = default_latest_d12_report_path(workspace)
    if default_d12.exists():
        return default_d12
    if d11_report_path:
        candidate = Path(d11_report_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"D11 report path does not exist: {candidate}")
    default_d11 = default_latest_d11_report_path(workspace)
    if default_d11.exists():
        return default_d11
    raise FileNotFoundError("No latest_demo_cross_bundle_regression_d12_report.json or latest_demo_animation_stability_regression_d11_report.json could be resolved for Q2.")


def resolve_q1_report_path(workspace: dict, q1_report_path: str | None) -> Path:
    if q1_report_path:
        candidate = Path(q1_report_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Q1 report path does not exist: {candidate}")
    candidate = default_latest_q1_report_path(workspace)
    if candidate.exists():
        return candidate
    raise FileNotFoundError("No latest_demo_shot_quality_gate_q1_report.json could be resolved for Q2.")


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
        payload["reason"] = "q2_first_complete_pass"
        return payload
    if status != "pass" and current_failed_ids and previous_status != "pass" and current_failed_ids == previous_failed_ids:
        payload["should_discuss"] = True
        payload["reason"] = "same_failed_requirement_two_rounds"
        payload["repeated_failed_requirement_ids"] = current_failed_ids
    return payload


def rect_dict(payload: dict | None) -> dict:
    return dict(payload or {})


def subject_rect_metrics(phase_report: dict, image_width: int, image_height: int) -> dict:
    subject_coverage = dict(phase_report.get("subject_coverage") or {})
    screen_rect = rect_dict(subject_coverage.get("screen_rect"))
    min_x = float(screen_rect.get("min_x") or 0.0)
    max_x = float(screen_rect.get("max_x") or 0.0)
    min_y = float(screen_rect.get("min_y") or 0.0)
    max_y = float(screen_rect.get("max_y") or 0.0)
    width = max(0.0, max_x - min_x)
    height = max(0.0, max_y - min_y)
    center_x = min_x + (width * 0.5)
    center_y = min_y + (height * 0.5)
    left_margin = min_x
    right_margin = max(0.0, float(image_width) - max_x)
    top_margin = min_y
    bottom_margin = max(0.0, float(image_height) - max_y)
    horizontal_center_offset_ratio = abs(center_x - (float(image_width) * 0.5)) / float(image_width) if image_width else 1.0
    return {
        "screen_rect": {
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "width": width,
            "height": height,
        },
        "center": {"x": center_x, "y": center_y},
        "margins": {
            "left": left_margin,
            "right": right_margin,
            "top": top_margin,
            "bottom": bottom_margin,
        },
        "horizontal_center_offset_ratio": horizontal_center_offset_ratio,
        "subject_screen_coverage": float(phase_report.get("subject_screen_coverage") or subject_coverage.get("coverage_ratio") or 0.0),
        "weapon_screen_coverage": float(phase_report.get("weapon_screen_coverage") or 0.0),
    }


def evaluate_phase_composition(phase_report: dict, image_width: int, image_height: int) -> dict:
    metrics = subject_rect_metrics(phase_report, image_width=image_width, image_height=image_height)
    failed_checks = []
    side_margin_min = FIXED_EXECUTION_PROFILE["minimum_subject_side_margin_ratio"] * float(image_width)
    top_margin_min = FIXED_EXECUTION_PROFILE["minimum_subject_top_margin_ratio"] * float(image_height)
    if metrics["screen_rect"]["width"] <= 0.0 or metrics["screen_rect"]["height"] <= 0.0:
        failed_checks.append("subject_rect_missing")
    if metrics["margins"]["left"] < side_margin_min:
        failed_checks.append("left_margin_too_small")
    if metrics["margins"]["right"] < side_margin_min:
        failed_checks.append("right_margin_too_small")
    if metrics["margins"]["top"] < top_margin_min:
        failed_checks.append("top_margin_too_small")
    if metrics["horizontal_center_offset_ratio"] > FIXED_EXECUTION_PROFILE["maximum_subject_center_offset_ratio"]:
        failed_checks.append("subject_center_offset_too_large")
    return {
        "status": "pass" if not failed_checks else "fail",
        "failed_checks": failed_checks,
        "metrics": metrics,
    }


def evaluate_pair_quality(pair_shot: dict, image_width: int, image_height: int) -> dict:
    before_phase = dict(pair_shot.get("before") or {})
    after_phase = dict(pair_shot.get("after") or {})
    before_eval = evaluate_phase_composition(before_phase, image_width=image_width, image_height=image_height)
    after_eval = evaluate_phase_composition(after_phase, image_width=image_width, image_height=image_height)
    failed_checks = []
    if before_eval["status"] != "pass":
        failed_checks.append("before_phase_composition_fail")
    if after_eval["status"] != "pass":
        failed_checks.append("after_phase_composition_fail")

    before_center = before_eval["metrics"]["center"]
    after_center = after_eval["metrics"]["center"]
    center_drift_pixels = float(
        math.hypot(
            float(after_center["x"]) - float(before_center["x"]),
            float(after_center["y"]) - float(before_center["y"]),
        )
    )
    if center_drift_pixels > FIXED_EXECUTION_PROFILE["maximum_pair_center_drift_pixels"]:
        failed_checks.append("pair_center_drift_too_large")

    subject_coverage_delta = abs(
        float(after_eval["metrics"]["subject_screen_coverage"]) - float(before_eval["metrics"]["subject_screen_coverage"])
    )
    if subject_coverage_delta > FIXED_EXECUTION_PROFILE["maximum_pair_subject_coverage_delta"]:
        failed_checks.append("pair_subject_coverage_drift_too_large")

    weapon_threshold = float(FIXED_EXECUTION_PROFILE["weapon_phase_min_screen_coverage"])
    visible_phases = []
    for phase_name, phase_eval in (("before", before_eval), ("after", after_eval)):
        if float(phase_eval["metrics"]["weapon_screen_coverage"]) >= weapon_threshold:
            visible_phases.append(phase_name)
    if not visible_phases:
        failed_checks.append("weapon_not_visible_in_pair")

    return {
        "shot_id": pair_shot.get("shot_id"),
        "camera_id": pair_shot.get("camera_id"),
        "status": "pass" if not failed_checks else "fail",
        "failed_checks": failed_checks,
        "before": before_eval,
        "after": after_eval,
        "center_drift_pixels": center_drift_pixels,
        "subject_coverage_delta": subject_coverage_delta,
        "weapon_visible_phases": visible_phases,
    }


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict] = []
    source_report_path = resolve_source_report_path(workspace, args.d12_report_path, args.d11_report_path)
    source_report = load_json(source_report_path)
    quality_subject_report, source_metadata = extract_quality_subject_report(source_report, source_report_path)
    q1_report_path = resolve_q1_report_path(workspace, args.q1_report_path)
    q1_report = load_json(q1_report_path)

    if quality_subject_report.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "q2_source_prerequisite",
                "Q2 requires a passing D11-like source report before enforcing composition quality.",
                source_report_path=str(source_report_path.resolve()),
                source_report_status=quality_subject_report.get("status"),
                source_report_gate_id=quality_subject_report.get("gate_id"),
            )
        )

    if q1_report.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "q1_prerequisite",
                "Q2 requires a passing Q1 shot-quality report before enforcing stricter composition and weapon rules.",
                q1_report_path=str(q1_report_path.resolve()),
                q1_status=q1_report.get("status"),
            )
        )

    q1_source_report_path = str(((q1_report.get("source_report") or {}).get("source_report_path")) or "")
    if q1_source_report_path and Path(q1_source_report_path).resolve() != source_report_path.resolve():
        failed_requirements.append(
            make_failed_requirement(
                "q1_source_mismatch",
                "Q2 requires the Q1 prerequisite to reference the same source report path.",
                q1_source_report_path=q1_source_report_path,
                q2_source_report_path=str(source_report_path.resolve()),
            )
        )

    fixed_execution_profile = dict(FIXED_EXECUTION_PROFILE)
    source_profile = dict(quality_subject_report.get("fixed_execution_profile") or {})
    capture_width = int(source_profile.get("capture_width") or 1280)
    capture_height = int(source_profile.get("capture_height") or 720)
    fixed_execution_profile["capture_width"] = capture_width
    fixed_execution_profile["capture_height"] = capture_height
    fixed_execution_profile["source_report_kind"] = source_metadata["source_report_kind"]
    fixed_execution_profile["source_gate_id"] = source_metadata["source_gate_id"]

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
                pair_results = [
                    evaluate_pair_quality(pair_shot, image_width=capture_width, image_height=capture_height)
                    for pair_shot in list(case_result.get("shots") or [])
                ]
                weapon_visible_pair_count = sum(1 for item in pair_results if item.get("weapon_visible_phases"))
                weapon_visible_phase_count = sum(len(list(item.get("weapon_visible_phases") or [])) for item in pair_results)
                failing_pair_ids = [item.get("shot_id") for item in pair_results if item.get("status") != "pass"]
                case_failed_requirements = []
                if failing_pair_ids:
                    case_failed_requirements.append(
                        make_failed_requirement(
                            "case_pair_quality_failure",
                            "Every shot pair must satisfy the strict Q2 composition gate.",
                            case_id=case_result.get("case_id"),
                            failing_pair_ids=failing_pair_ids,
                        )
                    )
                if weapon_visible_pair_count < int(FIXED_EXECUTION_PROFILE["required_weapon_visible_pairs_per_case"]):
                    case_failed_requirements.append(
                        make_failed_requirement(
                            "weapon_pair_visibility_insufficient",
                            "Q2 requires weapon visibility in enough distinct shot pairs for each case.",
                            case_id=case_result.get("case_id"),
                            required_weapon_visible_pairs=int(FIXED_EXECUTION_PROFILE["required_weapon_visible_pairs_per_case"]),
                            actual_weapon_visible_pairs=weapon_visible_pair_count,
                        )
                    )
                if weapon_visible_phase_count < int(FIXED_EXECUTION_PROFILE["required_weapon_visible_phases_per_case"]):
                    case_failed_requirements.append(
                        make_failed_requirement(
                            "weapon_phase_visibility_insufficient",
                            "Q2 requires enough weapon-visible phases within each case.",
                            case_id=case_result.get("case_id"),
                            required_weapon_visible_phases=int(FIXED_EXECUTION_PROFILE["required_weapon_visible_phases_per_case"]),
                            actual_weapon_visible_phases=weapon_visible_phase_count,
                            weapon_phase_min_screen_coverage=float(FIXED_EXECUTION_PROFILE["weapon_phase_min_screen_coverage"]),
                        )
                    )
                evaluated_round["per_case_results"].append(
                    {
                        "family": case_result.get("family"),
                        "case_id": case_result.get("case_id"),
                        "animation_asset_path": case_result.get("animation_asset_path"),
                        "status": "pass" if not case_failed_requirements else "fail",
                        "pair_results": pair_results,
                        "weapon_visible_pair_count": weapon_visible_pair_count,
                        "weapon_visible_phase_count": weapon_visible_phase_count,
                        "failed_requirements": case_failed_requirements,
                    }
                )

            failing_case_ids = [item.get("case_id") for item in evaluated_round["per_case_results"] if item.get("status") != "pass"]
            if failing_case_ids:
                evaluated_round["failed_requirements"].append(
                    make_failed_requirement(
                        "round_composition_failure",
                        "All cases in a Q2 round must satisfy the strict composition and weapon-visibility gate.",
                        round_index=evaluated_round["round_index"],
                        failing_case_ids=failing_case_ids,
                    )
                )
                evaluated_round["status"] = "fail"
            per_round_results.append(evaluated_round)

    phase_results = []
    pair_results = []
    for round_result in per_round_results:
        for case_result in list(round_result.get("per_case_results") or []):
            for pair_result in list(case_result.get("pair_results") or []):
                pair_payload = dict(pair_result)
                pair_payload["round_index"] = round_result.get("round_index")
                pair_payload["case_id"] = case_result.get("case_id")
                pair_payload["family"] = case_result.get("family")
                pair_results.append(pair_payload)
                for phase_key in ("before", "after"):
                    phase_payload = dict(pair_result.get(phase_key) or {})
                    phase_payload["round_index"] = round_result.get("round_index")
                    phase_payload["case_id"] = case_result.get("case_id")
                    phase_payload["family"] = case_result.get("family")
                    phase_payload["shot_id"] = pair_result.get("shot_id")
                    phase_payload["phase"] = phase_key
                    phase_results.append(phase_payload)

    failing_round_indices = [item.get("round_index") for item in per_round_results if item.get("status") != "pass"]
    if failing_round_indices:
        failed_requirements.append(
            make_failed_requirement(
                "q2_round_failure",
                "Every evaluated round must satisfy the Q2 composition gate.",
                failing_round_indices=failing_round_indices,
            )
        )

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(status, failed_requirements, previous_report, previous_report_path)
    counts = {
        "evaluated_rounds": len(per_round_results),
        "passing_rounds": sum(1 for item in per_round_results if item.get("status") == "pass"),
        "evaluated_cases": sum(len(list(item.get("per_case_results") or [])) for item in per_round_results),
        "passing_cases": sum(
            1 for round_result in per_round_results for case_result in list(round_result.get("per_case_results") or []) if case_result.get("status") == "pass"
        ),
        "evaluated_shot_pairs": len(pair_results),
        "passing_shot_pairs": sum(1 for item in pair_results if item.get("status") == "pass"),
        "evaluated_phase_shots": len(phase_results),
        "passing_phase_shots": sum(1 for item in phase_results if item.get("status") == "pass"),
        "weapon_visible_pairs": sum(1 for item in pair_results if item.get("weapon_visible_phases")),
        "weapon_visible_phases": sum(len(list(item.get("weapon_visible_phases") or [])) for item in pair_results),
        "max_pair_center_drift_pixels": max((float(item.get("center_drift_pixels") or 0.0) for item in pair_results), default=0.0),
        "max_pair_subject_coverage_delta": max((float(item.get("subject_coverage_delta") or 0.0) for item in pair_results), default=0.0),
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
            "fixed_execution_profile": fixed_execution_profile,
            "source_report": source_metadata,
            "q1_report_path": str(q1_report_path.resolve()),
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
        "aiue_demo_composition_quality_gate_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_demo_composition_quality_gate_report",
            notes=["internal_demo_composition_quality_gate", "strict_weapon_visibility", "q1_prerequisite"],
        ),
    )
    report_path = output_root / "q2_demo_composition_quality_gate_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    print(f"Q2 demo composition quality gate report written to: {report_path}")
    raise SystemExit(0 if status == "pass" else 1)


if __name__ == "__main__":
    main()
