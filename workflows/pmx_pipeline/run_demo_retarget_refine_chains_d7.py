from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, make_failed_requirement, now_utc, repo_root_from_workspace, run_stamp

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json
from aiue_unreal.host_bridge import run_host_auto_ue_cli

GATE_ID = "demo_retarget_refine_chains_d7"
DEMO_HOST_KEY = "demo"
REQUIRED_MODE = "editor_rendered"
REQUIRED_EXACT_CHAIN_NAMES = ["root", "Spine", "LeftArm", "RightArm"]

def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE D7 demo retarget chain refinement gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--d5-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()

def default_latest_d5_report_path(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace, REPO_ROOT) / "Saved" / "verification" / "latest_demo_retarget_bootstrap_d5_report.json"

def resolve_d5_report_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"D5 report path does not exist: {candidate}")
    candidate = default_latest_d5_report_path(workspace)
    if candidate.exists():
        return candidate
    raise FileNotFoundError("No latest_demo_retarget_bootstrap_d5_report.json could be resolved for D7.")

def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
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
                "D7 requires a passing D5 retarget bootstrap report.",
                d5_report_path=str(d5_report_path),
                d5_status=d5_report.get("status"),
            )
        )

    fixed_execution_profile = dict((d5_report.get("fixed_execution_profile") or {}))
    engine_evidence = dict(d5_report.get("engine_evidence") or {})
    result_path = output_root / "retarget_refine_chains_result.json"
    host_result = {}
    host_invocation_error = None
    if not failed_requirements:
        try:
            host_payload = run_host_auto_ue_cli(
                workspace_or_config=workspace,
                mode=REQUIRED_MODE,
                command="retarget-author-chains",
                params={
                    "source_ik_rig_asset_path": engine_evidence.get("source_ik_rig_asset_path"),
                    "retargeter_asset_path": engine_evidence.get("retargeter_asset_path"),
                    "target_ik_rig_asset_path": engine_evidence.get("target_ik_rig_asset_path"),
                    "clear_existing_chains": True,
                },
                output_path=str(result_path.resolve()),
                host_key=DEMO_HOST_KEY,
            )
            host_result = dict((host_payload.get("payload") or {}).get("result") or {})
        except Exception as exc:
            host_invocation_error = str(exc)
            if result_path.exists():
                payload = load_json(result_path)
                host_result = dict(payload.get("result") or {})

    authored_chain_names = sorted(
        {
            str(item.get("created_chain_name") or item.get("requested_chain_name") or "")
            for item in (host_result.get("authored_chain_records") or [])
            if str(item.get("created_chain_name") or item.get("requested_chain_name") or "")
        }
    )
    exact_named_mapped_chain_names = sorted(str(item) for item in (host_result.get("exact_named_mapped_chain_names") or []) if str(item))
    missing_required_source = [name for name in REQUIRED_EXACT_CHAIN_NAMES if name not in authored_chain_names]
    missing_required_mapping = [name for name in REQUIRED_EXACT_CHAIN_NAMES if name not in exact_named_mapped_chain_names]

    if not failed_requirements:
        if host_result.get("status") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "retarget_author_chains_host",
                    "The demo host retarget-author-chains command did not complete successfully for D7.",
                    host_invocation_error=host_invocation_error,
                    host_errors=list(host_result.get("errors") or []),
                    result_path=str(result_path.resolve()),
                )
            )
        if int(host_result.get("source_ik_rig_profile", {}).get("chain_count") or 0) < len(REQUIRED_EXACT_CHAIN_NAMES):
            failed_requirements.append(
                make_failed_requirement(
                    "source_chain_count_insufficient",
                    "D7 requires at least the minimal upper-body source retarget chain set to exist.",
                    required_chain_count=len(REQUIRED_EXACT_CHAIN_NAMES),
                    actual_chain_count=int(host_result.get("source_ik_rig_profile", {}).get("chain_count") or 0),
                )
            )
        if missing_required_source:
            failed_requirements.append(
                make_failed_requirement(
                    "required_source_chains_missing",
                    "D7 did not author the minimum required upper-body source chains.",
                    required_chain_names=list(REQUIRED_EXACT_CHAIN_NAMES),
                    authored_chain_names=authored_chain_names,
                    missing_chain_names=missing_required_source,
                )
            )
        if int(host_result.get("exact_named_mapped_chain_count") or 0) < len(REQUIRED_EXACT_CHAIN_NAMES):
            failed_requirements.append(
                make_failed_requirement(
                    "exact_named_mapping_insufficient",
                    "D7 requires exact-named target mappings for the minimum upper-body chain set.",
                    required_exact_chain_count=len(REQUIRED_EXACT_CHAIN_NAMES),
                    actual_exact_chain_count=int(host_result.get("exact_named_mapped_chain_count") or 0),
                    exact_named_mapped_chain_names=exact_named_mapped_chain_names,
                )
            )
        if missing_required_mapping:
            failed_requirements.append(
                make_failed_requirement(
                    "required_exact_mappings_missing",
                    "D7 is still missing exact-named mappings for one or more required upper-body chains.",
                    required_chain_names=list(REQUIRED_EXACT_CHAIN_NAMES),
                    exact_named_mapped_chain_names=exact_named_mapped_chain_names,
                    missing_chain_names=missing_required_mapping,
                )
            )

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(status, failed_requirements, previous_report, previous_report_path, 'd7_first_complete_pass')
    counts = {
        "source_bone_count": int(host_result.get("source_bone_count") or 0),
        "source_chain_count": int(host_result.get("source_ik_rig_profile", {}).get("chain_count") or 0),
        "mapped_chain_count": int(host_result.get("mapped_chain_count") or 0),
        "exact_named_mapped_chain_count": int(host_result.get("exact_named_mapped_chain_count") or 0),
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
            "required_exact_chain_names": list(REQUIRED_EXACT_CHAIN_NAMES),
            "counts": counts,
            "failed_requirements": failed_requirements,
            "engine_evidence": host_result,
            "readiness": {
                "ready_for_retarget_preview": bool(host_result.get("ready_for_animation_retry")),
                "authored_chain_names": authored_chain_names,
                "exact_named_mapped_chain_names": exact_named_mapped_chain_names,
                "missing_required_source_chain_names": missing_required_source,
                "missing_required_exact_mapping_names": missing_required_mapping,
                "recommended_next_step_id": host_result.get("recommended_next_step_id") or "refine_source_chain_mapping",
                "recommended_next_step_reason": host_result.get("recommended_next_step_reason") or "The source PMX rig still needs better exact-named upper-body chain coverage.",
            },
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "d5_report_path": str(d5_report_path.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
                "retarget_refine_chains_result_path": str(result_path.resolve()),
            },
        },
        "aiue_demo_retarget_refine_chains_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_demo_retarget_refine_chains_report",
            notes=["internal_demo_retarget_refine_chains_gate", "demo_host_only", "upper_body_chain_readiness"],
        ),
    )
    report_path = output_root / "d7_demo_retarget_refine_chains_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    print(f"D7 demo retarget refine chains report written to: {report_path}")
    raise SystemExit(0 if status == "pass" else 1)

if __name__ == "__main__":
    main()



