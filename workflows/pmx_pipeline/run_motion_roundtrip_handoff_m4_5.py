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
from aiue_core.schema_utils import load_json, load_workspace_config, write_json  # noqa: E402


GATE_ID = "motion_roundtrip_handoff_m4_5"
SOURCE_GATE_ID = "motion_quality_line_m4"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bundle the current motion default-source + quality evidence into a stable handoff packet for toy-yard."
    )
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
    raise FileNotFoundError(f"Latest M4 report is missing: {candidate}")


def _existing_file(path_text: str | None) -> bool:
    text = str(path_text or "").strip()
    if not text:
        return False
    return Path(text).expanduser().exists()


def classify_roundtrip_owner(m3_5_report: dict[str, Any], m4_report: dict[str, Any]) -> str:
    candidate_snapshot = dict(m4_report.get("candidate_snapshot") or {})
    problem_owner = str(candidate_snapshot.get("problem_owner") or "")
    if problem_owner in {"toy-yard", "aiue"}:
        return problem_owner
    if str(m3_5_report.get("status") or "") != "pass" or str(m4_report.get("status") or "") != "pass":
        return "aiue"
    return "none"


def build_roundtrip_signal(status: str, owner: str) -> dict[str, Any]:
    if status == "pass":
        return {
            "signal_kind": "aiue_motion_roundtrip_handoff_signal",
            "status": "ready",
            "handoff_ready": True,
            "should_contact_toy_yard": False,
            "owner": "none",
            "reason": "aiue_motion_roundtrip_bundle_ready",
            "recommended_next_node": "toyyard_import_aiue_motion_results",
        }
    if owner == "toy-yard":
        return {
            "signal_kind": "aiue_motion_roundtrip_handoff_signal",
            "status": "attention",
            "handoff_ready": False,
            "should_contact_toy_yard": True,
            "owner": "toy-yard",
            "reason": "upstream_motion_packet_or_signal_regressed",
            "recommended_next_node": "toy_yard_motion_export_followup",
        }
    return {
        "signal_kind": "aiue_motion_roundtrip_handoff_signal",
        "status": "attention",
        "handoff_ready": False,
        "should_contact_toy_yard": False,
        "owner": "aiue",
        "reason": "aiue_motion_roundtrip_bundle_incomplete",
        "recommended_next_node": "aiue_motion_handoff_fix",
    }


def evaluate_package_handoff(m2_5_package: dict[str, Any], m4_package: dict[str, Any]) -> dict[str, Any]:
    package_id = str(m2_5_package.get("package_id") or "")
    sample_id = str(m2_5_package.get("sample_id") or "")
    scenario_id = str(m2_5_package.get("scenario_id") or "")
    artifacts = dict(m2_5_package.get("import_ready_artifacts") or {})
    failed_requirements: list[dict[str, Any]] = []

    if str(m2_5_package.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "m4_5_source_package_not_pass",
                f"M2.5 package is not import-ready for package {package_id}.",
                package_id=package_id,
                package_status=str(m2_5_package.get("status") or ""),
            )
        )
    if str(m4_package.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "m4_5_quality_package_not_pass",
                f"M4 quality package is not pass for package {package_id}.",
                package_id=package_id,
                quality_status=str(m4_package.get("status") or ""),
            )
        )

    required_artifact_keys = (
        "packet_manifest_path",
        "consumer_result_report_path",
        "preview_result_json_path",
        "before_image_path",
        "after_image_path",
        "import_action_path",
        "preview_action_path",
        "motion_import_report_path",
        "motion_preview_report_path",
        "motion_consumer_request_path",
        "motion_consumer_result_path",
        "motion_consumer_context_path",
        "motion_consumer_state_path",
    )
    for artifact_key in required_artifact_keys:
        artifact_path = str(artifacts.get(artifact_key) or "")
        if not _existing_file(artifact_path):
            failed_requirements.append(
                make_failed_requirement(
                    f"m4_5_required_artifact_missing_{artifact_key}",
                    f"Required handoff artifact is missing for package {package_id}: {artifact_key}.",
                    package_id=package_id,
                    artifact_key=artifact_key,
                    artifact_path=artifact_path,
                )
            )

    consumer_result_path = str(artifacts.get("motion_consumer_result_path") or "")
    consumer_request_path = str(artifacts.get("motion_consumer_request_path") or "")
    consumer_result = load_json(consumer_result_path) if _existing_file(consumer_result_path) else {}
    consumer_request = load_json(consumer_request_path) if _existing_file(consumer_request_path) else {}
    if str(consumer_result.get("schema_version") or "") != "motion_consumer_result_v0":
        failed_requirements.append(
            make_failed_requirement(
                "m4_5_consumer_result_schema_invalid",
                f"Consumer result schema is invalid for package {package_id}.",
                package_id=package_id,
                schema_version=str(consumer_result.get("schema_version") or ""),
            )
        )
    if str(consumer_request.get("schema_version") or "") != "motion_consumer_request_v0":
        failed_requirements.append(
            make_failed_requirement(
                "m4_5_consumer_request_schema_invalid",
                f"Consumer request schema is invalid for package {package_id}.",
                package_id=package_id,
                schema_version=str(consumer_request.get("schema_version") or ""),
            )
        )

    communication_signal = dict(consumer_result.get("communication_signal") or {})
    if str(communication_signal.get("owner") or "") != "none":
        failed_requirements.append(
            make_failed_requirement(
                "m4_5_consumer_owner_not_none",
                f"Consumer result owner is not none for package {package_id}.",
                package_id=package_id,
                owner=str(communication_signal.get("owner") or ""),
            )
        )

    import_ready = not failed_requirements
    return {
        "package_id": package_id,
        "sample_id": sample_id,
        "scenario_id": scenario_id,
        "status": "pass" if import_ready else "fail",
        "import_ready": import_ready,
        "consumer_operation": str(consumer_result.get("operation") or ""),
        "owner": str(communication_signal.get("owner") or ""),
        "generated_assets": dict(consumer_result.get("generated_assets") or {}),
        "host_resolution": dict(consumer_result.get("host_resolution") or {}),
        "request_snapshot": {
            "host_key": str(consumer_request.get("host_key") or ""),
            "motion_asset_root": str(consumer_request.get("motion_asset_root") or ""),
            "preview_level_path": str(consumer_request.get("preview_level_path") or ""),
            "runtime_ready_only": bool(consumer_request.get("runtime_ready_only")),
        },
        "quality_snapshot": {
            "resolved_animation_compatible": bool(m4_package.get("resolved_animation_compatible")),
            "retarget_success": bool(m4_package.get("retarget_success")),
            "native_pose_changed": bool(m4_package.get("native_pose_changed")),
            "native_changed_bone_count": int(m4_package.get("native_changed_bone_count") or 0),
            "native_max_location_delta": float(m4_package.get("native_max_location_delta") or 0.0),
            "required_chain_coverage": list(m4_package.get("required_chain_coverage") or []),
        },
        "artifact_refs": {
            key: str(artifacts.get(key) or "")
            for key in required_artifact_keys
        },
        "failed_requirements": failed_requirements,
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
    m4_report = load_json(source_report_path)
    failed_requirements: list[dict[str, Any]] = []

    if str(m4_report.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "m4_5_source_m4_not_pass",
                "M4 source report is not pass.",
                source_report=str(source_report_path),
                source_status=str(m4_report.get("status") or ""),
            )
        )

    m3_5_report_path = Path(str(((m4_report.get("artifacts") or {}).get("m3_5_report_path")) or "")).expanduser()
    m2_5_report_path = Path(str(((m4_report.get("artifacts") or {}).get("m2_5_report_path")) or "")).expanduser()
    if not m3_5_report_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "m4_5_m3_5_report_missing",
                "M4.5 requires a resolvable M3.5 report path.",
                m3_5_report_path=str(m3_5_report_path),
            )
        )
    if not m2_5_report_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "m4_5_m2_5_report_missing",
                "M4.5 requires a resolvable M2.5 report path.",
                m2_5_report_path=str(m2_5_report_path),
            )
        )

    m3_5_report: dict[str, Any] = {}
    m2_5_report: dict[str, Any] = {}
    handoff_packages: list[dict[str, Any]] = []
    if not failed_requirements:
        m3_5_report = load_json(m3_5_report_path)
        m2_5_report = load_json(m2_5_report_path)
        m4_package_index = {
            str(item.get("package_id") or ""): dict(item)
            for item in list(m4_report.get("package_results") or [])
        }
        for package_payload in list(m2_5_report.get("package_results") or []):
            package_id = str(package_payload.get("package_id") or "")
            handoff = evaluate_package_handoff(dict(package_payload), m4_package_index.get(package_id, {}))
            handoff_packages.append(handoff)
            failed_requirements.extend(list(handoff.get("failed_requirements") or []))

    owner = classify_roundtrip_owner(m3_5_report, m4_report)
    status = "pass" if not failed_requirements else "fail"
    roundtrip_signal = build_roundtrip_signal(status, owner)
    counts = {
        "package_count": len(handoff_packages),
        "import_ready_packages": sum(1 for item in handoff_packages if item.get("import_ready")),
        "package_failures": sum(1 for item in handoff_packages if not item.get("import_ready")),
        "owner_none_packages": sum(1 for item in handoff_packages if item.get("owner") == "none"),
    }
    bundle_payload = {
        "schema_version": "aiue_motion_roundtrip_handoff_bundle_v1",
        "generated_at_utc": now_utc(),
        "gate_id": GATE_ID,
        "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
        "source_reports": {
            "m2_5_report_path": str(m2_5_report_path),
            "m3_5_report_path": str(m3_5_report_path),
            "m4_report_path": str(source_report_path),
        },
        "profile": str((m4_report.get("candidate_snapshot") or {}).get("profile") or ""),
        "communication_signal": roundtrip_signal,
        "counts": counts,
        "packages": handoff_packages,
    }
    bundle_path = write_json(output_root / "motion_roundtrip_handoff_bundle.json", bundle_payload)

    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        latest_report_path if latest_report_path.exists() else None,
        "m4_5_motion_roundtrip_handoff_first_pass",
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
                "handoff_focus": "toy_yard_result_import_boundary",
                "bundle_output": "single_roundtrip_handoff_bundle",
                "acceptance_requirements": [
                    "m3_5_pass",
                    "m4_pass",
                    "consumer_request_schema_v0",
                    "consumer_result_schema_v0",
                    "artifact_refs_complete",
                    "owner_none_each_package",
                ],
            },
            "handoff_ready": status == "pass",
            "communication_signal": roundtrip_signal,
            "counts": counts,
            "packages": handoff_packages,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "m4_report_path": str(source_report_path),
                "m3_5_report_path": str(m3_5_report_path),
                "m2_5_report_path": str(m2_5_report_path),
                "handoff_bundle_path": str(bundle_path),
            },
        },
        "motion_roundtrip_handoff_m4_5_report",
        workflow_pack="pmx_pipeline",
        tool_name="AiUE",
        compatibility=make_compatibility_block(
            schema_family="motion_roundtrip_handoff_m4_5_report",
            notes=["internal_gate_runner", "motion_roundtrip_handoff", "toy_yard_boundary_closure"],
        ),
    )
    report_path = output_root / f"{GATE_ID}_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(f"M4.5 motion roundtrip handoff report written to: {report_path}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
