from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _demo_common import default_named_verification_report_path, resolve_report_path, run_host_command_result
from _gate_common import (
    build_discussion_signal,
    default_latest_report_path,
    default_output_root,
    make_failed_requirement,
    now_utc,
)
from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json

GATE_ID = "demo_retarget_author_chains_d6"
DEMO_HOST_KEY = "demo"
REQUIRED_MODE = "editor_rendered"

def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE D6 demo retarget chain authoring gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--d5-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()

def default_latest_d5_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, "latest_demo_retarget_bootstrap_d5_report.json")


def resolve_d5_report_path(workspace: dict, explicit_path: str | None) -> Path:
    return resolve_report_path(
        explicit_path,
        default_latest_d5_report_path(workspace),
        "No latest_demo_retarget_bootstrap_d5_report.json could be resolved for D6.",
    )


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = (
        Path(args.latest_report_path).expanduser().resolve()
        if args.latest_report_path
        else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    )
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict] = []
    d5_report_path = resolve_d5_report_path(workspace, args.d5_report_path)
    d5_report = load_json(d5_report_path)
    if d5_report.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "d5_prerequisite",
                "D6 requires a passing D5 retarget bootstrap report.",
                d5_report_path=str(d5_report_path),
                d5_status=d5_report.get("status"),
            )
        )

    fixed_execution_profile = dict((d5_report.get("fixed_execution_profile") or {}))
    engine_evidence = dict(d5_report.get("engine_evidence") or {})
    result_path = output_root / "retarget_author_chains_result.json"
    host_result = {}
    host_invocation_error = None
    if not failed_requirements:
        host_result, host_invocation_error, result_path = run_host_command_result(
            workspace=workspace,
            mode=REQUIRED_MODE,
            command="retarget-author-chains",
            params={
                "source_ik_rig_asset_path": engine_evidence.get("source_ik_rig_asset_path"),
                "retargeter_asset_path": engine_evidence.get("retargeter_asset_path"),
                "target_ik_rig_asset_path": engine_evidence.get("target_ik_rig_asset_path"),
                "clear_existing_chains": True,
            },
            output_path=result_path,
            host_key=DEMO_HOST_KEY,
        )

    if not failed_requirements:
        if host_result.get("status") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "retarget_author_chains_host",
                    "The demo host retarget-author-chains command did not complete successfully.",
                    host_invocation_error=host_invocation_error,
                    host_errors=list(host_result.get("errors") or []),
                    result_path=str(result_path.resolve()),
                )
            )
        if int(host_result.get("source_ik_rig_profile", {}).get("chain_count") or 0) <= 0:
            failed_requirements.append(
                make_failed_requirement(
                    "source_chain_count_zero",
                    "D6 did not author any source retarget chains on the PMX source IK Rig.",
                    source_ik_rig_asset_path=host_result.get("source_ik_rig_asset_path"),
                    source_bone_name_source=host_result.get("source_bone_name_source"),
                )
            )

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        first_pass_reason="d6_first_complete_pass",
    )
    counts = {
        "source_bone_count": int(host_result.get("source_bone_count") or 0),
        "source_chain_count": int(host_result.get("source_ik_rig_profile", {}).get("chain_count") or 0),
        "target_chain_count": int(host_result.get("target_ik_rig_profile", {}).get("chain_count") or 0),
        "mapped_chain_count": int(host_result.get("mapped_chain_count") or 0),
        "authored_chain_count": len(list(host_result.get("authored_chain_records") or [])),
    }
    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": args.workspace_config,
            "host_key": DEMO_HOST_KEY,
            "package_id": d5_report.get("package_id"),
            "sample_id": d5_report.get("sample_id"),
            "host_blueprint_asset": d5_report.get("host_blueprint_asset"),
            "fixed_execution_profile": fixed_execution_profile,
            "counts": counts,
            "failed_requirements": failed_requirements,
            "engine_evidence": host_result,
            "readiness": {
                "ready_for_animation_retry": bool((host_result.get("mapped_chain_count") or 0) > 0),
                "recommended_next_step_id": host_result.get("recommended_next_step_id") or "inspect_source_chain_mapping",
                "recommended_next_step_reason": host_result.get("recommended_next_step_reason") or "The source rig chains need more inspection before retrying animation preview.",
            },
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "d5_report_path": str(d5_report_path.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
                "retarget_author_chains_result_path": str(result_path.resolve()),
            },
        },
        "aiue_demo_retarget_author_chains_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_demo_retarget_author_chains_report",
            notes=["internal_demo_retarget_author_chains_gate", "demo_host_only", "source_chain_authoring_evidence"],
        ),
    )
    report_path = output_root / "d6_demo_retarget_author_chains_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    print(f"D6 demo retarget author chains report written to: {report_path}")
    raise SystemExit(0 if status == "pass" else 1)


if __name__ == "__main__":
    main()
