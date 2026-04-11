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
from aiue_t1.q5c_lite import DEFAULT_THRESHOLDS, analyze_q5c_lite

GATE_ID = "volumetric_inspection_q5c_lite"
DEFAULT_Q5BX_LATEST_NAME = "latest_volumetric_fit_spatial_evidence_q5bx_report.json"
FIXED_EXECUTION_PROFILE = {
    "source_gate": "volumetric_fit_spatial_evidence_q5bx",
    "required_package_count": 2,
    "fixture_scope": "p2_echo_hair_fixture",
    **DEFAULT_THRESHOLDS,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE Q5C-lite volumetric inspection gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--q5bx-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def default_latest_q5bx_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, DEFAULT_Q5BX_LATEST_NAME)


def host_result_payload(package_result: dict) -> tuple[dict | None, str]:
    host_result_path = Path(str(((package_result.get("artifacts") or {}).get("q5a_host_result_path")) or "")).expanduser()
    if not str(host_result_path):
        return None, ""
    if not host_result_path.exists():
        return None, str(host_result_path.resolve())
    payload = load_json(host_result_path)
    return dict(payload.get("result") or {}), str(host_result_path.resolve())


def evaluate_package(package_result: dict) -> tuple[dict, list[dict]]:
    package_id = str(package_result.get("package_id") or "")
    failed_requirements: list[dict] = []
    host_result, host_result_path = host_result_payload(package_result)
    if not host_result:
        failed_requirements.append(
            make_failed_requirement(
                "q5c_lite_host_result_missing",
                "Q5C-lite requires the Q5A host result artifact for each passing Q5B.x package.",
                package_id=package_id,
                host_result_path=host_result_path,
            )
        )
        return (
            {
                "package_id": package_id,
                "sample_id": package_result.get("sample_id"),
                "host_blueprint_asset": package_result.get("host_blueprint_asset"),
                "status": "fail",
                "quality_class": "fail",
                "failed_requirements": failed_requirements,
                "artifacts": {"q5a_host_result_path": host_result_path},
            },
            failed_requirements,
        )

    analysis = analyze_q5c_lite(
        host_result=host_result,
        thresholds={key: value for key, value in FIXED_EXECUTION_PROFILE.items() if key not in {"source_gate", "required_package_count", "fixture_scope"}},
    )
    for requirement_id in list(analysis.get("failed_requirements") or []):
        failed_requirements.append(
            make_failed_requirement(
                requirement_id,
                "Q5C-lite detected a local volumetric fit issue for the fixed hair fixture.",
                package_id=package_id,
                quality_class=analysis.get("quality_class"),
            )
        )

    return (
        {
            "package_id": package_id,
            "sample_id": package_result.get("sample_id"),
            "host_blueprint_asset": package_result.get("host_blueprint_asset"),
            "clothing_binding": dict(package_result.get("clothing_binding") or {}),
            "clothing_attach_state": dict(package_result.get("clothing_attach_state") or {}),
            "status": "pass" if not failed_requirements else "fail",
            "quality_class": str(analysis.get("quality_class") or "fail"),
            "embedding_ratio": float(analysis.get("embedding_ratio") or 0.0),
            "floating_ratio": float(analysis.get("floating_ratio") or 0.0),
            "local_fit_volume": float(analysis.get("local_fit_volume") or 0.0),
            "penetration_clusters": list(analysis.get("penetration_clusters") or []),
            "analysis": analysis,
            "failed_requirements": failed_requirements,
            "artifacts": {"q5a_host_result_path": host_result_path},
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
    q5bx_report_path = resolve_report_path(
        args.q5bx_report_path,
        default_latest_q5bx_report_path(workspace),
        "No latest_volumetric_fit_spatial_evidence_q5bx_report.json could be resolved for Q5C-lite.",
    )
    q5bx_report = load_json(q5bx_report_path)
    if q5bx_report.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "q5c_lite_prerequisite_q5bx_failed",
                "Q5C-lite requires a passing Q5B.x richer spatial evidence report.",
                source_report=str(q5bx_report_path.resolve()),
                source_status=q5bx_report.get("status"),
            )
        )

    passing_packages = [dict(item) for item in list(q5bx_report.get("per_package_results") or []) if item.get("status") == "pass"]
    resolved_package_ids = [str(item.get("package_id") or "") for item in passing_packages if item.get("package_id")]
    if len(passing_packages) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
        failed_requirements.append(
            make_failed_requirement(
                "q5c_lite_required_package_count_mismatch",
                "Q5C-lite requires exactly two passing Q5B.x packages for the fixed hair fixture.",
                required_package_count=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                resolved_package_ids=resolved_package_ids,
            )
        )

    per_package_results = []
    for package_result in passing_packages:
        evaluation, package_failures = evaluate_package(package_result)
        per_package_results.append(evaluation)
        failed_requirements.extend(package_failures)

    counts = {
        "required_package_count": int(FIXED_EXECUTION_PROFILE["required_package_count"]),
        "resolved_package_count": len(resolved_package_ids),
        "packages": len(per_package_results),
        "passing_packages": sum(1 for item in per_package_results if item.get("status") == "pass"),
        "packages_without_penetration_clusters": sum(1 for item in per_package_results if not list(item.get("penetration_clusters") or [])),
    }
    status = "pass" if not failed_requirements and counts["packages"] == counts["passing_packages"] == int(FIXED_EXECUTION_PROFILE["required_package_count"]) else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        first_pass_reason="first_complete_q5c_lite_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_report": str(q5bx_report_path.resolve()),
            "fixed_execution_profile": FIXED_EXECUTION_PROFILE,
            "counts": counts,
            "failed_requirements": failed_requirements,
            "resolved_package_ids": resolved_package_ids,
            "per_package_results": per_package_results,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
            },
        },
        "aiue_volumetric_inspection_q5c_lite_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_volumetric_inspection_q5c_lite_report",
            notes=[
                "internal_q5c_lite_gate",
                "local_attach_region_volumetric_evidence",
            ],
        ),
    )
    report_path = output_root / f"{GATE_ID}_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)


if __name__ == "__main__":
    main()
