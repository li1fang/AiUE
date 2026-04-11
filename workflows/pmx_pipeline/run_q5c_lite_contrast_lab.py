from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()
T1_PYTHON_ROOT = REPO_ROOT / "tools" / "t1" / "python"

import sys

if str(T1_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(T1_PYTHON_ROOT))

from _demo_common import default_named_verification_report_path, resolve_report_path
from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, make_failed_requirement, now_utc, write_report_pair

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config
from aiue_t1.q5c_contrast import generate_q5c_contrast_suite
from aiue_t1.q5c_lite_debug import render_q5c_lite_debug_image


GATE_ID = "q5c_lite_contrast_lab"
DEFAULT_Q5C_LATEST_NAME = "latest_volumetric_inspection_q5c_lite_report.json"
FIXED_EXECUTION_PROFILE = {
    "source_gate": "volumetric_inspection_q5c_lite",
    "required_reference_cases": ["baseline_current", "best_pass_reference", "closest_fail_reference"],
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE Q5C-lite contrast lab.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--q5c-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def default_latest_q5c_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_Q5C_LATEST_NAME)


def host_result_payload(package_result: dict) -> tuple[dict | None, str]:
    host_result_path_raw = str(((package_result.get("artifacts") or {}).get("q5a_host_result_path")) or "").strip()
    if not host_result_path_raw:
        return None, ""
    host_result_path = Path(host_result_path_raw).expanduser()
    if not host_result_path.exists():
        return None, str(host_result_path.resolve())
    payload = load_json(host_result_path)
    return dict(payload.get("result") or {}), str(host_result_path.resolve())


def evaluate_package(package_result: dict, *, output_root: Path) -> tuple[dict, list[dict]]:
    package_id = str(package_result.get("package_id") or "")
    failed_requirements: list[dict] = []
    host_result, host_result_path = host_result_payload(package_result)
    if not host_result:
        failed_requirements.append(
            make_failed_requirement(
                "q5c_contrast_host_result_missing",
                "Q5C contrast lab requires the Q5A host result artifact for each package.",
                package_id=package_id,
                host_result_path=host_result_path,
            )
        )
        return (
            {
                "package_id": package_id,
                "status": "fail",
                "failed_requirements": failed_requirements,
                "artifacts": {"q5a_host_result_path": host_result_path},
            },
            failed_requirements,
        )

    suite = generate_q5c_contrast_suite(host_result=host_result)
    selected_cases = []
    debug_image_paths = []
    for case in list(suite.get("selected_cases") or []):
        case_id = str(case.get("case_id") or "case")
        debug_artifact = render_q5c_lite_debug_image(
            package_id=f"{package_id}:{case_id}",
            analysis=dict(case.get("analysis") or {}),
            risk_context={
                "risk_band": case.get("risk_band"),
                "risk_reason": case.get("risk_reason"),
                "closest_margin_metric": case.get("closest_margin_metric"),
                "closest_margin_value": case.get("closest_margin_value"),
                "margin_to_failure_by_metric": dict(case.get("margin_to_failure_by_metric") or {}),
            },
            output_path=output_root / "contrast_debug_images" / package_id / f"{case_id}.png",
        )
        debug_image_path = str(debug_artifact.get("image_path") or "")
        if debug_image_path:
            debug_image_paths.append(debug_image_path)
        selected_cases.append(
            {
                "case_id": case_id,
                "delta_z": float(case.get("delta_z") or 0.0),
                "status": str(case.get("status") or ""),
                "fit_diagnostic_class": str(case.get("fit_diagnostic_class") or ""),
                "risk_band": str(case.get("risk_band") or ""),
                "risk_reason": str(case.get("risk_reason") or ""),
                "closest_margin_metric": str(case.get("closest_margin_metric") or ""),
                "closest_margin_value": float(case.get("closest_margin_value") or 0.0),
                "margin_to_failure_by_metric": dict(case.get("margin_to_failure_by_metric") or {}),
                "analysis": dict(case.get("analysis") or {}),
                "artifacts": {
                    "debug_image_path": debug_image_path,
                },
            }
        )

    required_case_ids = set(FIXED_EXECUTION_PROFILE["required_reference_cases"])
    selected_case_ids = {str(item.get("case_id") or "") for item in selected_cases}
    missing_required_cases = sorted(required_case_ids - selected_case_ids)
    if missing_required_cases:
        failed_requirements.append(
            make_failed_requirement(
                "q5c_contrast_reference_missing",
                "Q5C contrast lab requires baseline, best-pass, and closest-fail references.",
                package_id=package_id,
                missing_case_ids=missing_required_cases,
            )
        )

    status = "pass" if not failed_requirements else "fail"
    return (
        {
            "package_id": package_id,
            "sample_id": package_result.get("sample_id"),
            "host_blueprint_asset": package_result.get("host_blueprint_asset"),
            "status": status,
            "baseline_case_id": str(suite.get("baseline_case_id") or ""),
            "selected_case_ids": list(suite.get("selected_case_ids") or []),
            "search_summary": dict(suite.get("search_summary") or {}),
            "case_results": selected_cases,
            "failed_requirements": failed_requirements,
            "artifacts": {
                "q5a_host_result_path": host_result_path,
                "debug_image_paths": debug_image_paths,
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
    q5c_report_path = resolve_report_path(
        args.q5c_report_path,
        default_latest_q5c_report_path(workspace),
        "No latest_volumetric_inspection_q5c_lite_report.json could be resolved for Q5C contrast lab.",
    )
    q5c_report = load_json(q5c_report_path)
    if str(q5c_report.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "q5c_contrast_prerequisite_report_not_pass",
                "Q5C contrast lab requires a passing latest_volumetric_inspection_q5c_lite_report.json.",
                source_report=str(q5c_report_path.resolve()),
                source_status=str(q5c_report.get("status") or ""),
            )
        )
    if not list(q5c_report.get("per_package_results") or []):
        failed_requirements.append(
            make_failed_requirement(
                "q5c_contrast_source_report_empty",
                "Q5C contrast lab requires a non-empty Q5C-lite report.",
                source_report=str(q5c_report_path.resolve()),
            )
        )

    passing_packages = [
        dict(item)
        for item in list(q5c_report.get("per_package_results") or [])
        if item.get("package_id") and str(item.get("status") or "") == "pass"
    ]
    resolved_package_ids = [str(item.get("package_id") or "") for item in passing_packages if item.get("package_id")]

    per_package_results = []
    debug_image_paths = []
    for package_result in passing_packages:
        evaluation, package_failures = evaluate_package(package_result, output_root=output_root)
        per_package_results.append(evaluation)
        failed_requirements.extend(package_failures)
        debug_image_paths.extend(list((evaluation.get("artifacts") or {}).get("debug_image_paths") or []))

    counts = {
        "packages": len(per_package_results),
        "passing_packages": sum(1 for item in per_package_results if item.get("status") == "pass"),
        "packages_with_best_pass_reference": sum(
            1
            for item in per_package_results
            if "best_pass_reference" in set(item.get("selected_case_ids") or [])
        ),
        "packages_with_closest_fail_reference": sum(
            1
            for item in per_package_results
            if "closest_fail_reference" in set(item.get("selected_case_ids") or [])
        ),
        "debug_images": len(debug_image_paths),
    }
    status = "pass" if not failed_requirements and counts["packages"] == counts["passing_packages"] else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        first_pass_reason="first_complete_q5c_contrast_lab_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_report": str(q5c_report_path.resolve()),
            "fixed_execution_profile": FIXED_EXECUTION_PROFILE,
            "counts": counts,
            "failed_requirements": failed_requirements,
            "resolved_package_ids": resolved_package_ids,
            "per_package_results": per_package_results,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "debug_image_paths": debug_image_paths,
            },
        },
        "aiue_q5c_lite_contrast_lab_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_q5c_lite_contrast_lab_report",
            notes=[
                "internal_q5c_contrast_lab",
                "risk_context_replayable_reference_cases",
            ],
        ),
    )
    report_path = output_root / f"{GATE_ID}_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)


if __name__ == "__main__":
    main()
