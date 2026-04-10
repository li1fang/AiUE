from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json
from aiue_unreal.host_bridge import run_host_auto_ue_cli

GATE_ID = "demo_retarget_bootstrap_d5"
DEMO_HOST_KEY = "demo"
REQUIRED_MODE = "editor_rendered"
DEFAULT_LEVEL_PATH = "/Game/Levels/DefaultLevel"
DEFAULT_ANIMATION_ASSET_PATH = "/Game/CombatMagicAnims/Demo/Mannequins/Anims/Unarmed/Attack/MM_Attack_01"
FIXED_EXECUTION_PROFILE = {
    "host_key": DEMO_HOST_KEY,
    "mode": REQUIRED_MODE,
    "level_path": DEFAULT_LEVEL_PATH,
    "animation_asset_path": DEFAULT_ANIMATION_ASSET_PATH,
    "purpose": "retarget_bootstrap_only",
    "spawn_location": {"x": 0.0, "y": 0.0, "z": 120.0},
    "spawn_rotation": {"pitch": 0.0, "yaw": 180.0, "roll": 0.0},
    "settle_delay_seconds": 0.2,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE D5 demo retarget bootstrap gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--d4-report-path")
    parser.add_argument("--package-id")
    parser.add_argument("--animation-asset-path")
    parser.add_argument("--target-ik-rig-asset-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def repo_root_from_workspace(workspace: dict) -> Path:
    return Path(workspace["paths"].get("aiue_repo_root") or REPO_ROOT).expanduser().resolve()


def default_output_root(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / f"{GATE_ID}_{run_stamp()}"


def default_latest_report_path(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / f"latest_{GATE_ID}_report.json"


def default_latest_d4_report_path(workspace: dict) -> Path:
    return repo_root_from_workspace(workspace) / "Saved" / "verification" / "latest_demo_retarget_preflight_d4_report.json"


def sanitize_segment(value: str) -> str:
    import re

    cleaned = re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff]+", "_", str(value).strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "asset"


def make_failed_requirement(requirement_id: str, message: str, **details) -> dict:
    payload = {
        "id": requirement_id,
        "message": message,
    }
    payload.update(details)
    return payload


def resolve_d4_report_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"D4 report path does not exist: {candidate}")
    candidate = default_latest_d4_report_path(workspace)
    if candidate.exists():
        return candidate
    raise FileNotFoundError("No latest_demo_retarget_preflight_d4_report.json could be resolved for D5.")


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
        payload["reason"] = "d5_first_complete_pass"
        return payload
    if status != "pass" and current_failed_ids and previous_status != "pass" and current_failed_ids == previous_failed_ids:
        payload["should_discuss"] = True
        payload["reason"] = "same_failed_requirement_two_rounds"
        payload["repeated_failed_requirement_ids"] = current_failed_ids
    return payload


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict] = []
    d4_report_path = resolve_d4_report_path(workspace, args.d4_report_path)
    d4_report = load_json(d4_report_path)
    if d4_report.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "d4_prerequisite",
                "D5 requires a passing D4 retarget preflight report.",
                d4_report_path=str(d4_report_path),
                d4_status=d4_report.get("status"),
            )
        )

    package_id = str(args.package_id or d4_report.get("package_id") or "")
    sample_id = str(d4_report.get("sample_id") or "")
    host_blueprint_asset = str(d4_report.get("host_blueprint_asset") or "")
    if args.package_id and args.package_id != package_id:
        failed_requirements.append(
            make_failed_requirement(
                "package_override_mismatch",
                "The requested package id does not match the latest D4 context.",
                requested_package_id=args.package_id,
                d4_package_id=package_id,
            )
        )

    fixed_execution_profile = dict(FIXED_EXECUTION_PROFILE)
    fixed_execution_profile["level_path"] = str(d4_report.get("level_path") or FIXED_EXECUTION_PROFILE["level_path"])
    fixed_execution_profile["animation_asset_path"] = str(
        args.animation_asset_path
        or (d4_report.get("fixed_execution_profile") or {}).get("animation_asset_path")
        or FIXED_EXECUTION_PROFILE["animation_asset_path"]
    )
    preferred_target_ik_rig_asset_path = str(
        args.target_ik_rig_asset_path
        or ((d4_report.get("engine_evidence") or {}).get("retarget_tooling") or {}).get("matching_target_ik_rigs", [{}])[0].get("object_path")
        or ""
    )

    asset_root = str(workspace["paths"]["asset_root"]).rstrip("/")
    target_slug = sanitize_segment(preferred_target_ik_rig_asset_path.rsplit("/", 1)[-1].split(".", 1)[0] if preferred_target_ik_rig_asset_path else "target")
    source_ik_rig_asset_path = f"{asset_root}/Retarget/Source/IK_{sanitize_segment(package_id)}"
    retargeter_asset_path = f"{asset_root}/Retarget/Demo/RTG_{sanitize_segment(package_id)}_to_{target_slug}"

    host_result_path = output_root / "retarget_bootstrap_result.json"
    host_result = {}
    host_invocation_error = None
    if not failed_requirements:
        try:
            host_payload = run_host_auto_ue_cli(
                workspace_or_config=workspace,
                mode=REQUIRED_MODE,
                command="retarget-bootstrap",
                params={
                    "package_id": package_id,
                    "sample_id": sample_id,
                    "host_blueprint_asset_path": host_blueprint_asset,
                    "level_path": fixed_execution_profile["level_path"],
                    "location": fixed_execution_profile["spawn_location"],
                    "rotation": fixed_execution_profile["spawn_rotation"],
                    "settle_delay_seconds": fixed_execution_profile["settle_delay_seconds"],
                    "animation_asset_path": fixed_execution_profile["animation_asset_path"],
                    "target_ik_rig_asset_path": preferred_target_ik_rig_asset_path,
                    "source_ik_rig_asset_path": source_ik_rig_asset_path,
                    "retargeter_asset_path": retargeter_asset_path,
                },
                output_path=str(host_result_path.resolve()),
                host_key=DEMO_HOST_KEY,
            )
            host_result = dict((host_payload.get("payload") or {}).get("result") or {})
        except Exception as exc:
            host_invocation_error = str(exc)
            if host_result_path.exists():
                payload = load_json(host_result_path)
                host_result = dict(payload.get("result") or {})

    if not failed_requirements:
        if host_result.get("status") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "retarget_bootstrap_host",
                    "The demo host retarget-bootstrap command did not complete successfully.",
                    host_invocation_error=host_invocation_error,
                    host_errors=list(host_result.get("errors") or []),
                    result_path=str(host_result_path.resolve()),
                )
            )
        if not host_result.get("source_ik_rig_asset_path"):
            failed_requirements.append(
                make_failed_requirement(
                    "source_ik_rig_missing",
                    "D5 did not create or load a source IK Rig for the imported PMX skeleton.",
                    requested_source_ik_rig_asset_path=source_ik_rig_asset_path,
                )
            )
        if not host_result.get("retargeter_asset_path"):
            failed_requirements.append(
                make_failed_requirement(
                    "retargeter_asset_missing",
                    "D5 did not create or load the PMX-to-demo IK Retargeter asset.",
                    requested_retargeter_asset_path=retargeter_asset_path,
                )
            )
        if not host_result.get("source_ik_rig_assigned"):
            failed_requirements.append(
                make_failed_requirement(
                    "source_ik_rig_unassigned",
                    "The created retargeter does not have the PMX source IK Rig assigned.",
                    source_ik_rig_asset_path=host_result.get("source_ik_rig_asset_path"),
                    retargeter_asset_path=host_result.get("retargeter_asset_path"),
                )
            )
        if not host_result.get("target_ik_rig_assigned"):
            failed_requirements.append(
                make_failed_requirement(
                    "target_ik_rig_unassigned",
                    "The created retargeter does not have the target demo IK Rig assigned.",
                    target_ik_rig_asset_path=host_result.get("target_ik_rig_asset_path"),
                    retargeter_asset_path=host_result.get("retargeter_asset_path"),
                )
            )

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(status, failed_requirements, previous_report, previous_report_path)
    counts = {
        "requested_packages": 1 if package_id else 0,
        "resolved_packages": 1 if package_id else 0,
        "source_chain_count": int(((host_result.get("source_ik_rig_profile") or {}).get("chain_count")) or 0),
        "target_chain_count": int(((host_result.get("target_ik_rig_profile") or {}).get("chain_count")) or 0),
        "mapped_chain_count": int(host_result.get("mapped_chain_count") or 0),
        "operation_count": int(host_result.get("operation_count") or 0),
    }
    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": args.workspace_config,
            "host_key": DEMO_HOST_KEY,
            "level_path": fixed_execution_profile["level_path"],
            "package_id": package_id,
            "sample_id": sample_id,
            "host_blueprint_asset": host_blueprint_asset,
            "fixed_execution_profile": {
                **fixed_execution_profile,
                "preferred_target_ik_rig_asset_path": preferred_target_ik_rig_asset_path,
                "source_ik_rig_asset_path": source_ik_rig_asset_path,
                "retargeter_asset_path": retargeter_asset_path,
            },
            "counts": counts,
            "failed_requirements": failed_requirements,
            "engine_evidence": host_result,
            "retarget_assets": {
                "source_ik_rig_asset_path": host_result.get("source_ik_rig_asset_path") or source_ik_rig_asset_path,
                "target_ik_rig_asset_path": host_result.get("target_ik_rig_asset_path") or preferred_target_ik_rig_asset_path,
                "retargeter_asset_path": host_result.get("retargeter_asset_path") or retargeter_asset_path,
            },
            "readiness": {
                "bootstrap_ready": status == "pass",
                "ready_for_animation_retry": bool((host_result.get("mapped_chain_count") or 0) > 0),
                "recommended_next_step_id": host_result.get("recommended_next_step_id") or "author_source_retarget_chains",
                "recommended_next_step_reason": host_result.get("recommended_next_step_reason") or "The bootstrap assets exist, but the imported PMX source rig still needs source chains or mapped chains.",
            },
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "d4_report_path": str(d4_report_path.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
                "retarget_bootstrap_result_path": str(host_result_path.resolve()),
            },
        },
        "aiue_demo_retarget_bootstrap_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_demo_retarget_bootstrap_report",
            notes=["internal_demo_retarget_bootstrap_gate", "demo_host_only", "retarget_asset_bootstrap_evidence"],
        ),
    )
    report_path = output_root / "d5_demo_retarget_bootstrap_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    print(f"D5 demo retarget bootstrap report written to: {report_path}")
    raise SystemExit(0 if status == "pass" else 1)


if __name__ == "__main__":
    main()
